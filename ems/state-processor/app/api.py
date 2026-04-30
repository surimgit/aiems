import json

import psycopg2.pool
import redis
from flask import Flask, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields

from .config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, SITE_ID,
)

_KNOWN_SITES = [SITE_ID]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["API_TITLE"] = "State API"
    app.config["API_VERSION"] = "1.0"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    _register_routes(app)
    _start_worker()
    return app


def _start_worker() -> None:
    import asyncio
    import threading
    from .adapters.stream_consumer import run
    from .adapters.state_publisher import StatePublisher

    async def _run():
        publisher = StatePublisher()
        try:
            await run(publisher)
        finally:
            await publisher.close()

    thread = threading.Thread(target=asyncio.run, args=(_run(),), daemon=True)
    thread.start()
    print("[state-processor] stream worker 시작")


def _register_routes(app: Flask) -> None:
    api = Api(app)

    # ── DB / Redis helpers ────────────────────────────────────────────────────

    _db_pool: psycopg2.pool.ThreadedConnectionPool | None = None
    _redis_client: redis.Redis | None = None

    def get_db_pool() -> psycopg2.pool.ThreadedConnectionPool:
        nonlocal _db_pool
        if _db_pool is None:
            _db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            )
        return _db_pool

    def get_redis() -> redis.Redis:
        nonlocal _redis_client
        if _redis_client is None:
            _redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                password=REDIS_PASSWORD, decode_responses=True,
            )
        return _redis_client

    def _get_site_states(site_id: str) -> list[dict]:
        r = get_redis()
        keys = r.keys(f"state:{site_id}:*")
        if not keys:
            return []
        return [json.loads(v) for v in r.mget(*keys) if v]

    # ── Schemas ───────────────────────────────────────────────────────────────

    class PlantSchema(Schema):
        site_id = fields.String()

    class PlantSummarySchema(Schema):
        site_id = fields.String()
        timestamp = fields.String()
        net_power_kw = fields.Float()
        pv_power_kw = fields.Float()
        ess_power_kw = fields.Float()
        load_power_kw = fields.Float()
        diesel_power_kw = fields.Float()
        ess_soc_avg = fields.Float(allow_none=True)

    class DeviceStateSchema(Schema):
        device_id = fields.String()
        site_id = fields.String()
        resource_type = fields.String()
        timestamp = fields.String()
        P = fields.Float(allow_none=True)
        SOC = fields.Float(allow_none=True)
        operating_mode = fields.String(allow_none=True)
        comms_health = fields.String(allow_none=True)
        emergency = fields.Boolean()
        interlock = fields.Boolean()
        desired_state = fields.Dict(allow_none=True)
        last_command_id = fields.String(allow_none=True)

    class EventLogSchema(Schema):
        time = fields.DateTime()
        site_id = fields.String()
        device_id = fields.String()
        resource_type = fields.String()
        event_type = fields.String()
        severity = fields.String()
        message = fields.String()
        payload = fields.Dict()

    class AlarmSchema(Schema):
        alarm_id = fields.String()
        time = fields.DateTime()
        site_id = fields.String()
        device_id = fields.String()
        resource_type = fields.String()
        event_type = fields.String()
        severity = fields.String()
        message = fields.String()
        acknowledged = fields.Boolean()
        acked_at = fields.DateTime(allow_none=True)
        acked_by = fields.String(allow_none=True)

    class AlarmAckRequestSchema(Schema):
        acked_by = fields.String(required=True)

    class SensorDataSchema(Schema):
        time = fields.DateTime()
        site_id = fields.String()
        device_id = fields.String()
        resource_type = fields.String()
        p_avg = fields.Float(allow_none=True)
        p_max = fields.Float(allow_none=True)
        p_min = fields.Float(allow_none=True)
        q_avg = fields.Float(allow_none=True)
        v_avg = fields.Float(allow_none=True)
        f_avg = fields.Float(allow_none=True)
        pf_avg = fields.Float(allow_none=True)
        soc = fields.Float(allow_none=True)
        sample_count = fields.Integer()

    # ── Blueprint & Routes ────────────────────────────────────────────────────

    blp = Blueprint("state", "state", url_prefix="/api")

    # ── Plant 목록 ─────────────────────────────────────────────────────────────

    @blp.route("/plants")
    class PlantListResource(MethodView):
        @blp.response(200, PlantSchema(many=True))
        def get(self):
            """등록된 Plant 목록 조회"""
            return [{"site_id": s} for s in _KNOWN_SITES]

    # ── Plant 요약 (net_power, pv, ess, load) ────────────────────────────────

    @blp.route("/plants/<string:site_id>/summary")
    class PlantSummaryResource(MethodView):
        @blp.response(200, PlantSummarySchema)
        def get(self, site_id):
            """Plant 전력 흐름 요약 — 대시보드 상단 숫자"""
            states = _get_site_states(site_id)

            pv_power = 0.0
            ess_power = 0.0
            load_power = 0.0
            diesel_power = 0.0
            ess_soc_list = []
            latest_ts = None

            for s in states:
                rs = s.get("reported_state") or {}
                p = rs.get("P") or 0.0
                rt = (s.get("resource_type") or "").upper()
                ts = s.get("calculated_at") or s.get("timestamp")
                if ts and (latest_ts is None or ts > latest_ts):
                    latest_ts = ts

                if rt == "SOLAR":
                    pv_power += p
                elif rt == "ESS":
                    ess_power += p
                    soc = rs.get("SOC")
                    if soc is not None:
                        ess_soc_list.append(soc)
                elif rt == "LOAD":
                    load_power += abs(p)
                elif rt == "DIESEL":
                    diesel_power += p

            net_power = pv_power + ess_power + diesel_power - load_power
            ess_soc_avg = round(sum(ess_soc_list) / len(ess_soc_list), 2) if ess_soc_list else None

            return {
                "site_id": site_id,
                "timestamp": latest_ts,
                "net_power_kw": round(net_power, 2),
                "pv_power_kw": round(pv_power, 2),
                "ess_power_kw": round(ess_power, 2),
                "load_power_kw": round(load_power, 2),
                "diesel_power_kw": round(diesel_power, 2),
                "ess_soc_avg": ess_soc_avg,
            }

    # ── 실시간 디바이스 상태 ────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/state")
    class PlantStateResource(MethodView):
        @blp.response(200, DeviceStateSchema(many=True))
        def get(self, site_id):
            """Plant 내 전체 디바이스 최신 상태 (Redis)"""
            resource_type = request.args.get("resource_type")
            states = _get_site_states(site_id)
            if resource_type:
                states = [s for s in states if (s.get("resource_type") or "").upper() == resource_type.upper()]
            return [
                {
                    "device_id": s.get("device_id"),
                    "site_id": s.get("site_id"),
                    "resource_type": s.get("resource_type"),
                    "timestamp": s.get("calculated_at") or s.get("timestamp"),
                    "P": (s.get("reported_state") or {}).get("P"),
                    "SOC": (s.get("reported_state") or {}).get("SOC"),
                    "operating_mode": (s.get("reported_state") or {}).get("operating_mode"),
                    "comms_health": s.get("comms_health"),
                    "emergency": s.get("emergency", False),
                    "interlock": s.get("interlock", False),
                    "desired_state": s.get("desired_state"),
                    "last_command_id": s.get("last_command_id"),
                }
                for s in states
            ]

    # ── 이벤트 로그 ────────────────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/events")
    class PlantEventResource(MethodView):
        @blp.response(200, EventLogSchema(many=True))
        def get(self, site_id):
            """Plant 이벤트 로그 조회"""
            device_id = request.args.get("device_id")
            severity = request.args.get("severity")
            limit = min(int(request.args.get("limit", 100)), 1000)

            filters = ["site_id = %s"]
            params = [site_id]
            if device_id:
                filters.append("device_id = %s")
                params.append(device_id)
            if severity:
                filters.append("severity = %s")
                params.append(severity.upper())

            params.append(limit)
            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT time, site_id, device_id, resource_type,
                               event_type, severity, message, payload
                        FROM event_log
                        WHERE {" AND ".join(filters)}
                        ORDER BY time DESC LIMIT %s
                        """,
                        params,
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            return [
                {
                    "time": r[0], "site_id": r[1], "device_id": r[2], "resource_type": r[3],
                    "event_type": r[4], "severity": r[5], "message": r[6],
                    "payload": r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}"),
                }
                for r in rows
            ]

    # ── 알람 ───────────────────────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/alarms")
    class PlantAlarmListResource(MethodView):
        @blp.response(200, AlarmSchema(many=True))
        def get(self, site_id):
            """알람 목록 조회 — WARNING 이상 이벤트. acknowledged 필터 지원"""
            acknowledged = request.args.get("acknowledged")  # "true" / "false" / 미입력=전체
            severity = request.args.get("severity")          # WARNING / CRITICAL / EMERGENCY
            limit = min(int(request.args.get("limit", 100)), 1000)

            filters = ["site_id = %s", "severity != 'INFO'"]
            params = [site_id]
            if acknowledged is not None:
                filters.append("acknowledged = %s")
                params.append(acknowledged.lower() == "true")
            if severity:
                filters.append("severity = %s")
                params.append(severity.upper())

            params.append(limit)
            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT alarm_id, time, site_id, device_id, resource_type,
                               event_type, severity, message, acknowledged, acked_at, acked_by
                        FROM event_log
                        WHERE {" AND ".join(filters)}
                        ORDER BY time DESC LIMIT %s
                        """,
                        params,
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            return [
                {
                    "alarm_id": str(r[0]) if r[0] else None,
                    "time": r[1], "site_id": r[2], "device_id": r[3],
                    "resource_type": r[4], "event_type": r[5], "severity": r[6],
                    "message": r[7], "acknowledged": r[8],
                    "acked_at": r[9], "acked_by": r[10],
                }
                for r in rows
            ]

    @blp.route("/plants/<string:site_id>/alarms/<string:alarm_id>")
    class PlantAlarmDetailResource(MethodView):
        @blp.arguments(AlarmAckRequestSchema)
        @blp.response(200, AlarmSchema)
        def patch(self, body, site_id, alarm_id):
            """알람 확인 처리 (acknowledged = true).

            주의 (A안 정책): event_log 는 TimescaleDB hypertable 이며 30일 이후 chunk 가 압축됨.
                          압축 chunk 는 UPDATE 가 거부되므로 30일 지난 알람은 ack 불가.
                          압축 거부 에러 발생 시 410 Gone 으로 응답.
            """
            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    try:
                        cur.execute(
                            """
                            UPDATE event_log
                            SET acknowledged = true, acked_at = NOW(), acked_by = %s
                            WHERE alarm_id = %s::uuid AND site_id = %s
                            RETURNING alarm_id, time, site_id, device_id, resource_type,
                                      event_type, severity, message, acknowledged, acked_at, acked_by
                            """,
                            (body["acked_by"], alarm_id, site_id),
                        )
                        r = cur.fetchone()
                        conn.commit()
                    except Exception as e:
                        conn.rollback()
                        # TimescaleDB 압축 chunk UPDATE 실패 케이스 캐치
                        msg = str(e).lower()
                        if "compress" in msg or "chunk" in msg or "cannot update" in msg:
                            from flask import abort
                            abort(410, message="압축된 오래된 알람(30일 이상)은 ack 할 수 없습니다.")
                        raise
            finally:
                pool.putconn(conn)

            if not r:
                from flask import abort
                abort(404)

            return {
                "alarm_id": str(r[0]) if r[0] else None,
                "time": r[1], "site_id": r[2], "device_id": r[3],
                "resource_type": r[4], "event_type": r[5], "severity": r[6],
                "message": r[7], "acknowledged": r[8],
                "acked_at": r[9], "acked_by": r[10],
            }

    # ── 센서 시계열 (차트용) ──────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/sensors")
    class PlantSensorResource(MethodView):
        @blp.response(200, SensorDataSchema(many=True))
        def get(self, site_id):
            """센서 시계열 데이터 조회 (TimescaleDB)"""
            device_id = request.args.get("device_id")
            resource_type = request.args.get("resource_type")
            limit = min(int(request.args.get("limit", 100)), 1000)

            filters = ["site_id = %s"]
            params = [site_id]
            if device_id:
                filters.append("device_id = %s")
                params.append(device_id)
            if resource_type:
                filters.append("resource_type = %s")
                params.append(resource_type.upper())

            params.append(limit)
            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT time, site_id, device_id, resource_type,
                               p_avg, p_max, p_min, q_avg, v_avg, f_avg, pf_avg, soc, sample_count
                        FROM sensor_data
                        WHERE {" AND ".join(filters)}
                        ORDER BY time DESC LIMIT %s
                        """,
                        params,
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            return [
                {
                    "time": r[0], "site_id": r[1], "device_id": r[2], "resource_type": r[3],
                    "p_avg": r[4], "p_max": r[5], "p_min": r[6],
                    "q_avg": r[7], "v_avg": r[8], "f_avg": r[9], "pf_avg": r[10],
                    "soc": r[11], "sample_count": r[12],
                }
                for r in rows
            ]

    api.register_blueprint(blp)

    @app.route("/health")
    def health():
        errors = []
        try:
            r = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                password=REDIS_PASSWORD, socket_connect_timeout=2,
            )
            r.ping()
            r.close()
        except Exception as e:
            errors.append(f"redis: {e}")
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASSWORD, connect_timeout=2,
            )
            conn.close()
        except Exception as e:
            errors.append(f"db: {e}")
        if errors:
            return jsonify({"status": "degraded", "errors": errors}), 503
        return jsonify({"status": "ok"})


app = create_app()

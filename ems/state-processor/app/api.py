import json

import psycopg2.pool
import redis
from flask import Flask, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields

from .config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    CONTROL_DB_HOST, CONTROL_DB_PORT, CONTROL_DB_NAME,
    CONTROL_DB_USER, CONTROL_DB_PASSWORD,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, SITE_ID,
)

_KNOWN_SITES = [SITE_ID]

# ── DTO 변환 헬퍼 (module-level) ──────────────────────────────────────────────
# 시뮬레이터의 DIESEL → 프론트 enum DIESEL_GENERATOR 로 변환.
_RESOURCE_TYPE_MAP = {
    "DIESEL": "DIESEL_GENERATOR",
}


def _state_to_resource(state: dict) -> dict:
    """Redis state → 프론트 ResourceDto."""
    rt_raw = (state.get("resource_type") or "").upper()
    rt = _RESOURCE_TYPE_MAP.get(rt_raw, rt_raw)
    reported = state.get("reported_state") or {}
    comms = state.get("comms_health")

    # 단일 status 산출: emergency > stale > NORMAL.
    if state.get("emergency"):
        status = "EMERGENCY"
    elif comms == "stale":
        status = "OFFLINE"
    else:
        status = "NORMAL"

    out: dict = {
        "resource_id": state.get("device_id"),
        "resource_type": rt,
        "name": state.get("device_id"),
        "status": status,
        "comms_health": comms,
    }

    if rt == "SWITCH":
        out["position"] = reported.get("switch_state") or "UNKNOWN"
        out["controllable"] = reported.get("controllable")
        out["interlock_blocked"] = reported.get("interlock_blocked")
        return out

    telemetry = {
        "p_kw": reported.get("P"),
        "q_kvar": reported.get("Q"),
        "v_volt": reported.get("V"),
        "i_amp": reported.get("I"),
        "f_hz": reported.get("f"),
        "pf": reported.get("PF"),
        "kwh": reported.get("kwh_total") or reported.get("kwh"),
        "soc": reported.get("SOC"),
        "operating_mode": reported.get("operating_mode"),
    }
    out["telemetry"] = {k: v for k, v in telemetry.items() if v is not None}
    return out


def _state_to_ess_status(state: dict) -> dict:
    """ESS state → 프론트 EssStatusDto. ESS 가 아니면 None."""
    rt = (state.get("resource_type") or "").upper()
    if rt != "ESS":
        return None
    reported = state.get("reported_state") or {}
    p = reported.get("P") or 0.0
    mode = (reported.get("operating_mode") or "").lower()

    # P 부호 + operating_mode 로 status 판정 (DTO enum: idle/charging/discharging/fault)
    if state.get("emergency"):
        status = "fault"
    elif mode == "charge" or p < 0:
        status = "charging"
    elif mode == "discharge" or p > 0:
        status = "discharging"
    else:
        status = "idle"

    return {
        "ess_id": state.get("device_id"),
        "name": state.get("device_id"),
        "capacity_kwh": reported.get("capacity_kwh") or 0.0,
        "max_power_kw": reported.get("power_limit_kw") or 0.0,
        "soc": reported.get("SOC") or 0.0,
        "soh": reported.get("SOH"),
        "status": status,
        "power_kw": p,
        "updated_at": state.get("calculated_at") or state.get("timestamp"),
    }


def _compute_summary(site_id: str, states: list[dict]) -> dict:
    """Redis state 리스트 → 프론트 PlantSummaryDto.

    grid_power_kw 는 시뮬레이터에 GRID 자원이 없으므로 0 으로 채운다.
    diesel_power_kw / ess_soc_avg 는 프론트 DTO 외 추가 정보 (호환).
    """
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
        "grid_power_kw": 0.0,
        "load_power_kw": round(load_power, 2),
        "diesel_power_kw": round(diesel_power, 2),
        "ess_soc_avg": ess_soc_avg,
    }


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["API_TITLE"] = "State API"
    app.config["API_VERSION"] = "1.0"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    _register_error_handlers(app)
    _register_routes(app)
    _start_worker()
    return app


def _register_error_handlers(app: Flask) -> None:
    """S305 표준 에러 응답 형식으로 통일.

    모든 HTTP 에러를 아래 형식으로 직렬화한다:
      { error_code, message, trace_id, details }
    Flask-Smorest 422 validation 에러도 동일 형식으로 래핑.
    """
    import uuid as _uuid

    def _err(code: str, msg: str, details: dict | None = None, status: int = 500):
        return jsonify({
            "error_code": code,
            "message": msg,
            "trace_id": str(_uuid.uuid4()),
            "details": details or {},
        }), status

    @app.errorhandler(400)
    def _h400(e):
        return _err("BAD_REQUEST", getattr(e, "description", str(e)), status=400)

    @app.errorhandler(404)
    def _h404(e):
        return _err("NOT_FOUND", getattr(e, "description", str(e)), status=404)

    @app.errorhandler(405)
    def _h405(e):
        return _err("METHOD_NOT_ALLOWED", getattr(e, "description", str(e)), status=405)

    @app.errorhandler(410)
    def _h410(e):
        return _err("GONE", getattr(e, "description", str(e)), status=410)

    @app.errorhandler(422)
    def _h422(e):
        # Flask-Smorest validation 에러: e.data['messages'] 에 필드별 오류 포함.
        details: dict = {}
        if hasattr(e, "data") and isinstance(e.data, dict):
            details = e.data.get("messages", {})
        return _err("VALIDATION_ERROR", "요청 데이터가 올바르지 않습니다.", details=details, status=422)

    @app.errorhandler(500)
    def _h500(e):
        return _err("INTERNAL_ERROR", "서버 내부 오류가 발생했습니다.", status=500)


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
    _control_db_pool: psycopg2.pool.ThreadedConnectionPool | None = None
    _redis_client: redis.Redis | None = None

    def get_db_pool() -> psycopg2.pool.ThreadedConnectionPool:
        # TimescaleDB pool — 시계열 (sensor_data / event_log / control_history).
        nonlocal _db_pool
        if _db_pool is None:
            _db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            )
        return _db_pool

    def get_control_db_pool() -> psycopg2.pool.ThreadedConnectionPool:
        # PostgreSQL.control_db pool — 운영 데이터 (topology_*).
        # state-processor 는 read-only 로만 접근 (단일 진실은 EMS 토폴로지 API).
        nonlocal _control_db_pool
        if _control_db_pool is None:
            _control_db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=CONTROL_DB_HOST, port=CONTROL_DB_PORT,
                dbname=CONTROL_DB_NAME, user=CONTROL_DB_USER, password=CONTROL_DB_PASSWORD,
            )
        return _control_db_pool

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
        timestamp = fields.String(allow_none=True)
        net_power_kw = fields.Float()
        pv_power_kw = fields.Float()
        ess_power_kw = fields.Float()
        grid_power_kw = fields.Float()  # 시뮬레이터에 GRID 없음 → 0 고정. 프론트 DTO 필수.
        load_power_kw = fields.Float()
        diesel_power_kw = fields.Float()  # 프론트 DTO 외 추가 필드 — 호환성 OK.
        ess_soc_avg = fields.Float(allow_none=True)

    class EssStatusSchema(Schema):
        ess_id = fields.String()
        name = fields.String(allow_none=True)
        capacity_kwh = fields.Float()
        max_power_kw = fields.Float()
        soc = fields.Float()
        soh = fields.Float(allow_none=True)
        status = fields.String()  # 'idle' / 'charging' / 'discharging' / 'fault'
        power_kw = fields.Float(allow_none=True)
        updated_at = fields.String(allow_none=True)

    class PlantStateSchema(Schema):
        site_id = fields.String()
        timestamp = fields.String(allow_none=True)
        # 아래 3개는 프론트에서 옵션. 본 응답에서는 항상 채워서 내보낸다.
        ess_list = fields.List(fields.Nested(EssStatusSchema))
        resources = fields.List(fields.Dict())  # ResourceSchema 와 동일 구조
        summary = fields.Nested(PlantSummarySchema)

    # ── Topology DTOs (프론트 api-contracts.ts 기준) ────────────────────────
    class PositionSchema(Schema):
        x = fields.Float()
        y = fields.Float()

    class TopologyNodeSchema(Schema):
        node_id = fields.String()
        node_type = fields.String()           # GENERATION / STORAGE / LOAD / GRID / BUS
        resource_id = fields.String(allow_none=True)
        position = fields.Nested(PositionSchema)
        status = fields.String()              # NORMAL / WARNING / EMERGENCY

    class TopologyLineSchema(Schema):
        line_id = fields.String()
        from_node_id = fields.String()
        to_node_id = fields.String()
        direction = fields.String()           # FORWARD / REVERSE / BIDIRECTIONAL
        flow_kw = fields.Float()
        status = fields.String()              # NORMAL / OPEN / BLOCKED / FAULT / UNKNOWN

    class TopologySwitchSchema(Schema):
        switch_id = fields.String()
        line_id = fields.String()
        position = fields.String()            # OPEN / CLOSED
        controllable = fields.Boolean()
        interlock_blocked = fields.Boolean()

    class TopologySchema(Schema):
        site_id = fields.String()
        nodes = fields.List(fields.Nested(TopologyNodeSchema))
        lines = fields.List(fields.Nested(TopologyLineSchema))
        switches = fields.List(fields.Nested(TopologySwitchSchema))

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

    # 프론트 EventDto 와 1:1 매칭 (api-contracts.ts).
    # DB 컬럼명 → DTO 필드명: time→timestamp, event_type→event_code, device_id→resource_id,
    # alarm_id → event_id (DB에선 알람용 UUID 였지만 DTO 의 식별자로 재사용).
    class EventLogSchema(Schema):
        event_id = fields.String()
        event_code = fields.String()
        severity = fields.String()  # INFO / WARNING / ALARM / EMERGENCY
        message = fields.String(allow_none=True)
        timestamp = fields.String()
        site_id = fields.String(allow_none=True)
        resource_id = fields.String(allow_none=True)
        trace_id = fields.String(allow_none=True)
        reason_code = fields.String(allow_none=True)
        payload = fields.Dict(allow_none=True)

    # 프론트 AlarmData 와 1:1 매칭 (common.ts).
    # 매핑: alarm_id, severity→level (소문자), event_type→code, time→timestamp,
    #       device_id→ess_id (옵션 — ESS device 일 때만 의미).
    class AlarmSchema(Schema):
        alarm_id = fields.String(allow_none=True)
        level = fields.String()  # 'info' / 'warning' / 'critical'
        code = fields.String()
        message = fields.String(allow_none=True)
        ess_id = fields.String(allow_none=True)
        timestamp = fields.String()
        acknowledged = fields.Boolean(allow_none=True)
        # 추가 필드 (프론트 무시 가능, 호환성):
        site_id = fields.String(allow_none=True)
        resource_type = fields.String(allow_none=True)
        acked_at = fields.String(allow_none=True)
        acked_by = fields.String(allow_none=True)

    class AlarmAckRequestSchema(Schema):
        acked_by = fields.String(load_default="operator")

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

    # 프론트 ResourceDto 와 1:1 매칭. 필드명 / 타입은 frontend/src/types/api-contracts.ts 정답.
    class ResourceTelemetrySchema(Schema):
        p_kw = fields.Float(allow_none=True)
        q_kvar = fields.Float(allow_none=True)
        v_volt = fields.Float(allow_none=True)
        i_amp = fields.Float(allow_none=True)
        f_hz = fields.Float(allow_none=True)
        pf = fields.Float(allow_none=True)
        kwh = fields.Float(allow_none=True)
        soc = fields.Float(allow_none=True)
        operating_mode = fields.String(allow_none=True)

    class ResourceSchema(Schema):
        resource_id = fields.String()
        resource_type = fields.String()
        name = fields.String(allow_none=True)
        status = fields.String(allow_none=True)
        comms_health = fields.String(allow_none=True)
        position = fields.String(allow_none=True)
        controllable = fields.Boolean(allow_none=True)
        interlock_blocked = fields.Boolean(allow_none=True)
        from_node = fields.String(allow_none=True)
        to_node = fields.String(allow_none=True)
        flow_kw = fields.Float(allow_none=True)
        import_kw = fields.Float(allow_none=True)
        export_kw = fields.Float(allow_none=True)
        limit_kw = fields.Float(allow_none=True)
        telemetry = fields.Nested(ResourceTelemetrySchema, allow_none=True)

    # ── Blueprint & Routes ────────────────────────────────────────────────────

    blp = Blueprint("state", "state", url_prefix="/api")

    def _alarm_level(severity: str) -> str:
        s = (severity or "").upper()
        if s in ("CRITICAL", "EMERGENCY"):
            return "critical"
        if s == "WARNING":
            return "warning"
        return "info"

    def _alarm_row_to_dto(row: tuple) -> dict:
        return {
            "alarm_id": str(row[0]) if row[0] else None,
            "level": _alarm_level(row[6]),
            "code": row[5],
            "message": row[7],
            # ESS device 인 경우만 ess_id 채움. 그 외엔 device_id 를 ess_id 자리에 넣지 않고 None.
            "ess_id": row[3] if (row[4] or "").upper() == "ESS" else None,
            "timestamp": row[1].isoformat() if row[1] else None,
            "acknowledged": row[8],
            # 호환 추가 필드 (프론트 type 무시 가능):
            "site_id": row[2],
            "resource_type": row[4],
            "acked_at": row[9].isoformat() if row[9] else None,
            "acked_by": row[10],
        }

    def _ack_alarm(site_id: str, alarm_id: str, acked_by: str) -> dict:
        """알람 확인 처리 공통 로직. PATCH와 POST /ack가 같은 DTO를 반환한다."""
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
                        (acked_by, alarm_id, site_id),
                    )
                    row = cur.fetchone()
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    # TimescaleDB 압축 chunk UPDATE 실패 케이스 캐치
                    msg = str(e).lower()
                    if "compress" in msg or "chunk" in msg or "cannot update" in msg:
                        from flask import abort
                        abort(410, "압축된 오래된 알람(30일 이상)은 ack 할 수 없습니다.")
                    raise
        finally:
            pool.putconn(conn)

        if not row:
            from flask import abort
            abort(404)

        return _alarm_row_to_dto(row)

    # ── Plant 목록 ─────────────────────────────────────────────────────────────

    @blp.route("/plants")
    class PlantListResource(MethodView):
        @blp.response(200, PlantSchema(many=True))
        def get(self):
            """등록된 Plant 목록 조회 — control_db.topology_nodes 의 distinct site_id.
            DB 조회 실패 또는 결과 없음이면 환경변수 SITE_ID 로 fallback (단일 plant 시연 호환).
            """
            site_ids: list[str] = []
            try:
                pool = get_control_db_pool()
                conn = pool.getconn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT DISTINCT site_id FROM topology_nodes ORDER BY site_id")
                        site_ids = [r[0] for r in cur.fetchall()]
                finally:
                    pool.putconn(conn)
            except Exception as e:
                print(f"[state-processor] plants 조회 실패, fallback to env: {e}")

            if not site_ids:
                site_ids = list(_KNOWN_SITES)

            return [{"site_id": s} for s in site_ids]

    # ── Plant 요약 (net_power, pv, ess, load) ────────────────────────────────

    @blp.route("/plants/<string:site_id>/summary")
    class PlantSummaryResource(MethodView):
        @blp.response(200, PlantSummarySchema)
        def get(self, site_id):
            """Plant 전력 흐름 요약 — 대시보드 상단 숫자"""
            return _compute_summary(site_id, _get_site_states(site_id))

    # ── 실시간 디바이스 상태 ────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/state")
    class PlantStateResource(MethodView):
        @blp.response(200, PlantStateSchema)
        def get(self, site_id):
            """Plant 통합 상태 — summary + resources + ess_list 한 번에 (대시보드 메인 응답)."""
            states = _get_site_states(site_id)
            summary = _compute_summary(site_id, states)
            resources = [_state_to_resource(s) for s in states]
            ess_list = [e for e in (_state_to_ess_status(s) for s in states) if e is not None]
            return {
                "site_id": site_id,
                "timestamp": summary["timestamp"],
                "ess_list": ess_list,
                "resources": resources,
                "summary": summary,
            }

    # device-level 원시 상태가 필요한 경우의 보조 엔드포인트 (디버깅 / 내부용).
    @blp.route("/plants/<string:site_id>/devices")
    class PlantDeviceListResource(MethodView):
        @blp.response(200, DeviceStateSchema(many=True))
        def get(self, site_id):
            """Plant 내 전체 디바이스 원시 상태 (Redis 그대로)"""
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

    @blp.route("/plants/<string:site_id>/resources")
    class PlantResourceListResource(MethodView):
        @blp.response(200, ResourceSchema(many=True))
        def get(self, site_id):
            """Plant 자원 목록 (대시보드 카드용) — Redis state → ResourceDto"""
            return [_state_to_resource(s) for s in _get_site_states(site_id)]

    # ── 토폴로지 (단선도) ─────────────────────────────────────────────────────
    # 단일 진실: control_db.topology_{nodes,lines,switches}.
    # 동적 정보(라인 flow, 노드 emergency 등) 는 Redis state 로 보강.

    @blp.route("/plants/<string:site_id>/topology")
    class PlantTopologyResource(MethodView):
        @blp.response(200, TopologySchema)
        def get(self, site_id):
            """Plant 토폴로지 — DB 정적 정보 + Redis state 로 status/flow 산출."""
            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT node_id, node_type, device_id, label, x, y
                          FROM topology_nodes WHERE site_id = %s
                        """,
                        (site_id,),
                    )
                    node_rows = cur.fetchall()

                    cur.execute(
                        """
                        SELECT line_id, from_node_id, to_node_id, rating_kw
                          FROM topology_lines WHERE site_id = %s
                        """,
                        (site_id,),
                    )
                    line_rows = cur.fetchall()

                    cur.execute(
                        """
                        SELECT switch_id, line_id, is_closed, controllable
                          FROM topology_switches WHERE site_id = %s
                        """,
                        (site_id,),
                    )
                    switch_rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            # Redis state 인덱스 (device_id → state) — 노드 status 산출용.
            states = _get_site_states(site_id)
            state_by_device = {s.get("device_id"): s for s in states if s.get("device_id")}
            state_by_switch = {
                s.get("device_id"): s for s in states
                if (s.get("resource_type") or "").upper() == "SWITCH"
            }

            # ── nodes 변환 ──
            def _node_status(device_id: str | None) -> str:
                if not device_id:
                    return "NORMAL"
                s = state_by_device.get(device_id) or {}
                if s.get("emergency"):
                    return "EMERGENCY"
                if (s.get("comms_health") or "") == "stale":
                    return "WARNING"
                return "NORMAL"

            nodes = [
                {
                    "node_id": r[0],
                    "node_type": r[1],
                    "resource_id": r[2],
                    "position": {"x": r[4] if r[4] is not None else 0.0,
                                 "y": r[5] if r[5] is not None else 0.0},
                    "status": _node_status(r[2]),
                }
                for r in node_rows
            ]

            # ── switches 인덱스 (line_id → switch row) ──
            sw_by_line: dict[str, tuple] = {r[1]: r for r in switch_rows}

            # ── lines 변환 (flow_kw 는 Redis state 에서 from_node device 의 P 사용) ──
            node_device_map = {r[0]: r[2] for r in node_rows}

            def _line_flow_kw(from_node_id: str) -> float:
                dev_id = node_device_map.get(from_node_id)
                if not dev_id:
                    return 0.0
                s = state_by_device.get(dev_id) or {}
                p = (s.get("reported_state") or {}).get("P")
                return float(p) if p is not None else 0.0

            def _line_status(line_id: str) -> str:
                # 스위치가 OPEN 이면 라인도 OPEN.
                # 우선순위: Redis state (실시간) > DB is_closed (정적).
                # blocked / fault 는 별도 시그널이 없어 미구현.
                sw = sw_by_line.get(line_id)
                if not sw:
                    return "UNKNOWN"
                switch_id = sw[0]
                sw_state = state_by_switch.get(switch_id) or {}
                live_pos = (sw_state.get("reported_state") or {}).get("switch_state")
                if live_pos == "OPEN":
                    return "OPEN"
                if live_pos == "CLOSED":
                    return "NORMAL"
                # Redis 에 정보 없으면 DB fallback (sw[2] = is_closed)
                return "NORMAL" if sw[2] else "OPEN"

            def _direction(flow_kw: float) -> str:
                if flow_kw > 0.01:
                    return "FORWARD"
                if flow_kw < -0.01:
                    return "REVERSE"
                return "BIDIRECTIONAL"

            lines = []
            for r in line_rows:
                line_id, from_node_id, to_node_id, _rating = r
                flow = _line_flow_kw(from_node_id)
                lines.append({
                    "line_id": line_id,
                    "from_node_id": from_node_id,
                    "to_node_id": to_node_id,
                    "direction": _direction(flow),
                    "flow_kw": round(flow, 2),
                    "status": _line_status(line_id),
                })

            # ── switches 변환 ──
            # interlock_blocked 는 switch state Redis 에서 가져옴.
            switches = []
            for r in switch_rows:
                switch_id, line_id, is_closed, controllable = r
                sw_state = state_by_switch.get(switch_id) or {}
                reported = sw_state.get("reported_state") or {}
                # DB is_closed 보다 Redis 의 실시간 switch_state 가 우선.
                position = reported.get("switch_state") or ("CLOSED" if is_closed else "OPEN")
                switches.append({
                    "switch_id": switch_id,
                    "line_id": line_id,
                    "position": position,
                    "controllable": bool(controllable),
                    "interlock_blocked": bool(reported.get("interlock_blocked", False)),
                })

            return {
                "site_id": site_id,
                "nodes": nodes,
                "lines": lines,
                "switches": switches,
            }

    # ── 이벤트 로그 ────────────────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/events")
    class PlantEventResource(MethodView):
        @blp.response(200, EventLogSchema(many=True))
        def get(self, site_id):
            """Plant 이벤트 로그 조회 — 프론트 EventDto 형식."""
            device_id = request.args.get("device_id")
            severity = request.args.get("severity")
            limit = min(int(request.args.get("limit", 100)), 1000)

            filters = ["site_id = %s"]
            params = [site_id]
            if device_id:
                filters.append("device_id = %s")
                params.append(device_id)
            if severity:
                # 프론트는 'ALARM' 으로 보내지만 DB 는 'CRITICAL' 로 저장 — 역매핑
                sev_upper = severity.upper()
                db_sev = "CRITICAL" if sev_upper == "ALARM" else sev_upper
                filters.append("severity = %s")
                params.append(db_sev)

            params.append(limit)
            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT alarm_id, time, site_id, device_id,
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

            # DB severity ↔ 프론트 enum 매핑. 'CRITICAL' 만 ALARM 으로, 나머지는 그대로.
            def _map_sev(s: str) -> str:
                return "ALARM" if (s or "").upper() == "CRITICAL" else (s or "").upper()

            return [
                {
                    "event_id": str(r[0]) if r[0] else None,
                    "timestamp": r[1].isoformat() if r[1] else None,
                    "site_id": r[2],
                    "resource_id": r[3],
                    "event_code": r[4],
                    "severity": _map_sev(r[5]),
                    "message": r[6],
                    "payload": r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}"),
                }
                for r in rows
            ]

    # ── 알람 ───────────────────────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/alarms")
    class PlantAlarmListResource(MethodView):
        @blp.response(200, AlarmSchema(many=True))
        def get(self, site_id):
            """알람 목록 조회 — WARNING 이상 이벤트. 프론트 AlarmData DTO 형식."""
            acknowledged = request.args.get("acknowledged")  # "true" / "false" / 미입력=전체
            severity = request.args.get("severity")          # info / warning / critical (프론트) 또는 WARNING / CRITICAL (DB)
            limit = min(int(request.args.get("limit", 100)), 1000)

            filters = ["site_id = %s", "severity != 'INFO'"]
            params = [site_id]
            if acknowledged is not None:
                filters.append("acknowledged = %s")
                params.append(acknowledged.lower() == "true")
            if severity:
                # 프론트 'critical' → DB 'CRITICAL' 매핑.
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

            return [_alarm_row_to_dto(r) for r in rows]

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
            return _ack_alarm(site_id, alarm_id, body.get("acked_by") or "operator")

    @blp.route("/plants/<string:site_id>/alarms/<string:alarm_id>/ack")
    class PlantAlarmAckResource(MethodView):
        @blp.arguments(AlarmAckRequestSchema)
        @blp.response(200, AlarmSchema)
        def post(self, body, site_id, alarm_id):
            """알람 확인 처리. 프론트/문서 표준 경로."""
            return _ack_alarm(site_id, alarm_id, body.get("acked_by") or "operator")

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

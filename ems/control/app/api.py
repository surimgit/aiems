import asyncio
import json
import threading
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt_client
import psycopg2.pool
from flask import Flask, abort, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields, validate
from prometheus_flask_exporter import PrometheusMetrics

from .config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    TS_DB_HOST, TS_DB_PORT, TS_DB_NAME, TS_DB_USER, TS_DB_PASSWORD,
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    SITE_ID, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
)

# operator 명령의 ACK 추적을 위해 asyncio 루프와 공유하는 pending dict
# command_id → (sent_at, device_id, resource_type)
import time as _time
_shared_pending_acks: dict[str, tuple[float, str, str]] = {}

# device_id → sent_at (cooldown 중인 장치 추적)
_COOLDOWN_SEC = 35.0  # ACK timeout(30s)보다 약간 길게
_device_cooldown: dict[str, float] = {}

# ess_mode 명령의 dead-band: 마지막 발행한 (mode, target_power_kw) 기억
# 변화량이 _ESS_DEADBAND_KW 미만이면 재발행 안 함
_ESS_DEADBAND_KW = 2.0
_device_last_ess_cmd: dict[str, tuple[str, float]] = {}  # device_id → (mode, kw)

# Operator 명령용 MQTT 싱글턴 — 매번 connect/disconnect 방지
_operator_mqtt: mqtt_client.Client | None = None


def _get_operator_mqtt() -> mqtt_client.Client:
    global _operator_mqtt
    if _operator_mqtt is None or not _operator_mqtt.is_connected():
        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        if MQTT_USER:
            client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        _operator_mqtt = client
    return _operator_mqtt


def create_app() -> Flask:
    app = Flask(__name__)
    PrometheusMetrics(app, group_by="endpoint")
    app.config["API_TITLE"] = "Control API"
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
        # S305 §3: INVALID_REQUEST — 요청 형식 또는 필수 필드 오류
        return _err("INVALID_REQUEST", getattr(e, "description", str(e)), status=400)

    @app.errorhandler(404)
    def _h404(e):
        return _err("NOT_FOUND", getattr(e, "description", str(e)), status=404)

    @app.errorhandler(405)
    def _h405(e):
        # S305 §3: METHOD_NOT_ALLOWED (§4: 405 추가됨)
        return _err("METHOD_NOT_ALLOWED", getattr(e, "description", str(e)), status=405)

    @app.errorhandler(422)
    def _h422(e):
        # S305 §3: INVALID_REQUEST — 의미상 처리 불가 (validation 실패)
        # Flask-Smorest validation 에러: e.data['messages'] 에 필드별 오류 포함.
        details: dict = {}
        if hasattr(e, "data") and isinstance(e.data, dict):
            details = e.data.get("messages", {})
        return _err("INVALID_REQUEST", "요청 데이터가 올바르지 않습니다.", details=details, status=422)

    @app.errorhandler(500)
    def _h500(e):
        return _err("INTERNAL_ERROR", "서버 내부 오류가 발생했습니다.", status=500)


def _start_worker() -> None:
    from .adapters.state_reader import StateReader
    from .adapters.mqtt_commander import MqttCommander
    from .adapters.db_writer import ControlDBWriter
    from .adapters.event_publisher import EventPublisher
    from .adapters.policy_reader import PolicyReader
    from .adapters.topology_reader import TopologyReader
    from .domain.rule_engine import run
    from .config import CONTROL_INTERVAL_SECONDS, STATE_PROCESSOR_URL, SITE_ID

    _POLICY_REFRESH_INTERVAL = 10

    def _should_send(cmd: dict, states: dict) -> bool:
        """3중 체크: cooldown → pending ACK → 현재 모드 비교."""
        device_id = cmd["device_id"]
        now = _time.monotonic()

        # 1. cooldown 중인 장치는 skip
        cooldown_since = _device_cooldown.get(device_id)
        if cooldown_since is not None:
            if now - cooldown_since < _COOLDOWN_SEC:
                return False
            else:
                del _device_cooldown[device_id]

        # 2. 이 장치로 보낸 명령 중 ACK 대기 중인 게 있으면 skip
        pending_devices = {dev_id for _, (_, dev_id, _) in _shared_pending_acks.items()}
        if device_id in pending_devices:
            return False

        # 3. 현재 모드가 요청 모드와 이미 같으면 skip
        state = states.get(device_id, {})
        reported = state.get("reported_state") or {}
        current_mode = reported.get("operating_mode", "standby")
        current_mode_lower = (current_mode or "").lower()

        if current_mode_lower in ("fault", "error") and cmd["command_type"] != "reset":
            print(f"[control] skip {device_id}: device is in FAULT state")
            return False

        if cmd["command_type"] == "ess_mode":
            requested_mode = cmd["payload"].get("mode", "standby")
            requested_kw = float(cmd["payload"].get("target_power_kw", 0.0))

            # 모드 전환이면 무조건 발행
            if current_mode != requested_mode:
                _device_last_ess_cmd[device_id] = (requested_mode, requested_kw)
                return True

            # 같은 모드면 dead-band 체크 — power set-point 변화가 작으면 스킵
            last_mode, last_kw = _device_last_ess_cmd.get(device_id, (None, None))
            if last_mode == requested_mode and last_kw is not None:
                if abs(requested_kw - last_kw) < _ESS_DEADBAND_KW:
                    return False

            _device_last_ess_cmd[device_id] = (requested_mode, requested_kw)
            return True

        if cmd["command_type"] == "start":
            return current_mode_lower not in ("running", "starting")

        if cmd["command_type"] == "stop":
            return current_mode_lower not in ("off", "stopped", "stopping", "idle")

        if cmd["command_type"] == "load_control":
            # 운전 중일 때만 부하조정 의미 있음
            return current_mode_lower == "running"

        return True

    async def _refresh_policy_loop(policy: PolicyReader) -> None:
        while True:
            await asyncio.sleep(_POLICY_REFRESH_INTERVAL)
            try:
                await policy.refresh()
            except Exception as e:
                print(f"[control] policy refresh 실패: {e}")

    async def _run():
        reader = StateReader()
        db = ControlDBWriter()
        event_pub = EventPublisher()
        policy = PolicyReader()
        topology = TopologyReader(STATE_PROCESSOR_URL, SITE_ID)
        await db.connect()
        await event_pub.connect()
        await policy.connect()
        print(f"[control] 시작: {CONTROL_INTERVAL_SECONDS}초 주기 판단")

        refresh_task = asyncio.create_task(_refresh_policy_loop(policy))

        try:
            async with MqttCommander(db, event_pub, _shared_pending_acks, _device_cooldown) as commander:
                while True:
                    try:
                        states = await reader.get_all()
                        if states:
                            graph = await topology.fetch()
                            commands, events = await run(states, policy, event_pub, topology_graph=graph)
                            sent = 0
                            for cmd in commands:
                                if not _should_send(cmd, states):
                                    continue
                                await commander.send(cmd)
                                _device_cooldown[cmd["device_id"]] = _time.monotonic()
                                sent += 1
                            if sent == 0:
                                print(f"[control] 판단 완료: 명령 없음 (장치 {len(states)}개)")
                            for evt in events:
                                await event_pub.publish(evt)
                    except Exception as e:
                        print(f"[control] 오류: {e}")

                    await asyncio.sleep(CONTROL_INTERVAL_SECONDS)
        finally:
            refresh_task.cancel()
            await topology.close()
            await db.close()
            await event_pub.close()
            await policy.close()

    thread = threading.Thread(target=asyncio.run, args=(_run(),), daemon=True)
    thread.start()
    print("[control] 제어 루프 시작")


def _register_routes(app: Flask) -> None:
    api = Api(app)

    # ── DB helper ─────────────────────────────────────────────────────────────

    _pool: psycopg2.pool.ThreadedConnectionPool | None = None
    _ts_pool: psycopg2.pool.ThreadedConnectionPool | None = None

    def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
        # PostgreSQL.control_db — control_policy 등.
        nonlocal _pool
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            )
        return _pool

    def get_ts_pool() -> psycopg2.pool.ThreadedConnectionPool:
        # TimescaleDB — control_history 시계열.
        nonlocal _ts_pool
        if _ts_pool is None:
            _ts_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=TS_DB_HOST, port=TS_DB_PORT,
                dbname=TS_DB_NAME, user=TS_DB_USER, password=TS_DB_PASSWORD,
            )
        return _ts_pool

    # ── Schemas ───────────────────────────────────────────────────────────────

    class OperatorCommandRequestSchema(Schema):
        site_id = fields.String(required=True)
        edge_id = fields.String(load_default=None, allow_none=True)
        device_id = fields.String(required=True)
        resource_type = fields.String(required=True)
        action = fields.String(
            required=True,
            validate=validate.OneOf([
                "START_CHARGE", "STOP_CHARGE",
                "START_DISCHARGE", "STOP_DISCHARGE",
                "START_GENERATOR", "STOP_GENERATOR",
                "OPEN_SWITCH", "CLOSE_SWITCH",
                "SHED_LOAD", "RESTORE_LOAD",
                "SET_POWER_LIMIT", "STANDBY",
            ]),
        )
        requested_by = fields.String(required=True)
        reason = fields.String(load_default="")
        source_recommendation_id = fields.String(load_default=None, allow_none=True)

    class CommandAcceptedResponseSchema(Schema):
        command_id = fields.String()
        status = fields.String()
        site_id = fields.String()
        edge_id = fields.String(allow_none=True)
        device_id = fields.String()
        action = fields.String()
        created_at = fields.DateTime()

    # 프론트 ControlResult DTO 와 매칭 (common.ts).
    # 매핑: ack_status→status, device_id→target_resource_id, time→created_at,
    #       command_type+payload → action 역추론.
    class CommandHistorySchema(Schema):
        command_id = fields.String()
        status = fields.String()                  # CommandStatus (ACCEPTED / REJECTED / TIMEOUT 등)
        site_id = fields.String()
        target_resource_id = fields.String()      # device_id 의 별칭
        action = fields.String()                  # CommandAction
        created_at = fields.String()
        # 추가 정보 (프론트 무시 가능, 디버깅 / 호환):
        resource_type = fields.String(allow_none=True)
        command_type = fields.String(allow_none=True)
        payload = fields.Dict(allow_none=True)
        reason = fields.String(allow_none=True)
        issued_by = fields.String(allow_none=True)


    class PolicySchema(Schema):
        key = fields.String()
        value = fields.Float()
        unit = fields.String(allow_none=True)
        description = fields.String(allow_none=True)
        updated_at = fields.DateTime()
        updated_by = fields.String()

    class PolicyUpdateRequestSchema(Schema):
        value = fields.Float(required=True)
        updated_by = fields.String(load_default="operator")

    class PolicyHistorySchema(Schema):
        id = fields.Integer()
        key = fields.String()
        old_value = fields.Float(allow_none=True)
        new_value = fields.Float()
        changed_at = fields.DateTime()
        changed_by = fields.String()

    class RecommendationDecisionSchema(Schema):
        requested_by = fields.String(required=True)
        reason = fields.String(load_default="")

    # ── Action 변환 ───────────────────────────────────────────────────────────

    _ACTION_MAP = {
        "START_CHARGE":    {"command_type": "ess_mode", "payload": {"mode": "charge",    "target_power_kw": 0.0}},
        "STOP_CHARGE":     {"command_type": "ess_mode", "payload": {"mode": "standby",   "target_power_kw": 0.0}},
        "START_DISCHARGE": {"command_type": "ess_mode", "payload": {"mode": "discharge", "target_power_kw": 0.0}},
        "STOP_DISCHARGE":  {"command_type": "ess_mode", "payload": {"mode": "standby",   "target_power_kw": 0.0}},
        "START_GENERATOR": {"command_type": "start",    "payload": {}},
        "STOP_GENERATOR":  {"command_type": "stop",     "payload": {}},
        "STANDBY":         {"command_type": "ess_mode", "payload": {"mode": "standby",   "target_power_kw": 0.0}},
        "SHED_LOAD":       {"command_type": "load_shed",      "payload": {"reduction_ratio": 1.0}},
        "RESTORE_LOAD":    {"command_type": "load_shed",      "payload": {"reduction_ratio": 0.0}},
        "OPEN_SWITCH":     {"command_type": "open",           "payload": {}},
        "CLOSE_SWITCH":    {"command_type": "close",          "payload": {}},
        "SET_POWER_LIMIT": {"command_type": "update_device_spec", "payload": {}},
    }

    def _translate_action(action: str) -> dict:
        return _ACTION_MAP.get(action, {"command_type": action.lower(), "payload": {}})

    # control_history row → 프론트 ControlResult DTO.
    # row schema: (command_id, site_id, device_id, resource_type,
    #              command_type, payload, reason, issued_by, ack_status, time)
    def _row_to_control_result(r) -> dict:
        payload_dict = r[5] if isinstance(r[5], dict) else json.loads(r[5] or "{}")
        return {
            "command_id": str(r[0]),
            "status": (r[8] or "").upper(),
            "site_id": r[1],
            "target_resource_id": r[2],
            "action": _action_from_db(r[4], payload_dict),
            "created_at": r[9].isoformat() if r[9] else None,
            "resource_type": r[3],
            "command_type": r[4],
            "payload": payload_dict,
            "reason": r[6],
            "issued_by": r[7],
        }

    # _ACTION_MAP 의 역방향 — DB 의 (command_type, payload) → 프론트 action enum.
    # 모드 의존이라 (command_type, mode) 키로 미세 매칭.
    def _action_from_db(command_type: str, payload: dict | None) -> str:
        ct = (command_type or "").lower()
        mode = ((payload or {}).get("mode") or "").lower() if isinstance(payload, dict) else ""
        if ct == "ess_mode":
            if mode == "charge":
                return "START_CHARGE"
            if mode == "discharge":
                return "START_DISCHARGE"
            if mode == "standby":
                return "STANDBY"
        elif ct == "start":
            return "START_GENERATOR"
        elif ct == "stop":
            return "STOP_GENERATOR"
        elif ct == "open":
            return "OPEN_SWITCH"
        elif ct == "close":
            return "CLOSE_SWITCH"
        elif ct == "load_shed":
            ratio = (payload or {}).get("reduction_ratio") if isinstance(payload, dict) else None
            return "RESTORE_LOAD" if ratio == 0 else "SHED_LOAD"
        elif ct == "update_device_spec":
            return "SET_POWER_LIMIT"
        return ct.upper()

    # ── Blueprint & Routes ────────────────────────────────────────────────────

    blp = Blueprint("control", "control", url_prefix="/api/control")

    @blp.route("/operator-commands")
    class OperatorCommandResource(MethodView):
        @blp.arguments(OperatorCommandRequestSchema)
        @blp.response(202, CommandAcceptedResponseSchema)
        def post(self, payload):
            command_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            translated = _translate_action(payload["action"])

            # control_history INSERT 는 db-writer 에 위임 — mg:db:write 로 stream publish.
            # (DB Writer 단일 게이트 정책: control 은 직접 INSERT 하지 않음)
            try:
                import redis as _redis_sync
                _r = _redis_sync.Redis(
                    host=REDIS_HOST, port=REDIS_PORT,
                    password=REDIS_PASSWORD, socket_connect_timeout=2,
                )
                _envelope = {
                    "kind": "command",
                    "command_id": command_id,
                    "site_id": payload["site_id"],
                    "edge_id": payload.get("edge_id"),
                    "device_id": payload["device_id"],
                    "resource_type": payload["resource_type"].upper(),
                    "command_type": translated["command_type"],
                    "payload": translated["payload"],
                    "reason": payload.get("reason", ""),
                    "issued_by": payload["requested_by"],
                    "ack_status": "PENDING",
                    "timestamp": now.isoformat(),
                }
                _envelope = {k: v for k, v in _envelope.items() if v is not None}
                _r.xadd("mg:db:write", {"data": json.dumps(_envelope, ensure_ascii=False)})
                _r.close()
            except Exception as e:
                print(f"[control][operator] control_history publish 실패: {e}")

            # MQTT로 실제 장치에 명령 전송
            resource_type = payload["resource_type"].lower()
            device_id = payload["device_id"]
            topic = f"{SITE_ID}/{resource_type}/{device_id}/command"
            mqtt_payload = json.dumps({
                "command_id": command_id,
                **_translate_action(payload["action"]),
                "source": "operator",
                "expires_in_sec": 30,
                "force": True,
            }, ensure_ascii=False)
            try:
                client = _get_operator_mqtt()
                client.publish(topic, mqtt_payload)
                print(f"[control][operator] → {topic} | {payload['action']} | by {payload['requested_by']}")
                # ACK 추적 + cooldown 등록 + dead-band 캐시 초기화
                _shared_pending_acks[command_id] = (_time.monotonic(), device_id, resource_type)
                _device_cooldown[device_id] = _time.monotonic()
                _device_last_ess_cmd.pop(device_id, None)
                # desired_state Redis 저장 (rule 경로와 동일하게 폐루프 추적 가능하도록)
                try:
                    import redis as _redis_sync
                    _r = _redis_sync.Redis(
                        host=REDIS_HOST, port=REDIS_PORT,
                        password=REDIS_PASSWORD, socket_connect_timeout=2,
                    )
                    translated = _translate_action(payload["action"])
                    desired_value = json.dumps({
                            "command_id": command_id,
                            "command_type": translated["command_type"],
                            "payload": translated["payload"],
                            "issued_by": payload["requested_by"],
                            "issued_at": _time.time(),
                        }, ensure_ascii=False)
                    if payload.get("edge_id") and payload["edge_id"] != device_id:
                        _r.set(
                            f"desired:{SITE_ID}:{payload['edge_id']}:{device_id}",
                            desired_value,
                            ex=43200,
                        )
                    _r.set(
                        f"desired:{SITE_ID}:{device_id}",
                        desired_value,
                        ex=43200,
                    )
                    _r.close()
                except Exception as e:
                    print(f"[control][operator] desired_state 저장 실패: {e}")
            except Exception as e:
                print(f"[control][operator] MQTT 전송 실패: {e}")

            return {
                "command_id": command_id,
                "status": "ACCEPTED",
                "site_id": payload["site_id"],
                "edge_id": payload.get("edge_id"),
                "device_id": payload["device_id"],
                "action": payload["action"],
                "created_at": now,
            }

    # ── AI 추천 승인/거부 (미구현 → 503) ───────────────────────────────────────

    def _ai_unavailable():
        return jsonify({
            "error_code": "FEATURE_UNAVAILABLE",
            "message": "AI 서비스가 아직 활성화되지 않았습니다.",
            "trace_id": str(uuid.uuid4()),
            "details": {},
        }), 503

    @blp.route("/recommendations/<string:recommendation_id>/approve")
    class RecommendationApproveResource(MethodView):
        @blp.arguments(RecommendationDecisionSchema)
        def post(self, payload, recommendation_id):
            """AI 추천 승인 — 미구현 (AI 서비스 비활성화 상태)."""
            return _ai_unavailable()

    @blp.route("/recommendations/<string:recommendation_id>/reject")
    class RecommendationRejectResource(MethodView):
        @blp.arguments(RecommendationDecisionSchema)
        def post(self, payload, recommendation_id):
            """AI 추천 거부 — 미구현 (AI 서비스 비활성화 상태)."""
            return _ai_unavailable()

    @blp.route("/commands")
    class CommandListResource(MethodView):
        @blp.response(200, CommandHistorySchema(many=True))
        def get(self):
            """명령 이력 조회.

            쿼리 파라미터 (모두 옵션):
              - site_id: 특정 plant 필터 (멀티 plant 지원)
              - device_id: 특정 디바이스 필터
              - issued_by: 발행자 필터 (예: operator-01, rule)
              - page: 페이지 번호 1-based (기본 1)
              - page_size: 페이지 크기 (기본 50, 최대 1000)

            정렬: time DESC.
            """
            site_id = request.args.get("site_id")
            device_id = request.args.get("device_id")
            issued_by = request.args.get("issued_by")
            page_size = min(int(request.args.get("page_size", 50)), 1000)
            page = max(int(request.args.get("page", 1)), 1)
            offset = (page - 1) * page_size

            filters: list[str] = []
            params: list = []
            if site_id:
                filters.append("site_id = %s")
                params.append(site_id)
            if device_id:
                filters.append("device_id = %s")
                params.append(device_id)
            if issued_by:
                filters.append("issued_by = %s")
                params.append(issued_by)
            where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

            # control_history 는 TimescaleDB 시계열 — TS pool 사용.
            pool = get_ts_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT command_id, site_id, device_id, resource_type,
                               command_type, payload, reason, issued_by, ack_status, time
                        FROM control_history
                        {where_clause}
                        ORDER BY time DESC
                        LIMIT %s OFFSET %s
                        """,
                        (*params, page_size, offset),
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            return [_row_to_control_result(r) for r in rows]

    @blp.route("/commands/<command_id>")
    class CommandDetailResource(MethodView):
        @blp.response(200, CommandHistorySchema)
        def get(self, command_id):
            # control_history 는 TimescaleDB 시계열 — TS pool 사용.
            pool = get_ts_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT command_id, site_id, device_id, resource_type,
                               command_type, payload, reason, issued_by, ack_status, time
                        FROM control_history
                        WHERE command_id = %s
                        """,
                        (command_id,),
                    )
                    r = cur.fetchone()
            finally:
                pool.putconn(conn)

            if not r:
                abort(404)

            return _row_to_control_result(r)

    # ── Policy Routes ─────────────────────────────────────────────────────────

    @blp.route("/policies")
    class PolicyListResource(MethodView):
        @blp.response(200, PolicySchema(many=True))
        def get(self):
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT key, value, unit, description, updated_at, updated_by "
                        "FROM control_policy ORDER BY key"
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)
            return [
                {"key": r[0], "value": r[1], "unit": r[2], "description": r[3],
                 "updated_at": r[4], "updated_by": r[5]}
                for r in rows
            ]

    @blp.route("/policies/<string:key>")
    class PolicyDetailResource(MethodView):
        @blp.response(200, PolicySchema)
        def get(self, key):
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT key, value, unit, description, updated_at, updated_by "
                        "FROM control_policy WHERE key = %s",
                        (key,),
                    )
                    r = cur.fetchone()
            finally:
                pool.putconn(conn)
            if not r:
                abort(404)
            return {"key": r[0], "value": r[1], "unit": r[2], "description": r[3],
                    "updated_at": r[4], "updated_by": r[5]}

        @blp.arguments(PolicyUpdateRequestSchema)
        @blp.response(200, PolicySchema)
        def patch(self, body, key):
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE control_policy SET value = %s, updated_by = %s, updated_at = NOW() "
                        "WHERE key = %s RETURNING key, value, unit, description, updated_at, updated_by",
                        (body["value"], body["updated_by"], key),
                    )
                    r = cur.fetchone()
                conn.commit()
            finally:
                pool.putconn(conn)
            if not r:
                abort(404)
            print(f"[control][policy] {key} = {body['value']} (by {body['updated_by']})")
            return {"key": r[0], "value": r[1], "unit": r[2], "description": r[3],
                    "updated_at": r[4], "updated_by": r[5]}

    @blp.route("/policies/<string:key>/history")
    class PolicyHistoryResource(MethodView):
        @blp.response(200, PolicyHistorySchema(many=True))
        def get(self, key):
            limit = min(int(request.args.get("limit", 20)), 100)
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, key, old_value, new_value, changed_at, changed_by "
                        "FROM control_policy_history WHERE key = %s "
                        "ORDER BY changed_at DESC LIMIT %s",
                        (key, limit),
                    )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)
            return [
                {"id": r[0], "key": r[1], "old_value": r[2], "new_value": r[3],
                 "changed_at": r[4], "changed_by": r[5]}
                for r in rows
            ]

    api.register_blueprint(blp)

    @app.route("/health")
    def health():
        errors = []
        # Redis 연결 확인
        try:
            import redis as _redis
            r = _redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                password=REDIS_PASSWORD, socket_connect_timeout=2,
            )
            r.ping()
            r.close()
        except Exception as e:
            errors.append(f"redis: {e}")
        # DB 연결 확인
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

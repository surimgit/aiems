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

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, MQTT_HOST, MQTT_PORT, SITE_ID, REDIS_HOST, REDIS_PORT

# operator 명령의 ACK 추적을 위해 asyncio 루프와 공유하는 pending dict
# command_id → (sent_at, device_id, resource_type)
import time as _time
_shared_pending_acks: dict[str, tuple[float, str, str]] = {}

# device_id → sent_at (cooldown 중인 장치 추적)
_COOLDOWN_SEC = 35.0  # ACK timeout(30s)보다 약간 길게
_device_cooldown: dict[str, float] = {}

# Operator 명령용 MQTT 싱글턴 — 매번 connect/disconnect 방지
_operator_mqtt: mqtt_client.Client | None = None


def _get_operator_mqtt() -> mqtt_client.Client:
    global _operator_mqtt
    if _operator_mqtt is None or not _operator_mqtt.is_connected():
        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()
        _operator_mqtt = client
    return _operator_mqtt


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["API_TITLE"] = "Control API"
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
    from adapters.state_reader import StateReader
    from adapters.mqtt_commander import MqttCommander
    from adapters.db_writer import ControlDBWriter
    from adapters.event_publisher import EventPublisher
    from adapters.policy_reader import PolicyReader
    from domain.rule_engine import run
    from config import CONTROL_INTERVAL_SECONDS

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

        if cmd["command_type"] == "ess_mode":
            requested_mode = cmd["payload"].get("mode", "standby")
            return current_mode != requested_mode

        if cmd["command_type"] == "diesel_command":
            action = cmd["payload"].get("action", "")
            if action == "start":
                return current_mode.lower() not in ("running",)
            if action == "stop":
                return current_mode.lower() not in ("stopped", "idle")

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
                            commands, events = await run(states, policy, event_pub)
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

    def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
        nonlocal _pool
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5,
                host=DB_HOST, port=DB_PORT,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            )
        return _pool

    # ── Schemas ───────────────────────────────────────────────────────────────

    class OperatorCommandRequestSchema(Schema):
        site_id = fields.String(required=True)
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
        device_id = fields.String()
        action = fields.String()
        created_at = fields.DateTime()

    class CommandHistorySchema(Schema):
        command_id = fields.String()
        site_id = fields.String()
        device_id = fields.String()
        resource_type = fields.String()
        command_type = fields.String()
        payload = fields.Dict()
        reason = fields.String()
        issued_by = fields.String()
        ack_status = fields.String()
        time = fields.DateTime()

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
        "RESTORE_LOAD":    {"command_type": "load_restore",   "payload": {}},
        "OPEN_SWITCH":     {"command_type": "open_switch",    "payload": {}},
        "CLOSE_SWITCH":    {"command_type": "close_switch",   "payload": {}},
        "SET_POWER_LIMIT": {"command_type": "update_device_spec", "payload": {}},
    }

    def _translate_action(action: str) -> dict:
        return _ACTION_MAP.get(action, {"command_type": action.lower(), "payload": {}})

    # ── Blueprint & Routes ────────────────────────────────────────────────────

    blp = Blueprint("control", "control", url_prefix="/api/control")

    @blp.route("/operator-commands")
    class OperatorCommandResource(MethodView):
        @blp.arguments(OperatorCommandRequestSchema)
        @blp.response(202, CommandAcceptedResponseSchema)
        def post(self, payload):
            command_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            pool = get_pool()
            conn = pool.getconn()
            try:
                translated = _translate_action(payload["action"])
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO control_history
                            (time, command_id, site_id, device_id, resource_type,
                             command_type, payload, reason, issued_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            now,
                            command_id,
                            payload["site_id"],
                            payload["device_id"],
                            payload["resource_type"].upper(),
                            translated["command_type"],
                            json.dumps(translated["payload"]),
                            payload.get("reason", ""),
                            payload["requested_by"],
                        ),
                    )
                conn.commit()
            finally:
                pool.putconn(conn)

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
                # ACK 추적 + cooldown 등록
                _shared_pending_acks[command_id] = (_time.monotonic(), device_id, resource_type)
                _device_cooldown[device_id] = _time.monotonic()
            except Exception as e:
                print(f"[control][operator] MQTT 전송 실패: {e}")

            return {
                "command_id": command_id,
                "status": "ACCEPTED",
                "site_id": payload["site_id"],
                "device_id": payload["device_id"],
                "action": payload["action"],
                "created_at": now,
            }

    @blp.route("/commands")
    class CommandListResource(MethodView):
        @blp.response(200, CommandHistorySchema(many=True))
        def get(self):
            device_id = request.args.get("device_id")
            limit = min(int(request.args.get("limit", 100)), 1000)
            pool = get_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    if device_id:
                        cur.execute(
                            """
                            SELECT command_id, site_id, device_id, resource_type,
                                   command_type, payload, reason, issued_by, ack_status, time
                            FROM control_history
                            WHERE device_id = %s
                            ORDER BY time DESC LIMIT %s
                            """,
                            (device_id, limit),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT command_id, site_id, device_id, resource_type,
                                   command_type, payload, reason, issued_by, ack_status, time
                            FROM control_history
                            ORDER BY time DESC LIMIT %s
                            """,
                            (limit,),
                        )
                    rows = cur.fetchall()
            finally:
                pool.putconn(conn)

            return [
                {
                    "command_id": str(r[0]),
                    "site_id": r[1],
                    "device_id": r[2],
                    "resource_type": r[3],
                    "command_type": r[4],
                    "payload": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                    "reason": r[6],
                    "issued_by": r[7],
                    "ack_status": r[8],
                    "time": r[9],
                }
                for r in rows
            ]

    @blp.route("/commands/<command_id>")
    class CommandDetailResource(MethodView):
        @blp.response(200, CommandHistorySchema)
        def get(self, command_id):
            pool = get_pool()
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

            return {
                "command_id": str(r[0]),
                "site_id": r[1],
                "device_id": r[2],
                "resource_type": r[3],
                "command_type": r[4],
                "payload": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                "reason": r[6],
                "issued_by": r[7],
                "ack_status": r[8],
                "time": r[9],
            }

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
            r = _redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=2)
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

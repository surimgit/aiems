import json
from datetime import datetime, timedelta, timezone

import psycopg2.pool
import redis
from flask import Flask, abort, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields
from prometheus_flask_exporter import PrometheusMetrics

from .config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    CONTROL_DB_HOST, CONTROL_DB_PORT, CONTROL_DB_NAME,
    CONTROL_DB_USER, CONTROL_DB_PASSWORD,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, SITE_ID,
    SIMULATOR_TOPOLOGY_URL,
    LOCAL_SIM_TOPOLOGY_MQTT_ENABLED,
)
from .extensions import socketio

_KNOWN_SITES = [SITE_ID]
_LOCAL_TOPOLOGY_CACHE_PREFIX = "ems:topology:"
_KST = timezone(timedelta(hours=9), "Asia/Seoul")
_SOLAR_SAVINGS_PERIODS = {"today", "month"}

# 실제 한전 계약종별/계절/시간대별 단가를 확정하면 여기만 바꾼다.
SOLAR_SAVINGS_TARIFF_WON_PER_KWH = 150.0
SOLAR_SAVINGS_TARIFF_BASIS = "한전 전력량요금 단가 기준"


def _fetch_simulator_topology(timeout_sec: float = 1.5) -> dict | None:
    """simulator/topology 의 GET /api/topology 를 호출. 실패 시 None.

    설계문서 §3 기준 토폴로지 master 는 simulator/topology 서비스다.
    EMS 가 응답을 만들 때 control_db (메타데이터) 와 이 응답 (런타임 라인) 을 합친다.
    """
    try:
        import requests
        resp = requests.get(f"{SIMULATOR_TOPOLOGY_URL}/api/topology", timeout=timeout_sec)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[state-processor][topology] simulator 응답 실패 (DB 만 사용): {e}")
        return None


def _apply_live_state_to_topology(topology: dict, states: list[dict]) -> dict:
    out = json.loads(json.dumps(topology))
    state_by_device = {s.get("device_id"): s for s in states if s.get("device_id")}
    state_by_switch = {
        s.get("device_id"): s for s in states
        if (s.get("resource_type") or "").upper() == "SWITCH"
    }

    def _node_status(device_id: str | None) -> str:
        if not device_id:
            return "NORMAL"
        s = state_by_device.get(device_id) or {}
        if s.get("emergency"):
            return "EMERGENCY"
        if (s.get("comms_health") or "") == "stale":
            return "WARNING"
        return "NORMAL"

    node_device_map = {}
    for node in out.get("nodes", []) or []:
        resource_id = node.get("resource_id")
        node_device_map[node.get("node_id")] = resource_id
        node["status"] = _node_status(resource_id)
        node.setdefault("position", {"x": 0.0, "y": 0.0})

    switches_by_line: dict[str, list[dict]] = {}
    for sw in out.get("switches", []) or []:
        switch_id = sw.get("switch_id")
        if switch_id:
            live = state_by_switch.get(switch_id) or {}
            reported = live.get("reported_state") or {}
            if reported.get("switch_state"):
                sw["position"] = reported["switch_state"]
            if reported.get("interlock_blocked") is not None:
                sw["interlock_blocked"] = bool(reported.get("interlock_blocked"))
        if sw.get("line_id"):
            switches_by_line.setdefault(sw["line_id"], []).append(sw)

    def _line_flow_kw(from_node_id: str) -> float:
        dev_id = node_device_map.get(from_node_id)
        if not dev_id:
            return 0.0
        s = state_by_device.get(dev_id) or {}
        p = (s.get("reported_state") or {}).get("P")
        return float(p) if p is not None else 0.0

    def _direction(flow_kw: float) -> str:
        if flow_kw > 0.01:
            return "FORWARD"
        if flow_kw < -0.01:
            return "REVERSE"
        return "BIDIRECTIONAL"

    for line in out.get("lines", []) or []:
        flow = _line_flow_kw(line.get("from_node_id"))
        line["flow_kw"] = round(flow, 2)
        line["direction"] = _direction(flow)
        sws = switches_by_line.get(line.get("line_id") or "", [])
        if any((sw.get("position") or "").upper() == "OPEN" for sw in sws):
            line["status"] = "OPEN"
        else:
            line["status"] = (line.get("status") or "NORMAL").upper()

    return out


def _get_local_topology_from_redis(redis_client: redis.Redis, site_id: str) -> dict | None:
    raw = redis_client.get(f"{_LOCAL_TOPOLOGY_CACHE_PREFIX}{site_id}")
    if not raw:
        return None
    try:
        entry = json.loads(raw)
    except Exception:
        return None
    topology = entry.get("topology")
    if not isinstance(topology, dict):
        return None
    return topology

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
        "edge_id": state.get("edge_id"),
        "resource_type": rt,
        "name": state.get("device_id"),
        "status": status,
        "comms_health": comms,
        "location": state.get("location"),
        "site_metadata": state.get("site_metadata"),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
    }
    for key in ("capacity_kw", "installed_capacity_kw", "rated_power_kw", "rated_capacity_kw", "max_power_kw", "power_limit_kw"):
        if reported.get(key) is not None:
            out[key] = reported.get(key)

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
        "edge_id": state.get("edge_id"),
        "name": state.get("device_id"),
        "capacity_kwh": reported.get("capacity_kwh") or 0.0,
        "max_power_kw": reported.get("power_limit_kw") or 0.0,
        "soc": reported.get("SOC") or 0.0,
        "soh": reported.get("SOH"),
        "status": status,
        "power_kw": p,
        "location": state.get("location"),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
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


def _parse_solar_savings_period(raw: str | None) -> str:
    period = (raw or "month").lower()
    if period not in _SOLAR_SAVINGS_PERIODS:
        abort(400, "period must be one of: today, month")
    return period


def _solar_savings_window(period: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    end_at = (now or datetime.now(_KST)).astimezone(_KST)
    if period == "today":
        start_at = end_at.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_at = end_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_at, end_at


def _build_solar_savings_payload(
    site_id: str,
    period: str,
    start_at: datetime,
    end_at: datetime,
    solar_generation_kwh: float,
    load_consumption_kwh: float,
) -> dict:
    avoided_grid_kwh = min(solar_generation_kwh, load_consumption_kwh) if load_consumption_kwh > 0 else solar_generation_kwh
    savings_won = avoided_grid_kwh * SOLAR_SAVINGS_TARIFF_WON_PER_KWH
    self_use_ratio_pct = (avoided_grid_kwh / solar_generation_kwh * 100.0) if solar_generation_kwh > 0 else 0.0
    return {
        "site_id": site_id,
        "period": period,
        "from": start_at.isoformat(),
        "to": end_at.isoformat(),
        "solar_generation_kwh": round(solar_generation_kwh, 3),
        "avoided_grid_kwh": round(avoided_grid_kwh, 3),
        "savings_won": round(savings_won),
        "avg_tariff_won_per_kwh": SOLAR_SAVINGS_TARIFF_WON_PER_KWH,
        "self_use_ratio_pct": round(self_use_ratio_pct, 2),
        "tariff_basis": SOLAR_SAVINGS_TARIFF_BASIS,
        "updated_at": end_at.isoformat(),
    }


def create_app() -> Flask:
    app = Flask(__name__)
    socketio.init_app(app)
    from . import realtime  # noqa: F401  # Socket.IO event handlers registration.
    PrometheusMetrics(app, group_by="endpoint")
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
        # S305 §3: INVALID_REQUEST — 요청 형식 또는 필수 필드 오류
        return _err("INVALID_REQUEST", getattr(e, "description", str(e)), status=400)

    @app.errorhandler(404)
    def _h404(e):
        return _err("NOT_FOUND", getattr(e, "description", str(e)), status=404)

    @app.errorhandler(405)
    def _h405(e):
        # S305 §3: METHOD_NOT_ALLOWED (§4: 405 추가됨)
        return _err("METHOD_NOT_ALLOWED", getattr(e, "description", str(e)), status=405)

    @app.errorhandler(409)
    def _h409(e):
        # S305 §3: CONFLICT — 현재 상태와 요청 충돌 (TimescaleDB 압축 chunk ack 거부 포함)
        return _err("CONFLICT", getattr(e, "description", str(e)), status=409)

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

    class SolarSavingsPerformanceSchema(Schema):
        site_id = fields.String()
        period = fields.String()
        from_time = fields.String(data_key="from", attribute="from")
        to = fields.String()
        solar_generation_kwh = fields.Float()
        avoided_grid_kwh = fields.Float()
        savings_won = fields.Float()
        avg_tariff_won_per_kwh = fields.Float()
        self_use_ratio_pct = fields.Float()
        tariff_basis = fields.String(allow_none=True)
        updated_at = fields.String(allow_none=True)

    class EssStatusSchema(Schema):
        ess_id = fields.String()
        edge_id = fields.String(allow_none=True)
        name = fields.String(allow_none=True)
        capacity_kwh = fields.Float()
        max_power_kw = fields.Float()
        soc = fields.Float()
        soh = fields.Float(allow_none=True)
        status = fields.String()  # 'idle' / 'charging' / 'discharging' / 'fault'
        power_kw = fields.Float(allow_none=True)
        location = fields.Dict(allow_none=True)
        latitude = fields.Float(allow_none=True)
        longitude = fields.Float(allow_none=True)
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
        edge_id = fields.String(allow_none=True)
        site_id = fields.String()
        resource_type = fields.String()
        timestamp = fields.String()
        location = fields.Dict(allow_none=True)
        latitude = fields.Float(allow_none=True)
        longitude = fields.Float(allow_none=True)
        P = fields.Float(allow_none=True)
        SOC = fields.Float(allow_none=True)
        operating_mode = fields.String(allow_none=True)
        comms_health = fields.String(allow_none=True)
        emergency = fields.Boolean()
        interlock = fields.Boolean()
        telemetry_window = fields.Dict(allow_none=True)
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
    #       device_id (범용 장치 ID), device_id→ess_id (옵션 — ESS device 일 때만 의미).
    class AlarmSchema(Schema):
        alarm_id = fields.String(allow_none=True)
        level = fields.String()  # 'info' / 'warning' / 'critical'
        code = fields.String()
        message = fields.String(allow_none=True)
        device_id = fields.String(allow_none=True)
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
        edge_id = fields.String(allow_none=True)
        resource_type = fields.String()
        name = fields.String(allow_none=True)
        status = fields.String(allow_none=True)
        comms_health = fields.String(allow_none=True)
        location = fields.Dict(allow_none=True)
        site_metadata = fields.Dict(allow_none=True)
        latitude = fields.Float(allow_none=True)
        longitude = fields.Float(allow_none=True)
        capacity_kw = fields.Float(allow_none=True)
        installed_capacity_kw = fields.Float(allow_none=True)
        rated_power_kw = fields.Float(allow_none=True)
        rated_capacity_kw = fields.Float(allow_none=True)
        max_power_kw = fields.Float(allow_none=True)
        power_limit_kw = fields.Float(allow_none=True)
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
            "device_id": row[3],
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
                        abort(409, "압축된 오래된 알람(30일 이상)은 ack 할 수 없습니다.")
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

    @blp.route("/plants/<string:site_id>/performance/solar-savings")
    class PlantSolarSavingsPerformanceResource(MethodView):
        @blp.response(200, SolarSavingsPerformanceSchema)
        def get(self, site_id):
            """실제 태양광 발전량 기반 한전 구매 대체 성과.

            sensor_data 의 SOLAR p_avg(kW)를 1초 집계 row 기준으로 적분해 kWh 를 계산한다.
            LOAD 데이터가 있으면 구매 대체량은 min(태양광 발전량, 부하 사용량) 으로 제한한다.
            """
            period = _parse_solar_savings_period(request.args.get("period"))
            start_at, end_at = _solar_savings_window(period)

            pool = get_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            COALESCE(
                                SUM(
                                    CASE
                                        WHEN resource_type IN ('SOLAR', 'PV') AND p_avg IS NOT NULL
                                            THEN GREATEST(p_avg, 0)
                                        ELSE 0
                                    END
                                ) / 3600.0,
                                0.0
                            ) AS solar_generation_kwh,
                            COALESCE(
                                SUM(
                                    CASE
                                        WHEN resource_type = 'LOAD' AND p_avg IS NOT NULL
                                            THEN ABS(p_avg)
                                        ELSE 0
                                    END
                                ) / 3600.0,
                                0.0
                            ) AS load_consumption_kwh
                        FROM sensor_data
                        WHERE site_id = %s
                          AND time >= %s
                          AND time < %s
                          AND resource_type IN ('SOLAR', 'PV', 'LOAD')
                        """,
                        (site_id, start_at, end_at),
                    )
                    row = cur.fetchone()
            finally:
                pool.putconn(conn)

            solar_generation_kwh = float(row[0] or 0.0) if row else 0.0
            load_consumption_kwh = float(row[1] or 0.0) if row else 0.0
            return _build_solar_savings_payload(
                site_id,
                period,
                start_at,
                end_at,
                solar_generation_kwh,
                load_consumption_kwh,
            )

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
                    "edge_id": s.get("edge_id"),
                    "site_id": s.get("site_id"),
                    "resource_type": s.get("resource_type"),
                    "timestamp": s.get("calculated_at") or s.get("timestamp"),
                    "location": s.get("location"),
                    "latitude": s.get("latitude"),
                    "longitude": s.get("longitude"),
                    "P": (s.get("reported_state") or {}).get("P"),
                    "SOC": (s.get("reported_state") or {}).get("SOC"),
                    "operating_mode": (s.get("reported_state") or {}).get("operating_mode"),
                    "comms_health": s.get("comms_health"),
                    "emergency": s.get("emergency", False),
                    "interlock": s.get("interlock", False),
                    "telemetry_window": s.get("telemetry_window"),
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
            states = _get_site_states(site_id)
            if LOCAL_SIM_TOPOLOGY_MQTT_ENABLED:
                cached = _get_local_topology_from_redis(get_redis(), site_id)
                if cached is None:
                    return {
                        "site_id": site_id,
                        "nodes": [],
                        "lines": [],
                        "switches": [],
                    }
                return _apply_live_state_to_topology(cached, states)

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

            # ── simulator topology 융합 (설계문서 §3 master) ─────────────────
            # 운영자가 simulator UI 또는 API 로 추가한 라인/스위치/노드를 흡수.
            # control_db 에 없는 자원이 있으면 추가, 있는 자원은 EMS DB 메타데이터 우선 유지.
            sim_topo = _fetch_simulator_topology()
            if sim_topo:
                existing_node_ids = {n["node_id"] for n in nodes}
                existing_line_ids = {l["line_id"] for l in lines}
                existing_switch_ids = {s["switch_id"] for s in switches}

                # simulator-only 노드 추가 (좌표는 simulator 응답에 없으면 0,0)
                for n in sim_topo.get("nodes", []) or []:
                    nid = n.get("node_id")
                    if not nid or nid in existing_node_ids:
                        continue
                    pos = n.get("position") or {}
                    nodes.append({
                        "node_id": nid,
                        "node_type": (n.get("node_type") or "BUS"),
                        "resource_id": n.get("resource_id"),
                        "position": {
                            "x": float(pos.get("x") or 0.0),
                            "y": float(pos.get("y") or 0.0),
                        },
                        "status": _node_status(n.get("resource_id")),
                    })
                    existing_node_ids.add(nid)

                # simulator-only 라인 + 그 안의 스위치 추가
                for l in sim_topo.get("lines", []) or []:
                    lid = l.get("line_id")
                    if not lid:
                        continue
                    sw = l.get("switch") or {}
                    sw_id = sw.get("switch_id")
                    if lid not in existing_line_ids:
                        flow = _line_flow_kw(l.get("from_node_id"))
                        # status 산출 시 우리 _line_status 는 sw_by_line 만 보니까,
                        # simulator-only 라인은 simulator 의 switch position 으로 직접 판정.
                        if sw_id:
                            live_state = state_by_switch.get(sw_id, {})
                            live_pos = (live_state.get("reported_state") or {}).get("switch_state")
                            sim_pos = (sw.get("position") or "").upper()
                            pos_for_status = live_pos or sim_pos
                            line_status = "OPEN" if pos_for_status == "OPEN" else (
                                "NORMAL" if pos_for_status == "CLOSED" else "UNKNOWN"
                            )
                        else:
                            line_status = (l.get("status") or "NORMAL").upper()
                        lines.append({
                            "line_id": lid,
                            "from_node_id": l.get("from_node_id"),
                            "to_node_id": l.get("to_node_id"),
                            "direction": _direction(flow),
                            "flow_kw": round(flow, 2),
                            "status": line_status,
                        })
                        existing_line_ids.add(lid)
                    # 스위치도 — simulator-only 라인이 아니어도 스위치는 추가될 수 있음
                    if sw_id and sw_id not in existing_switch_ids:
                        live_state = state_by_switch.get(sw_id, {})
                        reported = live_state.get("reported_state") or {}
                        sim_pos = (sw.get("position") or "").upper()
                        position = reported.get("switch_state") or sim_pos or "UNKNOWN"
                        switches.append({
                            "switch_id": sw_id,
                            "line_id": lid,
                            "position": position,
                            "controllable": bool(sw.get("controllable", True)),
                            "interlock_blocked": bool(
                                reported.get("interlock_blocked", sw.get("interlock_blocked", False))
                            ),
                        })
                        existing_switch_ids.add(sw_id)

            return {
                "site_id": site_id,
                "nodes": nodes,
                "lines": lines,
                "switches": switches,
            }

    # ── Topology CRUD (task_022 방안 A) ────────────────────────────────────────
    # control_db 에 직접 INSERT/DELETE 하여 dev 서버 EMS 토폴로지를 변경한다.
    # nginx 는 /api/plants/ 를 모든 HTTP method 허용하여 프록시하므로 추가 설정 불필요.

    @blp.route("/plants/<string:site_id>/topology/nodes")
    class PlantTopologyNodeListResource(MethodView):
        def post(self, site_id):
            """토폴로지 노드 생성 — control_db.topology_nodes INSERT."""
            if site_id not in _KNOWN_SITES:
                return jsonify({"error": "site not found"}), 404
            body = request.get_json(force=True) or {}
            node_id = (body.get("node_id") or "").strip()
            node_type = (body.get("node_type") or "").strip().upper()
            device_id = (body.get("device_id") or body.get("edge_id") or "").strip() or None
            label = (body.get("label") or node_id).strip()
            x = float(body.get("x") or 0.0)
            y = float(body.get("y") or 0.0)

            if not node_id:
                return jsonify({"error": "node_id is required"}), 400
            if node_type not in ("GENERATION", "STORAGE", "LOAD", "BUS", "GRID"):
                return jsonify({"error": "node_type must be GENERATION/STORAGE/LOAD/BUS/GRID"}), 400

            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO topology_nodes (site_id, node_id, node_type, device_id, label, x, y)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (site_id, node_id) DO UPDATE
                            SET node_type = EXCLUDED.node_type,
                                device_id = EXCLUDED.device_id,
                                label     = EXCLUDED.label,
                                x         = EXCLUDED.x,
                                y         = EXCLUDED.y
                        """,
                        (site_id, node_id, node_type, device_id, label, x, y),
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                pool.putconn(conn)

            return jsonify({"node_id": node_id, "status": "created"}), 201

    @blp.route("/plants/<string:site_id>/topology/nodes/<string:node_id>")
    class PlantTopologyNodeResource(MethodView):
        def delete(self, site_id, node_id):
            """토폴로지 노드 삭제 — 연결된 라인/스위치도 cascade 삭제."""
            if site_id not in _KNOWN_SITES:
                return jsonify({"error": "site not found"}), 404

            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    # 연결된 라인 조회 (cascade 용)
                    cur.execute(
                        """
                        SELECT line_id FROM topology_lines
                        WHERE site_id = %s AND (from_node_id = %s OR to_node_id = %s)
                        """,
                        (site_id, node_id, node_id),
                    )
                    line_ids = [r[0] for r in cur.fetchall()]

                    # 연결된 스위치 삭제
                    if line_ids:
                        cur.execute(
                            "DELETE FROM topology_switches WHERE site_id = %s AND line_id = ANY(%s)",
                            (site_id, line_ids),
                        )
                    # 라인 삭제
                    cur.execute(
                        "DELETE FROM topology_lines WHERE site_id = %s AND (from_node_id = %s OR to_node_id = %s)",
                        (site_id, node_id, node_id),
                    )
                    # 노드 삭제
                    cur.execute(
                        "DELETE FROM topology_nodes WHERE site_id = %s AND node_id = %s",
                        (site_id, node_id),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        return jsonify({"error": f"node '{node_id}' not found"}), 404
                conn.commit()
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                pool.putconn(conn)

            return jsonify({"node_id": node_id, "status": "deleted", "removed_lines": line_ids}), 200

    @blp.route("/plants/<string:site_id>/topology/lines")
    class PlantTopologyLineListResource(MethodView):
        def post(self, site_id):
            """토폴로지 라인 + 스위치 생성 — control_db INSERT."""
            if site_id not in _KNOWN_SITES:
                return jsonify({"error": "site not found"}), 404
            body = request.get_json(force=True) or {}
            line_id = (body.get("line_id") or "").strip()
            from_node_id = (body.get("from_node_id") or "").strip()
            to_node_id = (body.get("to_node_id") or "").strip()
            rating_kw = float(body.get("rating_kw") or 0.0)

            if not line_id or not from_node_id or not to_node_id:
                return jsonify({"error": "line_id, from_node_id, to_node_id are required"}), 400

            # 스위치 정보 (없으면 기본값)
            sw = body.get("switch") or {}
            switch_id = (sw.get("switch_id") or f"sw-{line_id}").strip()
            switch_type = (sw.get("switch_type") or "CB").strip()
            is_closed = bool(sw.get("is_closed", True))
            controllable = bool(sw.get("controllable", True))

            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO topology_lines (site_id, line_id, from_node_id, to_node_id, rating_kw)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (site_id, line_id) DO NOTHING
                        """,
                        (site_id, line_id, from_node_id, to_node_id, rating_kw),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        return jsonify({"error": f"line '{line_id}' already exists"}), 409

                    cur.execute(
                        """
                        INSERT INTO topology_switches (site_id, switch_id, line_id, switch_type, is_closed, controllable)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (site_id, switch_id) DO NOTHING
                        """,
                        (site_id, switch_id, line_id, switch_type, is_closed, controllable),
                    )
                conn.commit()
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                pool.putconn(conn)

            return jsonify({"line_id": line_id, "switch_id": switch_id, "status": "created"}), 201

    @blp.route("/plants/<string:site_id>/topology/lines/<string:line_id>")
    class PlantTopologyLineResource(MethodView):
        def delete(self, site_id, line_id):
            """토폴로지 라인 삭제 — 연결된 스위치도 함께 삭제."""
            if site_id not in _KNOWN_SITES:
                return jsonify({"error": "site not found"}), 404

            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM topology_switches WHERE site_id = %s AND line_id = %s",
                        (site_id, line_id),
                    )
                    cur.execute(
                        "DELETE FROM topology_lines WHERE site_id = %s AND line_id = %s",
                        (site_id, line_id),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        return jsonify({"error": f"line '{line_id}' not found"}), 404
                conn.commit()
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                pool.putconn(conn)

            return jsonify({"line_id": line_id, "status": "deleted"}), 200

        def patch(self, site_id, line_id):
            """토폴로지 라인 스위치 상태 변경 — is_closed UPDATE."""
            if site_id not in _KNOWN_SITES:
                return jsonify({"error": "site not found"}), 404
            body = request.get_json(force=True) or {}
            is_closed = body.get("is_closed")
            if is_closed is None:
                return jsonify({"error": "is_closed is required"}), 400

            pool = get_control_db_pool()
            conn = pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE topology_switches SET is_closed = %s WHERE site_id = %s AND line_id = %s",
                        (bool(is_closed), site_id, line_id),
                    )
                    if cur.rowcount == 0:
                        conn.rollback()
                        return jsonify({"error": f"line '{line_id}' not found"}), 404
                conn.commit()
            except Exception as e:
                conn.rollback()
                return jsonify({"error": str(e)}), 500
            finally:
                pool.putconn(conn)

            return jsonify({"line_id": line_id, "is_closed": bool(is_closed), "status": "updated"}), 200

    # ── 이벤트 로그 ────────────────────────────────────────────────────────────

    @blp.route("/plants/<string:site_id>/events")
    class PlantEventResource(MethodView):
        @blp.response(200, EventLogSchema(many=True))
        def get(self, site_id):
            """Plant 이벤트 로그 조회 — 프론트 EventDto 형식.

            쿼리 파라미터 (모두 옵션):
              - device_id: 특정 디바이스 필터
              - severity: INFO/WARNING/ALARM/EMERGENCY
              - limit: 기본 100, 최대 1000
            """
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
            """알람 목록 조회 — WARNING 이상 이벤트. 프론트 AlarmData DTO 형식.

            쿼리 파라미터 (모두 옵션):
              - acknowledged: true/false/미입력=전체
              - severity: WARNING/CRITICAL/EMERGENCY
              - limit: 기본 100, 최대 1000
            """
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

    @blp.route("/plants/<string:site_id>/alarms/<string:alarm_id>/ack")
    class PlantAlarmAckResource(MethodView):
        @blp.arguments(AlarmAckRequestSchema)
        @blp.response(200, AlarmSchema)
        def post(self, body, site_id, alarm_id):
            """알람 확인 처리 (S305 표준 경로).

            event_log 는 TimescaleDB hypertable 이며 30일 이후 chunk 가 압축됨.
            압축 chunk 는 UPDATE 가 거부되므로 30일 지난 알람은 ack 불가 → 409 Conflict.
            """
            return _ack_alarm(site_id, alarm_id, body.get("acked_by") or "operator")

    # ── AI 관련 미구현 엔드포인트 (→ 503) ───────────────────────────────────
    # 아래 3개 엔드포인트는 AI 서비스 활성화 전까지 503 FEATURE_UNAVAILABLE 로 응답.
    # 기술 부채: 향후 ai-service 구현 시 state-processor에서 제거 후 ai-service로 이관.
    # 참조: S305 dashboard-api.md §7, ai-api.md §3

    def _ai_unavailable():
        import uuid as _uuid
        return jsonify({
            "error_code": "FEATURE_UNAVAILABLE",
            "message": "AI 서비스가 아직 활성화되지 않았습니다.",
            "trace_id": str(_uuid.uuid4()),
            "details": {},
        }), 503

    @blp.route("/plants/<string:site_id>/ai/latest")
    class PlantAiLatestResource(MethodView):
        def get(self, site_id):
            """Plant AI 최신 결과 — 미구현 (AI 서비스 비활성화 상태).

            프론트엔드: GET /api/plants/{siteId}/ai/latest
            """
            return _ai_unavailable()

    @blp.route("/plants/<string:site_id>/forecasts")
    class PlantForecastResource(MethodView):
        def get(self, site_id):
            """예측 목록 — 미구현 (AI 서비스 비활성화 상태).

            프론트엔드: GET /api/plants/{siteId}/forecasts
            """
            return _ai_unavailable()

    @blp.route("/plants/<string:site_id>/recommendations")
    class PlantRecommendationResource(MethodView):
        def get(self, site_id):
            """권고 목록 — 미구현 (AI 서비스 비활성화 상태).

            프론트엔드: GET /api/plants/{siteId}/recommendations
            """
            return _ai_unavailable()

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

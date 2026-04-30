"""이상 감지 룰. 이벤트와 fail-safe 명령을 반환한다.

설계문서 §4.6 기준. 감지된 이상은 EventPublisher가 Redis stream에 발행한다.
STATE_TTL 초과 장치는 이벤트 발행과 함께 standby 명령도 반환한다.

알람 중복 발행 억제는 EventPublisher의 Redis 키(ems:alerted:*)로 처리한다.
프로세스 재시작 후에도 중복 발행하지 않는다.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PRIORITY = 100

_DEFICIT_THRESHOLD = 3
_DEFICIT_KW = -50.0

# Redis 키
_REDIS_DEFICIT_COUNT = "ems:safety:deficit_count"
_REDIS_PREV_LOAD_P = "ems:safety:prev_load_p:"
_REDIS_PREV_SOLAR_P = "ems:safety:prev_solar_p:"

# Load 이상 감지 임계값
_LOAD_SURGE_RATIO = 0.30     # 30% 이상 급증
_LOAD_OVERLOAD_KW = 200.0   # 과부하 절대값 (policy 미지원 시 기본값)

# Solar 이상 감지 임계값
_SOLAR_DROP_RATIO = 0.50     # 주간 50% 이상 급감
_SOLAR_DAYTIME_MIN_P = 1.0  # 주간 최소 발전량 기준 kW
_SOLAR_DAYTIME_HOURS = (6, 18)  # 주간 시간대 (현지 시간 기준)

# Diesel 엔진 이상 감지 임계값 (policy 미지원 시 기본값)
_DIESEL_COOLANT_TEMP_MAX_DEFAULT = 95.0   # °C
_DIESEL_RPM_NOMINAL = 1800.0
_DIESEL_RPM_TOLERANCE = 0.10              # ±10%


async def evaluate(flow: dict, states: dict, policy, event_pub) -> tuple[list[dict], list[dict]]:
    """(events, failsafe_commands) 튜플 반환.

    events: 이상 감지 이벤트 — EventPublisher가 Redis stream에 발행
    failsafe_commands: TTL 초과 장치에 대한 standby 강제 명령 — priority=100으로 자동 제어 override
    """
    from ...config import TIMEZONE
    redis = event_pub._redis
    events = []
    failsafe_commands = []
    now = datetime.now(timezone.utc)
    now_local = now.astimezone(ZoneInfo(TIMEZONE))

    soc_low = policy.get("SOC_LOW")
    soc_critical = policy.get("SOC_CRITICAL_LOW")
    fuel_low = policy.get("DIESEL_FUEL_LOW")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")
    state_ttl = policy.get("STATE_TTL")

    # ESS 이상 감지
    for ess in flow["ess_devices"]:
        soc = ess["SOC"]
        if soc is None:
            continue
        device_id = ess["device_id"]

        if soc <= soc_critical:
            key = f"{device_id}:EVT-E-001"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "ess", "EVT-E-001", "CRITICAL",
                    f"ESS SOC 긴급 하한 도달: {soc}% <= {soc_critical}%",
                    {"SOC": soc},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-E-001")

        if soc_critical < soc <= soc_low:
            key = f"{device_id}:EVT-N-001"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "ess", "EVT-N-001", "WARNING",
                    f"ESS SOC 하한 경고: {soc}% <= {soc_low}%",
                    {"SOC": soc},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-N-001")

    # Diesel 연료 이상 감지
    for diesel in flow["diesel_devices"]:
        fuel = diesel["fuel_percent"]
        if fuel is None:
            continue
        device_id = diesel["device_id"]

        if fuel <= fuel_critical:
            key = f"{device_id}:EVT-E-002"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "diesel", "EVT-E-002", "CRITICAL",
                    f"디젤 연료 긴급 하한 도달: {fuel}% <= {fuel_critical}%",
                    {"fuel_percent": fuel},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-E-002")

        if fuel_critical < fuel <= fuel_low:
            key = f"{device_id}:EVT-N-002"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "diesel", "EVT-N-002", "WARNING",
                    f"디젤 연료 부족 경고: {fuel}% <= {fuel_low}%",
                    {"fuel_percent": fuel},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-N-002")

        # Diesel 냉각수 온도 이상 감지
        coolant_temp = diesel.get("coolant_temp")
        coolant_max = policy.get("COOLANT_TEMP_MAX") or _DIESEL_COOLANT_TEMP_MAX_DEFAULT
        if coolant_temp is not None and coolant_temp > coolant_max:
            key = f"{device_id}:EVT-E-003"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "diesel", "EVT-E-003", "CRITICAL",
                    f"디젤 냉각수 과열: {coolant_temp:.1f}°C > {coolant_max:.1f}°C",
                    {"coolant_temp": coolant_temp, "threshold": coolant_max},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-E-003")

        # Diesel RPM 이상 감지 (운전 중일 때만)
        rpm = diesel.get("rpm")
        operating_mode = (diesel.get("operating_mode") or "").lower()
        if rpm is not None and operating_mode == "running":
            rpm_min = _DIESEL_RPM_NOMINAL * (1 - _DIESEL_RPM_TOLERANCE)
            rpm_max = _DIESEL_RPM_NOMINAL * (1 + _DIESEL_RPM_TOLERANCE)
            if rpm < rpm_min or rpm > rpm_max:
                key = f"{device_id}:EVT-E-004"
                if not await event_pub.is_alerted(key):
                    await event_pub.set_alerted(key)
                    events.append(_evt(
                        device_id, "diesel", "EVT-E-004", "CRITICAL",
                        f"디젤 RPM 이상: {rpm:.0f}rpm (정상 범위 {rpm_min:.0f}~{rpm_max:.0f})",
                        {"rpm": rpm, "rpm_min": rpm_min, "rpm_max": rpm_max},
                    ))
            else:
                await event_pub.clear_alert(f"{device_id}:EVT-E-004")

    # Load 이상 감지 (급증, 과부하, 소실)
    for device_id, state in states.items():
        if state.get("resource_type") != "LOAD":
            continue
        reported = state.get("reported_state") or {}
        current_p = abs(reported.get("P") or 0.0)
        prev_p_raw = await redis.get(f"{_REDIS_PREV_LOAD_P}{device_id}")
        prev_p = float(prev_p_raw) if prev_p_raw else None

        if prev_p is not None and prev_p > 1.0:
            # 급증: 이전 대비 30% 이상 증가
            if current_p > prev_p * (1 + _LOAD_SURGE_RATIO):
                key = f"{device_id}:EVT-N-008"
                if not await event_pub.is_alerted(key):
                    await event_pub.set_alerted(key)
                    events.append(_evt(
                        device_id, "load", "EVT-N-008", "WARNING",
                        f"부하 급증 감지: {prev_p:.1f}→{current_p:.1f}kW (+{(current_p/prev_p-1)*100:.0f}%)",
                        {"prev_kw": prev_p, "current_kw": current_p},
                    ))
            else:
                await event_pub.clear_alert(f"{device_id}:EVT-N-008")

            # 소실: 이전에 부하가 있었는데 0으로 떨어짐
            if prev_p > 5.0 and current_p < 0.5:
                key = f"{device_id}:EVT-N-009"
                if not await event_pub.is_alerted(key):
                    await event_pub.set_alerted(key)
                    events.append(_evt(
                        device_id, "load", "EVT-N-009", "WARNING",
                        f"부하 소실 감지: {prev_p:.1f}kW → {current_p:.1f}kW",
                        {"prev_kw": prev_p, "current_kw": current_p},
                    ))
            else:
                await event_pub.clear_alert(f"{device_id}:EVT-N-009")

        # 과부하: 절대값 기준
        overload_kw = policy.get("LOAD_OVERLOAD_KW") or _LOAD_OVERLOAD_KW
        if current_p > overload_kw:
            key = f"{device_id}:EVT-N-010"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "load", "EVT-N-010", "WARNING",
                    f"부하 과부하 감지: {current_p:.1f}kW > {overload_kw:.1f}kW",
                    {"current_kw": current_p, "threshold_kw": overload_kw},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-N-010")

        await redis.set(f"{_REDIS_PREV_LOAD_P}{device_id}", str(current_p))

    # Solar 이상 감지 (주간 발전량 0, 급감)
    for device_id, state in states.items():
        if state.get("resource_type") != "SOLAR":
            continue
        reported = state.get("reported_state") or {}
        current_p = reported.get("P") or 0.0
        prev_p_raw = await redis.get(f"{_REDIS_PREV_SOLAR_P}{device_id}")
        prev_p = float(prev_p_raw) if prev_p_raw else None

        # 주간 발전량 0 감지 (낮 시간대인데 P = 0)
        is_daytime = _SOLAR_DAYTIME_HOURS[0] <= now_local.hour < _SOLAR_DAYTIME_HOURS[1]
        if is_daytime and current_p < _SOLAR_DAYTIME_MIN_P:
            key = f"{device_id}:EVT-N-011"
            if not await event_pub.is_alerted(key):
                await event_pub.set_alerted(key)
                events.append(_evt(
                    device_id, "solar", "EVT-N-011", "WARNING",
                    f"주간 태양광 발전량 0 감지: {now_local.hour}시(KST) 기준 낮 시간대, P={current_p:.1f}kW",
                    {"hour_local": now_local.hour, "current_kw": current_p},
                ))
        else:
            await event_pub.clear_alert(f"{device_id}:EVT-N-011")

        # 급감: 이전 대비 50% 이상 감소 (주간에만)
        if prev_p is not None and prev_p > _SOLAR_DAYTIME_MIN_P:
            if current_p < prev_p * (1 - _SOLAR_DROP_RATIO):
                key = f"{device_id}:EVT-N-012"
                if not await event_pub.is_alerted(key):
                    await event_pub.set_alerted(key)
                    events.append(_evt(
                        device_id, "solar", "EVT-N-012", "WARNING",
                        f"태양광 급감 감지: {prev_p:.1f}→{current_p:.1f}kW ({(1-current_p/prev_p)*100:.0f}% 감소)",
                        {"prev_kw": prev_p, "current_kw": current_p},
                    ))
            else:
                await event_pub.clear_alert(f"{device_id}:EVT-N-012")

        await redis.set(f"{_REDIS_PREV_SOLAR_P}{device_id}", str(current_p))

    # net_power 연속 부족 감지
    if flow["net_power"] < _DEFICIT_KW:
        deficit_count = await redis.incr(_REDIS_DEFICIT_COUNT)
    else:
        await redis.set(_REDIS_DEFICIT_COUNT, 0)
        deficit_count = 0

    if deficit_count >= _DEFICIT_THRESHOLD:
        key = "system:EVT-N-003"
        if not await event_pub.is_alerted(key):
            await event_pub.set_alerted(key)
            events.append(_evt(
                "system", "system", "EVT-N-003", "WARNING",
                f"전력 부족 {_DEFICIT_THRESHOLD}회 연속: net={flow['net_power']:.1f}kW",
                {"net_power": flow["net_power"], "count": deficit_count},
            ))
    else:
        await event_pub.clear_alert("system:EVT-N-003")

    # STATE_TTL 초과 디바이스 감지 + fail-safe standby 명령
    if state_ttl:
        for device_id, state in states.items():
            calculated_at = state.get("calculated_at")
            if not calculated_at:
                continue
            try:
                ts = datetime.fromisoformat(calculated_at)
                age = (now - ts).total_seconds()
                key = f"{device_id}:EVT-N-004"
                resource_type = state.get("resource_type", "unknown").lower()
                if age > state_ttl:
                    if not await event_pub.is_alerted(key):
                        await event_pub.set_alerted(key)
                        events.append(_evt(
                            device_id, resource_type, "EVT-N-004", "WARNING",
                            f"STATE_TTL 초과: {device_id} 마지막 갱신 {age:.0f}초 전",
                            {"age_seconds": round(age)},
                        ))
                    # TTL 초과 장치는 상태를 알 수 없으므로 standby 강제 진입
                    if resource_type == "ess":
                        failsafe_commands.append(_failsafe_standby(device_id, resource_type, age))
                    elif resource_type == "diesel":
                        failsafe_commands.append(_failsafe_stop(device_id, resource_type, age))
                else:
                    await event_pub.clear_alert(key)
            except Exception as e:
                print(f"[safety] STATE_TTL 처리 오류 | {device_id} | {e}")
                continue

    # Heartbeat 두절 감지 — STATE_TTL과 별도로 통신 단절 자체를 감지
    # ingestion이 heartbeat 수신 시 ems:heartbeat:{site_id}:{device_id} 키를 TTL 30s로 저장
    # 키가 없으면 = 30초 이상 heartbeat 미수신 = 통신 두절
    from ...config import SITE_ID
    for device_id, state in states.items():
        resource_type = state.get("resource_type", "unknown").lower()
        hb_key = f"ems:heartbeat:{SITE_ID}:{device_id}"
        hb_exists = await redis.exists(hb_key)
        evt_key = f"{device_id}:EVT-N-013"
        if not hb_exists:
            if not await event_pub.is_alerted(evt_key):
                await event_pub.set_alerted(evt_key)
                events.append(_evt(
                    device_id, resource_type, "EVT-N-013", "WARNING",
                    f"heartbeat 두절: {device_id} 30초 이상 응답 없음",
                    {"device_id": device_id},
                ))
        else:
            await event_pub.clear_alert(evt_key)

    return events, failsafe_commands


def _evt(device_id: str, resource_type: str, event_type: str,
         severity: str, message: str, payload: dict) -> dict:
    return {
        "device_id": device_id,
        "resource_type": resource_type,
        "event_type": event_type,
        "severity": severity,
        "message": message,
        "payload": payload,
    }


def _failsafe_standby(device_id: str, resource_type: str, age: float) -> dict:
    return {
        "device_id": device_id,
        "resource_type": resource_type,
        "command_type": "ess_mode",
        "payload": {"mode": "standby", "target_power_kw": 0.0},
        "reason": f"fail-safe: STATE_TTL 초과 {age:.0f}초, 상태 불명으로 standby 강제 진입",
        "priority": PRIORITY,
    }


def _failsafe_stop(device_id: str, resource_type: str, age: float) -> dict:
    return {
        "device_id": device_id,
        "resource_type": resource_type,
        "command_type": "stop",
        "payload": {},
        "reason": f"fail-safe: STATE_TTL 초과 {age:.0f}초, 상태 불명으로 정지 명령",
        "priority": PRIORITY,
    }

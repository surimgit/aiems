import asyncio
import json
import time
import uuid

import aiomqtt
import redis.asyncio as aioredis

from ..config import (
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    SITE_ID, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
)
from .db_writer import ControlDBWriter
from .event_publisher import EventPublisher

_ACK_TIMEOUT_SEC = 30.0
_VERIFY_DELAY_SEC = 10.0   # ACK accepted 후 물리 결과 검증까지 대기
_MAX_RETRIES = 3
_RETRY_DELAY_SEC = 2.0

# 명령 타입별 ACK 타임아웃 (초) — diesel 기동은 워밍업 시간 고려
_ACK_TIMEOUT_BY_TYPE: dict[str, float] = {
    "ess_mode": 30.0,
    "start": 60.0,       # diesel 기동 — 워밍업 30초 + 여유
    "stop": 30.0,
    "load_control": 20.0,
    "load_shed": 10.0,
    "curtailment": 15.0,
    "clear_curtailment": 15.0,
    "open": 10.0,    # switch 개방 — 설계문서 §7.4: 2초 이내 전이, 10초 ACK timeout
    "close": 10.0,   # switch 투입
}


def _build_mqtt_command(command_id: str, command: dict) -> tuple[str, dict]:
    device_id = command["device_id"]
    resource_type = command["resource_type"]
    command_type = command["command_type"]
    timeout_sec = _ACK_TIMEOUT_BY_TYPE.get(command_type, _ACK_TIMEOUT_SEC)

    if resource_type.lower() == "switch" and command_type in ("open", "close"):
        return (
            f"{SITE_ID}/simulator-manager/topology/command",
            {
                "command_id": command_id,
                "target_type": "switch",
                "target_id": device_id,
                "command": "OPEN_SWITCH" if command_type == "open" else "CLOSE_SWITCH",
                "source": command.get("issued_by", "rule"),
                "expires_in_sec": command.get("expires_in_sec", timeout_sec),
                "force": command.get("force", False),
            },
        )

    return (
        f"{SITE_ID}/{resource_type}/{device_id}/command",
        {
            "command_id": command_id,
            "command_type": command_type,
            "payload": command["payload"],
            "source": command.get("issued_by", "rule"),
            "expires_in_sec": command.get("expires_in_sec", timeout_sec),
            "force": command.get("force", False),
        },
    )


class MqttCommander:
    def __init__(self, db: ControlDBWriter, event_pub: EventPublisher,
                 pending_acks: dict | None = None, device_cooldown: dict | None = None):
        self._pub_client = None   # 명령 발행 전용
        self._db = db
        self._event_pub = event_pub
        self._redis = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            password=REDIS_PASSWORD, decode_responses=True,
        )
        self._pending_acks: dict[str, tuple[float, str, str]] = pending_acks if pending_acks is not None else {}
        # command_id → (command_type, payload_snapshot) for closed-loop check
        self._pending_verify: dict[str, tuple[str, dict, str, str]] = {}
        # command_id → (retry_count, command_dict) — 재시도 추적
        self._retry_counts: dict[str, tuple[int, dict]] = {}
        # 외부 공유 cooldown dict — ACK 수신 시 즉시 해제
        self._device_cooldown: dict[str, float] = device_cooldown if device_cooldown is not None else {}
        # (device_id, command_type) → 이미 EVT-N-005 발행 중 — 성공 시 해제
        self._verify_fail_alerted: set[tuple[str, str]] = set()
        self._ack_task: asyncio.Task | None = None
        self._timeout_task: asyncio.Task | None = None

    async def __aenter__(self):
        self._pub_client = aiomqtt.Client(
            hostname=MQTT_HOST, port=MQTT_PORT,
            username=MQTT_USER, password=MQTT_PASSWORD,
        )
        await self._pub_client.__aenter__()

        self._ack_task = asyncio.create_task(self._ack_listener())
        self._timeout_task = asyncio.create_task(self._timeout_checker())
        return self

    async def __aexit__(self, *args):
        for task in (self._ack_task, self._timeout_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        await self._pub_client.__aexit__(*args)
        await self._redis.aclose()

    async def send(self, command: dict) -> None:
        device_id = command["device_id"]
        resource_type = command["resource_type"]
        command_id = str(uuid.uuid4())
        topic, payload = _build_mqtt_command(command_id, command)
        # publish 전에 먼저 등록 — ACK가 publish await 중에 먼저 들어오는 race condition 방지
        self._pending_acks[command_id] = (time.monotonic(), device_id, resource_type)
        self._retry_counts[command_id] = (0, command)

        # desired_state 저장 — state-processor가 읽어서 State Snapshot에 반영
        desired = {
            "command_id": command_id,
            "command_type": command["command_type"],
            "payload": command["payload"],
            "issued_by": command.get("issued_by", "rule"),
            "issued_at": time.time(),
        }
        await self._set_desired(command, desired)

        # 폐루프 검증 대상 등록 (command_type, payload, device_id, resource_type)
        self._pending_verify[command_id] = (
            command["command_type"],
            command["payload"],
            device_id,
            resource_type,
        )

        await self._pub_client.publish(topic, json.dumps(payload, ensure_ascii=False))
        print(f"[control] → {topic} | {command['command_type']} {command['payload']} | {command['reason']} | cmd={command_id[:8]}")

        command["site_id"] = SITE_ID
        await self._db.insert_command(command, command_id)

    async def _ack_listener(self) -> None:
        _RECONNECT_DELAY = 5
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=MQTT_HOST,
                    port=MQTT_PORT,
                    username=MQTT_USER,
                    password=MQTT_PASSWORD,
                ) as sub:
                    await sub.subscribe(f"{SITE_ID}/+/+/ack", qos=1)
                    await sub.subscribe(f"{SITE_ID}/simulator-manager/topology/command/ack", qos=1)
                    print("[control][ack] ACK 구독 시작")
                    async for msg in sub.messages:
                        topic = str(msg.topic)
                        if not topic.endswith("/ack"):
                            continue
                        try:
                            data = json.loads(msg.payload)
                            command_id = data.get("command_id")
                            status = data.get("status", "unknown")
                            reason = data.get("reason", "")
                            if command_id and command_id in self._pending_acks:
                                _, device_id, resource_type = self._pending_acks.pop(command_id)
                                self._retry_counts.pop(command_id, None)
                                # ACK 수신 즉시 cooldown 해제 — 35초 무조건 대기 불필요
                                self._device_cooldown.pop(device_id, None)
                                ack_label = f"{status}" + (f" ({reason})" if reason else "")
                                print(f"[control][ack] {device_id} | {command_id[:8]}... | {ack_label}")
                                await self._db.update_ack(command_id, status.upper())

                                if status.upper() == "ACCEPTED":
                                    verify_info = self._pending_verify.pop(command_id, None)
                                    if verify_info:
                                        asyncio.create_task(
                                            self._verify_after_delay(command_id, *verify_info)
                                        )
                                    else:
                                        asyncio.create_task(
                                            self._verify_from_db(command_id, device_id, resource_type)
                                        )
                                else:
                                    self._pending_verify.pop(command_id, None)
                        except Exception:
                            continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"[control][ack] 구독 연결 끊김: {e} — {_RECONNECT_DELAY}s 후 재연결")
                await asyncio.sleep(_RECONNECT_DELAY)

    async def _verify_from_db(
        self,
        command_id: str,
        device_id: str,
        resource_type: str,
    ) -> None:
        """operator 명령: DB에서 command_type/payload 조회 후 물리 결과 검증."""
        print(f"[control][verify] DB 조회 시작 | {device_id} | {command_id[:8]}...")
        try:
            row = await self._db.get_command(command_id)
            if not row:
                print(f"[control][verify] DB 레코드 없음 | {command_id[:8]}...")
                return
            command_type, payload = row
            if isinstance(payload, str):
                payload = json.loads(payload)
            await self._verify_after_delay(command_id, command_type, payload, device_id, resource_type)
        except Exception as e:
            print(f"[control][verify] DB 조회 오류 | {device_id} | {e}")

    async def _verify_after_delay(
        self,
        command_id: str,
        command_type: str,
        payload: dict,
        device_id: str,
        resource_type: str,
    ) -> None:
        await asyncio.sleep(_VERIFY_DELAY_SEC)
        try:
            state_raw = await self._get_state(device_id)
            if not state_raw:
                # 상태 자체가 없으면 TTL 초과 → safety 룰이 처리
                return

            state = json.loads(state_raw)
            verified = _check_physical_result(command_type, payload, state)

            await self._db.mark_verified(command_id, verified)
            alert_key = (device_id, command_type)
            if verified:
                print(f"[control][verify] OK | {device_id} | {command_id[:8]}...")
                self._verify_fail_alerted.discard(alert_key)
            else:
                print(f"[control][verify] FAIL | {device_id} | {command_id[:8]}... — 물리 반영 안됨")
                if alert_key not in self._verify_fail_alerted:
                    self._verify_fail_alerted.add(alert_key)
                    await self._event_pub.publish({
                        "device_id": device_id,
                        "resource_type": resource_type,
                        "event_type": "EVT-N-005",
                        "severity": "WARNING",
                        "message": f"명령 미반영 ({command_type})",
                        "payload": {"command_id": command_id, "command_type": command_type, "expected": payload},
                    })
        except Exception as e:
            print(f"[control][verify] ERROR | {device_id} | {e}")

    async def _get_state(self, device_id: str) -> str | None:
        state_raw = await self._redis.get(f"state:{SITE_ID}:{device_id}")
        if state_raw:
            return state_raw

        pattern = f"state:{SITE_ID}:*:{device_id}"
        keys = [key async for key in self._redis.scan_iter(pattern)]
        if not keys:
            return None
        values = await self._redis.mget(*keys)
        states = [json.loads(value) for value in values if value]
        if not states:
            return None
        latest = max(
            states,
            key=lambda state: state.get("calculated_at") or state.get("timestamp") or "",
        )
        return json.dumps(latest, ensure_ascii=False)

    async def _set_desired(self, command: dict, desired: dict) -> None:
        device_id = command["device_id"]
        edge_id = command.get("edge_id")
        value = json.dumps(desired, ensure_ascii=False)
        keys = [f"desired:{SITE_ID}:{device_id}"]
        if edge_id and edge_id != device_id:
            keys.insert(0, f"desired:{SITE_ID}:{edge_id}:{device_id}")

        for key in keys:
            await self._redis.set(
                key,
                value,
                ex=43200,  # 12시간 TTL — 재시작 후에도 desired 상태 유지
            )

    async def _timeout_checker(self) -> None:
        while True:
            await asyncio.sleep(5)
            now = time.monotonic()
            expired = [
                cid for cid, (sent_at, _, __) in self._pending_acks.items()
                if now - sent_at > _ACK_TIMEOUT_BY_TYPE.get(
                    (self._retry_counts.get(cid, (0, {}))[1] or {}).get("command_type", ""),
                    _ACK_TIMEOUT_SEC
                )
            ]
            for command_id in expired:
                _, device_id, resource_type = self._pending_acks.pop(command_id)
                self._pending_verify.pop(command_id, None)
                retry_count, original_cmd = self._retry_counts.pop(command_id, (0, None))

                if original_cmd and retry_count < _MAX_RETRIES:
                    # 재시도: 새 command_id로 재발행
                    await asyncio.sleep(_RETRY_DELAY_SEC)
                    new_id = str(uuid.uuid4())
                    new_retry = retry_count + 1
                    print(f"[control][ack] TIMEOUT → 재시도 {new_retry}/{_MAX_RETRIES} | {device_id} | {command_id[:8]}...")
                    self._pending_acks[new_id] = (time.monotonic(), device_id, resource_type)
                    self._retry_counts[new_id] = (new_retry, original_cmd)
                    self._pending_verify[new_id] = self._pending_verify.pop(command_id, (
                        original_cmd.get("command_type", ""),
                        original_cmd.get("payload", {}),
                        device_id,
                        resource_type,
                    ))
                    topic, retry_payload = _build_mqtt_command(new_id, original_cmd)
                    try:
                        await self._pub_client.publish(topic, json.dumps(retry_payload, ensure_ascii=False))
                        await self._db.update_ack(command_id, "TIMEOUT")
                    except Exception as e:
                        print(f"[control][ack] 재시도 발행 실패 | {device_id} | {e}")
                else:
                    # 최대 재시도 초과 → CRITICAL 이벤트 발행
                    print(f"[control][ack] TIMEOUT 최종 실패 ({_MAX_RETRIES}회) | {device_id} | {command_id[:8]}...")
                    await self._db.update_ack(command_id, "TIMEOUT")
                    alert_key = (device_id, "timeout")
                    if alert_key not in self._verify_fail_alerted:
                        self._verify_fail_alerted.add(alert_key)
                        await self._event_pub.publish({
                            "device_id": device_id,
                            "resource_type": resource_type,
                            "event_type": "EVT-E-005",
                            "severity": "CRITICAL",
                            "message": f"명령 전달 실패",
                            "payload": {"command_id": command_id, "retries": _MAX_RETRIES},
                        })


def _check_physical_result(command_type: str, payload: dict, state: dict) -> bool:
    """명령 의도가 현재 Redis state에 반영됐는지 휴리스틱 검증."""
    rs = state.get("reported_state") or {}
    p = rs.get("P") or 0

    if command_type == "ess_mode":
        mode = payload.get("mode")
        current_mode = (rs.get("operating_mode") or "").lower()
        if mode in ("charge", "charging"):
            return current_mode in ("charge", "charging") or p < -0.5
        if mode in ("discharge", "discharging"):
            return current_mode in ("discharge", "discharging") or p > 0.5
        if mode == "standby":
            return current_mode == "standby" or abs(p) < 1.0

    if command_type == "start":
        operating_mode = (rs.get("operating_mode") or "").lower()
        return operating_mode in ("running", "starting")

    if command_type == "stop":
        operating_mode = (rs.get("operating_mode") or "").lower()
        return operating_mode in ("off", "stopped", "stopping", "idle")

    if command_type == "load_shed":
        # 이전 P값 없이 정확한 검증 불가 — ACK accepted 자체를 성공으로 간주
        return True

    if command_type == "curtailment":
        limit_kw = payload.get("limit_kw")
        if limit_kw is not None and p > 0:
            return p <= limit_kw + 1.0  # 1kW 허용 오차

    if command_type == "clear_curtailment":
        # 해제 명령 — P가 curtailment 전보다 높아야 하지만 기준값 없음
        # ACK accepted 자체를 성공으로 간주
        return True

    if command_type == "load_control":
        target_kw = payload.get("target_kw")
        if target_kw is not None:
            return abs(p - target_kw) <= target_kw * 0.1 + 1.0  # 10% + 1kW 허용 오차

    if command_type == "open":
        return (rs.get("switch_state") or "").upper() == "OPEN"

    if command_type == "close":
        return (rs.get("switch_state") or "").upper() == "CLOSED"

    # 알 수 없는 명령 타입 → 낙관적 True
    return True

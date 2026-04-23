import asyncio
import json
import time
import uuid

import aiomqtt
import redis.asyncio as aioredis

from config import MQTT_HOST, MQTT_PORT, SITE_ID, REDIS_HOST, REDIS_PORT
from adapters.db_writer import ControlDBWriter
from adapters.event_publisher import EventPublisher

_ACK_TIMEOUT_SEC = 30.0
_VERIFY_DELAY_SEC = 10.0   # ACK accepted 후 물리 결과 검증까지 대기


class MqttCommander:
    def __init__(self, db: ControlDBWriter, event_pub: EventPublisher, pending_acks: dict | None = None):
        self._pub_client = None   # 명령 발행 전용
        self._sub_client = None   # ACK 구독 전용
        self._db = db
        self._event_pub = event_pub
        self._redis = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self._pending_acks: dict[str, tuple[float, str, str]] = pending_acks if pending_acks is not None else {}
        # command_id → (command_type, payload_snapshot) for closed-loop check
        self._pending_verify: dict[str, tuple[str, dict, str, str]] = {}
        self._ack_task: asyncio.Task | None = None
        self._timeout_task: asyncio.Task | None = None

    async def __aenter__(self):
        self._pub_client = aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT)
        await self._pub_client.__aenter__()

        self._sub_client = aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT)
        await self._sub_client.__aenter__()
        await self._sub_client.subscribe(f"{SITE_ID}/+/+/ack")

        self._ack_task = asyncio.create_task(self._ack_listener())
        self._timeout_task = asyncio.create_task(self._timeout_checker())
        return self

    async def __aexit__(self, *args):
        if self._ack_task:
            self._ack_task.cancel()
        if self._timeout_task:
            self._timeout_task.cancel()
        await self._sub_client.__aexit__(*args)
        await self._pub_client.__aexit__(*args)
        await self._redis.aclose()

    async def send(self, command: dict) -> None:
        device_id = command["device_id"]
        resource_type = command["resource_type"]
        command_id = str(uuid.uuid4())
        topic = f"{SITE_ID}/{resource_type}/{device_id}/command"
        payload = {
            "command_id": command_id,
            "command_type": command["command_type"],
            "payload": command["payload"],
            "source": command.get("issued_by", "rule"),
            "expires_in_sec": command.get("expires_in_sec", 30),
            "force": command.get("force", False),
        }
        await self._pub_client.publish(topic, json.dumps(payload, ensure_ascii=False))
        print(f"[control] → {topic} | {command['command_type']} {command['payload']} | {command['reason']}")

        command["site_id"] = SITE_ID
        await self._db.insert_command(command, command_id)

        self._pending_acks[command_id] = (time.monotonic(), device_id, resource_type)

        # desired_state 저장 — state-processor가 읽어서 State Snapshot에 반영
        desired = {
            "command_id": command_id,
            "command_type": command["command_type"],
            "payload": command["payload"],
            "issued_by": command.get("issued_by", "rule"),
            "issued_at": time.time(),
        }
        await self._redis.set(
            f"desired:{SITE_ID}:{device_id}",
            json.dumps(desired, ensure_ascii=False),
            ex=300,  # 5분 TTL — 명령 반영 후 자연 만료
        )

        # 폐루프 검증 대상 등록 (command_type, payload, device_id, resource_type)
        self._pending_verify[command_id] = (
            command["command_type"],
            command["payload"],
            device_id,
            resource_type,
        )

    async def _ack_listener(self) -> None:
        try:
            async for msg in self._sub_client.messages:
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
                        ack_label = f"{status}" + (f" ({reason})" if reason else "")
                        print(f"[control][ack] {device_id} | {command_id[:8]}... | {ack_label}")
                        await self._db.update_ack(command_id, status.upper())

                        if status.upper() == "ACCEPTED":
                            verify_info = self._pending_verify.pop(command_id, None)
                            if verify_info:
                                # rule 명령: _pending_verify에 등록된 경우
                                asyncio.create_task(
                                    self._verify_after_delay(command_id, *verify_info)
                                )
                            else:
                                # operator 명령: command_type/payload를 DB에서 조회해 검증
                                asyncio.create_task(
                                    self._verify_from_db(command_id, device_id, resource_type)
                                )
                        else:
                            self._pending_verify.pop(command_id, None)
                except Exception:
                    continue
        except asyncio.CancelledError:
            pass

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
            state_raw = await self._redis.get(f"state:{SITE_ID}:{device_id}")
            if not state_raw:
                # 상태 자체가 없으면 TTL 초과 → safety 룰이 처리
                return

            state = json.loads(state_raw)
            verified = _check_physical_result(command_type, payload, state)

            await self._db.mark_verified(command_id, verified)
            if verified:
                print(f"[control][verify] OK | {device_id} | {command_id[:8]}...")
            else:
                print(f"[control][verify] FAIL | {device_id} | {command_id[:8]}... — 물리 반영 안됨")
                await self._event_pub.publish({
                    "device_id": device_id,
                    "resource_type": resource_type,
                    "event_type": "EVT-N-005",
                    "severity": "WARNING",
                    "message": (
                        f"명령 수락됐으나 {_VERIFY_DELAY_SEC:.0f}s 후에도 상태 미반영 "
                        f"[{command_type}]"
                    ),
                    "payload": {"command_id": command_id, "command_type": command_type, "expected": payload},
                })
        except Exception as e:
            print(f"[control][verify] ERROR | {device_id} | {e}")

    async def _timeout_checker(self) -> None:
        while True:
            await asyncio.sleep(5)
            now = time.monotonic()
            expired = [
                cid for cid, (sent_at, _, __) in self._pending_acks.items()
                if now - sent_at > _ACK_TIMEOUT_SEC
            ]
            for command_id in expired:
                _, device_id, _ = self._pending_acks.pop(command_id)
                self._pending_verify.pop(command_id, None)
                print(f"[control][ack] TIMEOUT | {device_id} | {command_id[:8]}...")
                await self._db.update_ack(command_id, "TIMEOUT")


def _check_physical_result(command_type: str, payload: dict, state: dict) -> bool:
    """명령 의도가 현재 Redis state에 반영됐는지 휴리스틱 검증."""
    if command_type == "ess_mode":
        mode = payload.get("mode")
        if mode == "charging":
            return (state.get("P") or 0) < 0       # 충전 중 → P < 0
        if mode == "discharging":
            return (state.get("P") or 0) > 0       # 방전 중 → P > 0
        if mode == "standby":
            return abs(state.get("P") or 0) < 1.0  # 대기 중 → |P| ≈ 0

    if command_type == "diesel_command":
        action = payload.get("action")
        if action == "start":
            return state.get("operating_mode") in ("running", "RUNNING")
        if action == "stop":
            return state.get("operating_mode") in ("stopped", "STOPPED", "idle", "IDLE")

    if command_type == "load_shed":
        # reduction_ratio가 0보다 크면 실제 P가 줄었어야 함
        # 정확한 이전값이 없으므로 ratio > 0.5 이상이면 P가 절반 이하여야 한다고 가정
        ratio = payload.get("reduction_ratio", 0)
        if ratio >= 1.0:
            return abs(state.get("P") or 0) < 1.0
        # 부분 차단은 P값 변화를 사전값 없이 검증 불가 → 낙관적으로 True
        return True

    if command_type == "set_curtailment":
        target = payload.get("curtailment_ratio", 1.0)
        p = state.get("P") or 0
        rated = state.get("rated_power") or p
        if rated > 0:
            actual_ratio = p / rated
            return actual_ratio <= target + 0.1  # ±10% 허용

    # 알 수 없는 명령 타입 → 검증 건너뜀 (낙관적 True)
    return True

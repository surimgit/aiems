from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import LoadCommandHandler
from core.load import LoadDevice, LoadDeviceConfig, load_device_configs
from core.scenario import LoadScenarioEngine
from runtime_config import RuntimeConfig

# topology 상태 추적
_topology_line_states: dict = {}
_topology_switch_states: dict = {}  # line_id → switch payload


def _is_wire_fault(device_id: str) -> bool:
    for line_id, line in _topology_line_states.items():
        if device_id not in line.get("affected_devices", []):
            continue
        if line.get("status", "NORMAL") != "NORMAL":
            return True
        sw = _topology_switch_states.get(line_id, {})
        if sw.get("position", "CLOSED") not in ("CLOSED",):
            return True
    return False


def _on_topology_message(topic: str, payload: dict) -> None:
    parts = topic.split("/")
    if len(parts) < 4:
        return
    kind = parts[2]
    if kind == "line":
        line_id = payload.get("line_id")
        if line_id:
            _topology_line_states[line_id] = payload
    elif kind == "switch":
        line_id = payload.get("line_id")
        if line_id:
            _topology_switch_states[line_id] = payload

CONFIG_POLL_INTERVAL = 2


@dataclass(slots=True)
class RuntimePublishBatch:
    device_id: str
    telemetry_json: str
    heartbeat_json: str


class LoadSimulatorApp:
    # 런타임 의존성을 조립하고 앱 상태를 초기화한다.
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config
        self.publisher = MqttPublisher(config.mqtt_broker_host, config.mqtt_broker_port)
        self.command_handler = LoadCommandHandler(config.fleet)
        self.scenario_engine = LoadScenarioEngine(config.scenario_profiles)
        self.mqtt_subscriber = MqttCommandSubscriber(
            self.command_handler,
            self.publisher,
            config.site_id,
            "load",
            config.mqtt_broker_host,
            config.mqtt_broker_port,
            topology_callback=_on_topology_message,
        )
        self._stop_event = asyncio.Event()

    def add_device(self, device_config: LoadDeviceConfig) -> None:
        if self.config.fleet.get(device_config.device_id) is not None:
            return
        device = LoadDevice.from_config(device_config)
        self.config.fleet.register(device)
        print(f"[hot-reload] Device added: {device_config.device_id}")

    def remove_device(self, device_id: str) -> None:
        self.config.fleet.unregister(device_id)
        print(f"[hot-reload] Device removed: {device_id}")

    async def _watch_config(self) -> None:
        last_mtime = self.config.devices_path.stat().st_mtime
        while not self._stop_event.is_set():
            await asyncio.sleep(CONFIG_POLL_INTERVAL)
            try:
                mtime = self.config.devices_path.stat().st_mtime
                if mtime == last_mtime:
                    continue
                last_mtime = mtime
                new_configs = load_device_configs(self.config.devices_path)
                new_ids = {c.device_id for c in new_configs}
                current_ids = {d.device_id for d in self.config.fleet.list_all()}
                for cfg in new_configs:
                    if cfg.device_id not in current_ids:
                        self.add_device(cfg)
                for device_id in current_ids - new_ids:
                    self.remove_device(device_id)
            except Exception as e:
                print(f"[hot-reload] Config reload error: {e}")

    # 외부 종료 요청을 받아 런타임 루프를 멈추게 한다.
    def request_shutdown(self) -> None:
        self._stop_event.set()

    # 현재 시점 기준으로 모든 활성 분전함의 발행 배치를 만든다.
    def build_publish_batches(self, observed_at: datetime | None = None) -> list[RuntimePublishBatch]:
        current_time = observed_at or datetime.now(timezone.utc)
        self.scenario_engine.tick_fleet(self.config.fleet, current_time)

        batches: list[RuntimePublishBatch] = []
        for device in self.config.fleet.list_enabled():
            batches.append(
                RuntimePublishBatch(
                    device_id=device.device_id,
                    telemetry_json=self.publisher.serialize_telemetry(device),
                    heartbeat_json=self.publisher.serialize_heartbeat(device.site_id, device.device_id),
                )
            )
        return batches

    # 발행 직전 핵심 측정값을 콘솔 로그로 남긴다.
    @staticmethod
    def log_publish_batch(device: LoadDevice, batch: RuntimePublishBatch) -> None:
        print(
            f"[LOAD][{device.device_id}][panel={device.panel_id}] "
            f"P={device.measurement.p_kw:.3f}kW shed={device.state.shed_ratio:.3f}"
        )

    # 한 분전함의 telemetry와 heartbeat를 브로커로 발행한다.
    def publish_batch(self, device: LoadDevice) -> None:
        self.publisher.publish_telemetry(device, wire_fault=_is_wire_fault(device.device_id))
        self.publisher.publish_heartbeat(device.site_id, "load", device.device_id)

    # 한 주기의 시나리오 계산과 MQTT 발행을 순서대로 수행한다.
    def run_publish_cycle(self, observed_at: datetime | None = None) -> list[RuntimePublishBatch]:
        batches = self.build_publish_batches(observed_at)
        for batch in list(batches):
            device = self.config.fleet.get(batch.device_id)
            if device is None:
                continue
            self.log_publish_batch(device, batch)
            self.publish_batch(device)
        return batches

    # MQTT 입출력을 시작하고 정해진 주기로 발행 루프를 실행한다.
    async def run(self, *, max_cycles: int | None = None) -> None:
        print(
            f"[LOAD] Starting simulator fleet "
            f"(site={self.config.site_id}, edge={self.config.edge_id}, devices={len(self.config.fleet.list_enabled())})"
        )
        self.publisher.start()
        self.mqtt_subscriber.start()

        completed_cycles = 0
        watch_task = asyncio.create_task(self._watch_config())
        try:
            while not self._stop_event.is_set():
                self.run_publish_cycle()
                completed_cycles += 1
                if max_cycles is not None and completed_cycles >= max_cycles:
                    break
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.config.publish_interval_sec,
                    )
                except asyncio.TimeoutError:
                    continue
        finally:
            watch_task.cancel()
            try:
                await watch_task
            except asyncio.CancelledError:
                pass
            self.mqtt_subscriber.stop()
            self.publisher.stop()

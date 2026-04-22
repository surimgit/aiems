from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import LoadCommandHandler
from core.load import LoadDevice
from core.scenario import LoadScenarioEngine
from runtime_config import RuntimeConfig


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
        )
        self._stop_event = asyncio.Event()

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
        self.publisher.publish_telemetry(device)
        self.publisher.publish_heartbeat(device.site_id, "load", device.device_id)

    # 한 주기의 시나리오 계산과 MQTT 발행을 순서대로 수행한다.
    def run_publish_cycle(self, observed_at: datetime | None = None) -> list[RuntimePublishBatch]:
        batches = self.build_publish_batches(observed_at)
        for batch in batches:
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
            self.mqtt_subscriber.stop()
            self.publisher.stop()

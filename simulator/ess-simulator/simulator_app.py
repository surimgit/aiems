from __future__ import annotations

import asyncio

from adapters.inbound.cli_controller import CliController, CliExitRequested
from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandHandler
from core.ess import DeviceSpec, EssSimulator, SafetySpec
from mqtt_contract import coerce_simulator_snapshot
from runtime_config import DeviceFileConfig


class EssSimulatorApp:
    """설정, 도메인 로직, MQTT 입출력을 한 곳에서 조립하는 앱 계층이다."""

    def __init__(self, config: DeviceFileConfig) -> None:
        """실행 설정을 기반으로 시뮬레이터와 어댑터를 모두 초기화한다."""

        device_spec = DeviceSpec(
            plant_id=config.plant_id,
            device_id=config.device_id,
            resource_type=config.resource_type,
            publish_interval_sec=config.publish_interval_sec,
            power_limit_kw=config.power_limit_kw,
            capacity_kwh=config.capacity_kwh,
        )
        safety_spec = SafetySpec(
            low_soc_threshold=config.low_soc_threshold,
            high_soc_threshold=config.high_soc_threshold,
            min_safe_soc_threshold=config.min_safe_soc_threshold,
            max_safe_soc_threshold=config.max_safe_soc_threshold,
            max_temperature_c=config.max_temperature_c,
        )

        self.simulator = EssSimulator(
            device_spec=device_spec,
            safety_spec=safety_spec,
            initial_soc=config.initial_soc,
            temperature_c=config.temperature_c,
        )
        self.command_handler = CommandHandler(self.simulator)
        self.publisher = MqttPublisher(config.mqtt_broker_host, config.mqtt_broker_port)
        self.mqtt_subscriber = MqttCommandSubscriber(
            self.command_handler,
            self.publisher,
            config.plant_id,
            config.resource_type,
            config.device_id,
            config.mqtt_broker_host,
            config.mqtt_broker_port,
        )
        self.cli = CliController(self.command_handler, self.publisher)
        self._stop_event = asyncio.Event()

    def request_shutdown(self) -> None:
        """다른 루프들이 종료를 감지할 수 있도록 stop 이벤트를 세팅한다."""

        self._stop_event.set()

    async def run(self) -> None:
        """publisher, subscriber, CLI 루프를 동시에 실행하고 종료 시 정리한다."""

        snapshot = self.simulator.snapshot()
        print(
            "[ESS] Starting simulator "
            f"(plant={snapshot['plant_id']}, device={snapshot['device_id']}, interval={snapshot['publish_interval_sec']}s)"
        )
        print("[ESS] Commands: mode <charge|discharge|standby> [power], set-spec <field> <value>, set-safety <field> <value>, show, quit")
        self.publisher.start()
        self.mqtt_subscriber.start()

        try:
            await asyncio.gather(
                self._runtime_loop(),
                self._cli_loop(),
            )
        finally:
            self.mqtt_subscriber.stop()
            self.publisher.stop()

    async def _runtime_loop(self) -> None:
        """주기마다 시뮬레이터를 한 tick 진행하고 telemetry와 heartbeat를 함께 발행한다."""

        while not self._stop_event.is_set():
            snapshot = coerce_simulator_snapshot(self.simulator.tick())
            telemetry_json = self.publisher.serialize_telemetry(snapshot)
            print(f"[ESS][telemetry] {telemetry_json}")
            self.publisher.publish_telemetry(snapshot)

            heartbeat_json = self.publisher.serialize_heartbeat(
                snapshot["plant_id"],
                snapshot["resource_type"],
                snapshot["device_id"],
            )
            print(f"[ESS][heartbeat] {heartbeat_json}")
            self.publisher.publish_heartbeat(
                snapshot["plant_id"],
                snapshot["resource_type"],
                snapshot["device_id"],
            )

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.simulator.device_spec.publish_interval_sec,
                )
            except asyncio.TimeoutError:
                continue

    async def _cli_loop(self) -> None:
        """사용자 입력을 받아 command handler로 넘기고 결과를 콘솔에 출력한다."""

        while not self._stop_event.is_set():
            try:
                line = await asyncio.to_thread(input, "ess> ")
            except EOFError:
                self.request_shutdown()
                return

            if not line.strip():
                continue

            try:
                result = self.cli.handle_line(line)
            except CliExitRequested:
                self.request_shutdown()
                return
            except Exception as exc:
                print(f"[ESS][cli] error: {exc}")
                continue

            if result is None:
                continue

            print(result)

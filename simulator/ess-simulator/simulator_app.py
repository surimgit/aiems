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
    """설정, 시뮬레이터, MQTT 어댑터를 한 곳에서 조립한다."""

    def __init__(self, config: DeviceFileConfig) -> None:
        device_spec = DeviceSpec(
            plant_id=config.plant_id,
            device_id=config.device_id,
            resource_type=config.resource_type,
            publish_interval_sec=config.publish_interval_sec,
            power_limit_kw=config.power_limit_kw,
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
        """다음 루프 반복에서 안전하게 종료하도록 신호를 남긴다."""
        self._stop_event.set()

    async def run(self) -> None:
        """Publisher, subscriber, CLI 루프를 함께 시작한다."""
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
        """주기적으로 tick을 수행하고 telemetry를 발행한다."""
        while not self._stop_event.is_set():
            snapshot = coerce_simulator_snapshot(self.simulator.tick())
            telemetry_json = self.publisher.serialize_telemetry(snapshot)
            print(f"[ESS][telemetry] {telemetry_json}")
            self.publisher.publish_telemetry(snapshot)

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.simulator.device_spec.publish_interval_sec,
                )
            except asyncio.TimeoutError:
                continue

    async def _cli_loop(self) -> None:
        """로컬 CLI 입력을 받아 같은 command handler로 전달한다."""
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

from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass
from pathlib import Path

from adapters.inbound.cli_controller import CliController, CliExitRequested
from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandHandler
from core.ess import DeviceSpec, EssSimulator, SafetySpec
from mqtt_contract import coerce_simulator_snapshot, snapshot_to_telemetry
from runtime_config import DeviceConfig, RuntimeConfig, load_config

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


@dataclass
class RuntimePublishBatch:
    snapshot: dict[str, object]
    telemetry_json: str
    heartbeat_json: str


def build_profile(device: DeviceConfig):
    profile_module = importlib.import_module(device.profile.module)
    profile_class = getattr(profile_module, device.profile.class_name)
    return profile_class(seed=device.profile.seed)


class EssSimulatorApp:
    def __init__(self, config: RuntimeConfig, config_path: Path, *, interactive: bool = True) -> None:
        self.config = config
        self.config_path = config_path
        self.interactive = interactive
        self.publisher = MqttPublisher(config.mqtt_broker_host, config.mqtt_broker_port)
        self.simulators: dict[str, EssSimulator] = {}
        self.command_handlers: dict[str, CommandHandler] = {}
        self.cli = CliController(self)
        self.mqtt_subscriber = MqttCommandSubscriber(
            self.command_handlers,
            self.publisher,
            config.plant_id,
            "ess",
            config.mqtt_broker_host,
            config.mqtt_broker_port,
            topology_callback=_on_topology_message,
        )
        self._stop_event = asyncio.Event()
        self._frozen_soc: dict[str, float] = {}
        self._build_simulators()

    def _build_simulators(self) -> None:
        for device in self.config.devices:
            simulator = EssSimulator(
                device_spec=DeviceSpec(
                    plant_id=self.config.plant_id,
                    device_id=device.device_id,
                    resource_type=device.resource_type,
                    publish_interval_sec=device.publish_interval_sec,
                    power_limit_kw=device.power_limit_kw,
                    capacity_kwh=device.capacity_kwh,
                ),
                safety_spec=SafetySpec(
                    low_soc_threshold=device.low_soc_threshold,
                    high_soc_threshold=device.high_soc_threshold,
                    min_safe_soc_threshold=device.min_safe_soc_threshold,
                    max_safe_soc_threshold=device.max_safe_soc_threshold,
                    max_temperature_c=device.max_temperature_c,
                ),
                initial_soc=device.initial_soc,
                temperature_c=device.temperature_c,
                profile=build_profile(device),
            )
            self.simulators[device.device_id] = simulator
            self.command_handlers[device.device_id] = CommandHandler(simulator)

    def add_device(self, device: DeviceConfig) -> None:
        if device.device_id in self.simulators:
            return
        simulator = EssSimulator(
            device_spec=DeviceSpec(
                plant_id=self.config.plant_id,
                device_id=device.device_id,
                resource_type=device.resource_type,
                publish_interval_sec=device.publish_interval_sec,
                power_limit_kw=device.power_limit_kw,
                capacity_kwh=device.capacity_kwh,
            ),
            safety_spec=SafetySpec(
                low_soc_threshold=device.low_soc_threshold,
                high_soc_threshold=device.high_soc_threshold,
                min_safe_soc_threshold=device.min_safe_soc_threshold,
                max_safe_soc_threshold=device.max_safe_soc_threshold,
                max_temperature_c=device.max_temperature_c,
            ),
            initial_soc=device.initial_soc,
            temperature_c=device.temperature_c,
            profile=build_profile(device),
        )
        self.simulators[device.device_id] = simulator
        self.command_handlers[device.device_id] = CommandHandler(simulator)
        print(f"[hot-reload] Device added: {device.device_id}")

    def remove_device(self, device_id: str) -> None:
        self.simulators.pop(device_id, None)
        self.command_handlers.pop(device_id, None)
        print(f"[hot-reload] Device removed: {device_id}")

    async def _watch_config(self) -> None:
        last_mtime = self.config_path.stat().st_mtime
        while not self._stop_event.is_set():
            await asyncio.sleep(CONFIG_POLL_INTERVAL)
            try:
                mtime = self.config_path.stat().st_mtime
                if mtime == last_mtime:
                    continue
                last_mtime = mtime
                new_config = load_config(self.config_path)
                new_ids = {d.device_id for d in new_config.devices}
                current_ids = set(self.simulators.keys())
                for device in new_config.devices:
                    if device.device_id not in current_ids:
                        self.add_device(device)
                for device_id in current_ids - new_ids:
                    self.remove_device(device_id)
            except Exception as e:
                print(f"[hot-reload] Config reload error: {e}")

    def request_shutdown(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        print(f"[ESS] Starting simulator fleet (plant={self.config.plant_id}, devices={len(self.simulators)})")
        if self.interactive:
            print("[ESS] Commands: show, show <device_id>, mode <device_id> <charge|discharge|standby> [power], quit")
        else:
            print("[ESS] Interactive CLI disabled; runtime loop only")
        self.publisher.start()
        self.mqtt_subscriber.start()

        try:
            if self.interactive:
                await asyncio.gather(self._runtime_loop(), self._cli_loop(), self._watch_config())
            else:
                await asyncio.gather(self._runtime_loop(), self._watch_config())
        finally:
            self.mqtt_subscriber.stop()
            self.publisher.stop()

    def build_publish_batches(self) -> list[RuntimePublishBatch]:
        batches: list[RuntimePublishBatch] = []
        for simulator in list(self.simulators.values()):
            snapshot = coerce_simulator_snapshot(simulator.tick())
            device_id = snapshot["device_id"]
            wire_fault = _is_wire_fault(device_id)

            if wire_fault:
                # SOC 고정: wire_fault 시작 시점에 저장된 SOC를 계속 발행
                if device_id not in self._frozen_soc:
                    self._frozen_soc[device_id] = snapshot["soc"]
                snapshot = dict(snapshot)
                snapshot["power_kw"] = 0.0
                snapshot["soc"] = self._frozen_soc[device_id]
            else:
                # 정상 복귀 시 frozen SOC 해제
                self._frozen_soc.pop(device_id, None)

            comms = "wire_fault" if wire_fault else "ok"
            batches.append(
                RuntimePublishBatch(
                    snapshot=snapshot,
                    telemetry_json=self.publisher.serialize_telemetry(snapshot, comms_health=comms),
                    heartbeat_json=self.publisher.serialize_heartbeat(
                        snapshot["plant_id"],
                        snapshot["resource_type"],
                        snapshot["device_id"],
                    ),
                )
            )
        return batches

    @staticmethod
    def log_publish_batch(batch: RuntimePublishBatch) -> None:
        print(f"[ESS][{batch.snapshot['device_id']}][telemetry] {batch.telemetry_json}")

    def publish_batch(self, batch: RuntimePublishBatch) -> None:
        wire_fault = _is_wire_fault(batch.snapshot["device_id"])
        comms = "wire_fault" if wire_fault else "ok"
        self.publisher.publish_telemetry(batch.snapshot, comms_health=comms)
        self.publisher.publish_heartbeat(
            batch.snapshot["plant_id"],
            batch.snapshot["resource_type"],
            batch.snapshot["device_id"],
        )

    def run_publish_cycle(self) -> list[RuntimePublishBatch]:
        batches = self.build_publish_batches()
        for batch in batches:
            self.log_publish_batch(batch)
            self.publish_batch(batch)
        return batches

    async def _runtime_loop(self) -> None:
        while not self._stop_event.is_set():
            interval = min(
                (sim.device_spec.publish_interval_sec for sim in self.simulators.values()),
                default=0.5,
            )
            self.run_publish_cycle()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue

    async def _cli_loop(self) -> None:
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

            if result is not None:
                print(result)

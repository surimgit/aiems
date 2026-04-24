import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from domain.device.models import (
    SolarData, Instantaneous, Energy, Status, 
    DeviceState, ControlMode
)
from domain.device.interpolator import TimeSeriesInterpolator
from domain.device.local_safety import SolarLocalSafetyGuard

class SolarDevice:
    def __init__(self, plant_id: str, device_id: str, interpolator: TimeSeriesInterpolator):
        self.plant_id = plant_id
        self.device_id = device_id
        self.interpolator = interpolator

        # State Data
        self.data = SolarData()
        self.reported_state = DeviceState.STANDBY
        self.mode = ControlMode.AUTO
        
        self.emergency_stop = False
        self.local_fault = False
        
        # Curtailment (명세서 5.2)
        self.curtailment_limit_kw = float('inf')

        self.last_update_time = None
        self.max_current_a = 10000.0

        # 로컬 안전 판단 (rule-engine-spec.md §5.3)
        self.safety_guard = SolarLocalSafetyGuard()

    def tick(self, sim_time: datetime, real_time: datetime) -> Optional[Tuple[str, str, str, Dict[str, Any]]]:
        # ── [1] 로컬 안전 판단 (최우선, rule-engine-spec.md §5.3) ────────────
        # safety_guard.check()는 위반 감지 시 device 상태를 직접 변경하고 이벤트를 반환
        safety_event = self.safety_guard.check(self, sim_time, real_time)
        if safety_event:
            # 안전 위반 이벤트가 있으면 물리 계산 생략 후 즉시 반환
            # (실제 P값은 safety_guard 내부에서 curtailment_limit 조정으로 반영됨)
            return safety_event

        # ── [2] 물리 발전량 계산 ─────────────────────────────────────────────
        # 발전량 계산 (W -> kW)
        raw_p = self.interpolator.get_interpolated_value(sim_time) / 1000.0
        
        # 출력 제한 적용 (Curtailment)
        actual_p = min(raw_p, self.curtailment_limit_kw)

        if self.mode == ControlMode.AUTO and not self.local_fault and not self.emergency_stop:
            if actual_p > 0:
                self.reported_state = DeviceState.GENERATING
            else:
                self.reported_state = DeviceState.STANDBY

        if self.reported_state != DeviceState.GENERATING:
            actual_p = 0.0

        v_val = 380.0
        i_val = (actual_p * 1000.0) / v_val if actual_p > 0 else 0.0

        # ── [3] 과전류 감지 (기존 로직 유지) ─────────────────────────────────
        event_data = None
        if not self.local_fault and not self.emergency_stop:
            if i_val > self.max_current_a:
                self.local_fault = True
                self.reported_state = DeviceState.FAULT
                event_data = (
                    "OVER_CURRENT",
                    "EMERGENCY",
                    f"과전류({i_val:.2f}A) 발생으로 차단되었습니다.",
                    {"current_a": i_val, "threshold_a": self.max_current_a}
                )
                actual_p = 0.0
                i_val = 0.0

        # Update Energy & Data
        if self.last_update_time:
            hours_diff = (real_time - self.last_update_time).total_seconds() / 3600.0
            self.data.energy.kWh += actual_p * hours_diff

        self.last_update_time = real_time
        self.data.instantaneous.P = round(actual_p, 2)
        self.data.instantaneous.V = v_val
        self.data.instantaneous.I = round(i_val, 3)
        self.data.instantaneous.S = round(actual_p, 2)
        
        return event_data

    def execute_command(self, cmd: dict, current_time: datetime) -> Tuple[str, Optional[str]]:
        cmd_type = cmd.get("command_type")
        payload = cmd.get("payload", {})
        
        # ── 로컬 안전 선검증 (rule-engine-spec.md §5.3 마지막 조건) ──────────
        # RESET 명령은 안전 차단 대상에서 제외 (복구 목적)
        if cmd_type != "mode_change" and (self.local_fault or self.emergency_stop):
            return "rejected", (
                f"LOCAL_SAFETY_BLOCKED: device is in {self.reported_state.value} state. "
                "Send mode_change/RESET to recover."
            )

        result = "rejected"
        reason = None

        if cmd_type == "curtailment":
            limit = payload.get("limit_kw")
            if limit is not None:
                self.curtailment_limit_kw = float(limit)
                result = "accepted"
            else:
                reason = "MISSING_LIMIT_KW"

        elif cmd_type == "clear_curtailment":
            self.curtailment_limit_kw = float('inf')
            result = "accepted"
        
        # 공통 명령어 처리
        elif cmd_type == "mode_change":
            action = payload.get("action")
            if action == "RESET":
                self.local_fault = False
                self.emergency_stop = False
                self.curtailment_limit_kw = float('inf')
                self.reported_state = DeviceState.STANDBY
                # 로컬 안전 가드 내부 상태도 초기화
                self.safety_guard._freq_curtail_active = False
                self.safety_guard._comms_timeout_reported = False
                self.safety_guard._night_standby_reported = False
                result = "accepted"
        else:
            reason = f"UNKNOWN_COMMAND_TYPE: {cmd_type}"

        return result, reason

    def notify_comms_alive(self):
        """EMS와의 통신이 살아있음을 알림 (LocalSafetyGuard의 타임아웃 타이머 리셋)"""
        self.safety_guard.notify_comms_alive()

    def get_telemetry(self, current_time: datetime) -> SolarData:
        return self.data

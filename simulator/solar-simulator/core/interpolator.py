import math
import random
from datetime import datetime
from abc import ABC, abstractmethod

# --- 추후 확장성을 위한 추상 베이스 클래스 ---
class SolarDataProvider(ABC):
    @abstractmethod
    def get_value(self, target_time: datetime) -> float:
        pass

# --- 물리 기반 태양광 발전 동적 생성기 ---
class PhysicsSolarGenerator(SolarDataProvider):
    def __init__(self, max_capacity_kw: float = 500.0, latitude: float = 37.5665):
        self.max_capacity_kw = max_capacity_kw
        self.latitude = math.radians(latitude)
        
        # 외부에서 동적으로 제어할 수 있는 상태 변수 (명령어/MCP를 통한 조작 대상)
        self.cloud_cover = 0.0     # 운량 (0.0=맑음 ~ 1.0=흐림)
        self.temperature_c = 15.0  # 대기 온도 (섭씨)
        self.efficiency_multiplier = 1.0 # 인위적 출력 제한 등 외부 효율 강제 적용 계수

    def set_conditions(self, cloud_cover: float = None, temperature_c: float = None, efficiency: float = None):
        """MCP나 외부 텍스트 명령어로 호출하여 발전 환경을 실시간으로 변경합니다."""
        if cloud_cover is not None:
            # 운량은 0.0 ~ 1.0 사이로 제한
            self.cloud_cover = max(0.0, min(1.0, cloud_cover))
        if temperature_c is not None:
            self.temperature_c = temperature_c
        if efficiency is not None:
            self.efficiency_multiplier = max(0.0, efficiency)

    def get_value(self, target_time: datetime) -> float:
        # 1. 시각 계산 (0 ~ 24)
        current_hour = target_time.hour + (target_time.minute / 60.0) + (target_time.second / 3600.0)
        
        # 2. 1년 중 특성 (계절별 태양 고도 반영용 적위 계산)
        # Julian Day 식별 (1월 1일 = 1)
        day_of_year = target_time.timetuple().tm_yday
        # 태양 적위 곡선 (Solar Declination): -23.45 ~ +23.45 도
        declination = math.radians(23.45 * math.sin(math.radians((360 / 365.25) * (day_of_year - 81))))
        
        # 3. 시간각 (Hour Angle): 정오(12시)를 0으로 기준, 시간당 15도씩 회전
        hour_angle = math.radians(15.0 * (current_hour - 12.0))
        
        # 4. 태양 고도각 (Elevation Angle) 연산. 음수면 해가 진 것.
        # sin(El) = sin(Lat)*sin(Dec) + cos(Lat)*cos(Dec)*cos(HA)
        sin_elevation = (math.sin(self.latitude) * math.sin(declination) +
                         math.cos(self.latitude) * math.cos(declination) * math.cos(hour_angle))
        
        # math.asin domain error 방지
        sin_elevation = max(-1.0, min(1.0, sin_elevation))
        elevation = math.asin(sin_elevation)
        elevation_deg = math.degrees(elevation)

        if elevation_deg <= 0:
            return 0.0  # 야간
        
        # 5. Clear Sky 기반 기본 발전비율 계산 (고도각에 비례)
        # 고도각이 높을수록 1.0에 가까워짐
        base_power_ratio = math.sin(elevation)
        
        # 6. 날씨 변수 페널티 (Weather Derating)
        # 6.1 구름(운량) 감쇠: 구름이 1.0(100%) 껴도 산란광 등으로 약 20%는 발전됨
        cloud_factor = 1.0 - (self.cloud_cover * 0.8)
        
        # 6.2 온도 저하 (Temperature Derating)
        # 패널 온도 수식: 패널 표면 온도 = 대기온도 + (고도각비례 일사량 * 30)
        cell_temperature = self.temperature_c + (base_power_ratio * 30.0)
        temp_factor = 1.0
        if cell_temperature > 25.0:
            # 25도 초과 시 1도당 효율 0.4% 하락 (기본적인 결정질 실리콘 온도계수)
            temp_factor -= (cell_temperature - 25.0) * 0.004
            temp_factor = max(0.5, temp_factor) # 페널티 하한선 설정
            
        # 7. 노이즈 및 최종 출력 결합
        noise_factor = random.uniform(0.98, 1.02)
        power_ratio = base_power_ratio * cloud_factor * temp_factor * self.efficiency_multiplier * noise_factor

        return self.max_capacity_kw * max(0.0, power_ratio)


# --- 기존 코드와의 호환성 및 제어 권한을 제공하는 래퍼 클래스 ---
class TimeSeriesInterpolator:
    """
    내부적으로 PhysicsSolarGenerator를 사용하여 동적으로 전력을 생성하고,
    생성기 상태(구름, 온도)를 조절할 수 있는 인터페이스를 개방합니다.
    """
    def __init__(self, _unused_path: str = None):
        self.provider = PhysicsSolarGenerator(
            max_capacity_kw=800.0,
            latitude=37.5665 # 서울 중심 위도
        )

    def set_environment(self, cloud_cover: float = None, temperature_c: float = None, efficiency: float = None):
        """
        [새로운 기능] 외부(예: command_handler)에서 해당 함수를 호출하여
        시뮬레이터의 실시간 발전 조건(구름량, 온도, 효율)을 변경할 수 있습니다.
        """
        self.provider.set_conditions(cloud_cover, temperature_c, efficiency)

    def get_first_time(self) -> datetime:
        return datetime.now()

    def get_interpolated_value(self, target_time: datetime) -> float:
        # Watt 단위 반환
        return self.provider.get_value(target_time) * 1000.0

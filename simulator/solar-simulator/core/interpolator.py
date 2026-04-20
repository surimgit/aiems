import math
import random
from datetime import datetime
from abc import ABC, abstractmethod

# --- 추후 확장성을 위한 추상 베이스 클래스 ---
class SolarDataProvider(ABC):
    @abstractmethod
    def get_value(self, target_time: datetime) -> float:
        pass

# --- 3번 방식: 수학적 모델 기반 동적 생성기 ---
class SolarModelGenerator(SolarDataProvider):
    def __init__(self, max_capacity_kw: float = 500.0):
        self.max_capacity_kw = max_capacity_kw
        self.sunrise_hour = 6.0  # 일출 (오전 6시)
        self.sunset_hour = 19.0   # 일몰 (오후 7시)
        
        # 날씨 변화 시뮬레이션을 위한 내부 상태
        self.weather_factor = 1.0  # 1.0=맑음, 0.5=흐림, 0.1=비
        self.last_update_hour = -1

    def _update_weather_randomly(self, current_hour: float):
        """매 시간마다 날씨가 조금씩 변할 확률을 둡니다."""
        if int(current_hour) != self.last_update_hour:
            # 20% 확률로 날씨가 변함
            if random.random() < 0.2:
                self.weather_factor = random.uniform(0.3, 1.0)
            self.last_update_hour = int(current_hour)

    def get_value(self, target_time: datetime) -> float:
        # 시간 단위로 변환 (예: 14시 30분 -> 14.5)
        current_hour = target_time.hour + (target_time.minute / 60.0) + (target_time.second / 3600.0)

        # 해가 떠있는 시간이 아니면 0.0 (밤)
        if current_hour < self.sunrise_hour or current_hour > self.sunset_hour:
            return 0.0

        # 일조 시간을 0 ~ 1 사이의 진행률로 계산
        daylight_duration = self.sunset_hour - self.sunrise_hour
        progress = (current_hour - self.sunrise_hour) / daylight_duration

        # 사인 곡선: 정오(progress=0.5)일 때 sin(pi/2) = 1 (최대값)
        # 약간의 가우시안 효과를 위해 제곱을 사용하여 곡선을 더 현실적으로(뾰족하게) 만듦
        base_curve = math.sin(progress * math.pi) ** 1.5

        # 랜덤 노이즈 추가 (±3%)
        noise = random.uniform(0.97, 1.03)

        # 날씨 상태 업데이트
        self._update_weather_randomly(current_hour)

        # 최종 발전량 계산
        return self.max_capacity_kw * base_curve * self.weather_factor * noise

# --- 기존 코드와의 호환성을 위한 래퍼 클래스 ---
class TimeSeriesInterpolator:
    """
    기존 main.py에서 호출하는 인터페이스를 유지하면서 
    내부적으로 Generator를 사용하여 무한 데이터를 생성합니다.
    """
    def __init__(self, _unused_path: str = None):
        # 나중에 실제 데이터로 바꾸고 싶으면 다른 Provider로 교체만 하면 됩니다.
        self.provider = SolarModelGenerator(max_capacity_kw=800.0)

    def get_first_time(self) -> datetime:
        # 동적 생성이므로 시작 시점은 '현재'를 반환하여 즉시 시작되게 합니다.
        return datetime.now()

    def get_interpolated_value(self, target_time: datetime) -> float:
        # 3.3kW(3300W) 데이터 이슈를 방지하기 위해 
        # SolarDevice.tick에서 /1000 처리를 하므로, 여기서는 Watt 단위로 반환합니다.
        # 만약 이미 kW 단위가 필요하다면 이 값을 그대로 사용하세요.
        return self.provider.get_value(target_time) * 1000.0

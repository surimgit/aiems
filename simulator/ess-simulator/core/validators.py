from __future__ import annotations


# 퍼센트 계열 값이 0~100 범위 안에 있는지 검증한다.
def validate_percent_range(value: float, name: str) -> None:
    if not 0 <= value <= 100:
        raise ValueError(f"{name} must be between 0 and 100")


# 양수여야 하는 값을 검증한다.
def validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


# low/high 형태의 임계값 쌍이 올바른 순서를 가지는지 검증한다.
def validate_threshold_pair(low: float, high: float, low_name: str, high_name: str) -> None:
    validate_percent_range(low, low_name)
    validate_percent_range(high, high_name)
    if low >= high:
        raise ValueError(f"{low_name} must be lower than {high_name}")

from config import REDIS_NORMAL_STREAM, REDIS_EMERGENCY_STREAM


def classify(message_type: str) -> str:
    if message_type == "emergency":
        return REDIS_EMERGENCY_STREAM
    return REDIS_NORMAL_STREAM

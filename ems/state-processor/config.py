import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

REDIS_NORMAL_STREAM = "ems:normal"
REDIS_STATE_STREAM = "ems:state"

CONSUMER_GROUP = "state-processor-group"
CONSUMER_NAME = "state-processor-1"

STATE_TTL_SECONDS = 60

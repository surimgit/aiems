import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")

REDIS_NORMAL_STREAM = "ems:normal"
REDIS_EMERGENCY_STREAM = "ems:emergency"
REDIS_STATE_STREAM = "ems:state"

CONSUMER_GROUP = "state-processor-group"
CONSUMER_NAME = "state-processor-1"

STATE_TTL_SECONDS = 60

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "emsdb")
DB_USER = os.getenv("DB_USER", "ems")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ems1234")

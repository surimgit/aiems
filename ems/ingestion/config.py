import os

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

REDIS_NORMAL_STREAM = "ems:normal"
REDIS_EMERGENCY_STREAM = "ems:emergency"

STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", 10000))

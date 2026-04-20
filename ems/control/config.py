import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")

CONTROL_INTERVAL_SECONDS = 1.0

SOC_LOW = 20.0
SOC_HIGH = 90.0

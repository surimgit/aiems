import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")

CONTROL_INTERVAL_SECONDS = 1.0

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "emsdb")
DB_USER = os.getenv("DB_USER", "ems")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ems1234")

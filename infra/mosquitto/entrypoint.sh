#!/bin/sh
# mosquitto 기동 시 MQTT_USER / MQTT_PASSWORD 환경변수로 passwd / acl 파일 생성
set -e

if [ -z "${MQTT_USER}" ] || [ -z "${MQTT_PASSWORD}" ]; then
    echo "[mosquitto] ERROR: MQTT_USER / MQTT_PASSWORD 환경변수가 비어있음" >&2
    exit 1
fi

PASSWD_FILE=/mosquitto/config/passwd
ACL_TEMPLATE=/mosquitto/config/acl.template
ACL_FILE=/mosquitto/config/acl

mosquitto_passwd -b -c "${PASSWD_FILE}" "${MQTT_USER}" "${MQTT_PASSWORD}"

sed "s|\${MQTT_USER}|${MQTT_USER}|g" "${ACL_TEMPLATE}" > "${ACL_FILE}"

# mosquitto 프로세스는 기동 후 mosquitto 유저로 권한을 낮추므로
# passwd/acl 은 해당 유저가 읽을 수 있어야 함.
chown mosquitto:mosquitto "${PASSWD_FILE}" "${ACL_FILE}"
chmod 0640 "${PASSWD_FILE}" "${ACL_FILE}"

exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf

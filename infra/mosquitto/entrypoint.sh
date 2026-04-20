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
chmod 0700 "${PASSWD_FILE}"

sed "s|\${MQTT_USER}|${MQTT_USER}|g" "${ACL_TEMPLATE}" > "${ACL_FILE}"

exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf

#!/usr/bin/env bash
# EMS DB 복구 스크립트
# 사용법:
#   ./restore.sh postgres 2026-04-30                # 해당 날짜의 가장 최근 PostgreSQL 백업 복구
#   ./restore.sh postgres 2026-04-30 20260430-143146 # 특정 시각 백업 복구
#   ./restore.sh timescale 2026-04-30
#
# ⚠️ 주의: 기존 DB 가 통째로 덮어씀. 운영 DB 에 직접 실행 금지.
# 먼저 별도 검증용 DB 컨테이너에서 테스트 후 운영에 적용 권장.
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "사용법: $0 <postgres|timescale> <YYYY-MM-DD> [TIMESTAMP]"
    echo "예시:   $0 postgres 2026-04-30"
    echo "        $0 timescale 2026-04-30 20260430-143146"
    exit 1
fi

TARGET="$1"   # postgres | timescale
DATE="$2"
TIMESTAMP_FILTER="${3:-}"

S3_BUCKET="ssafy-s305-ems-backup"
ENV_FILE="/home/ubuntu/app/.env"
WORK_DIR="/tmp/ems-restore-$$"
mkdir -p "${WORK_DIR}"
trap "rm -rf ${WORK_DIR}" EXIT

# shellcheck disable=SC1090
source "${ENV_FILE}"

case "${TARGET}" in
    postgres)
        CONTAINER="app-postgres-1"
        S3_PREFIX="postgres/${DATE}/"
        PASS="${POSTGRES_ROOT_PASSWORD}"
        ;;
    timescale)
        CONTAINER="app-timescaledb-1"
        S3_PREFIX="timescale/${DATE}/"
        PASS="${TIMESCALE_ROOT_PASSWORD}"
        ;;
    *)
        echo "ERROR: TARGET 은 postgres 또는 timescale 이어야 함"
        exit 1
        ;;
esac

echo "[restore] S3 에서 백업 파일 검색: s3://${S3_BUCKET}/${S3_PREFIX}"

if [ -n "${TIMESTAMP_FILTER}" ]; then
    BACKUP_FILE=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}" \
        | grep "${TIMESTAMP_FILTER}" \
        | awk '{print $NF}' | tail -n 1)
else
    BACKUP_FILE=$(aws s3 ls "s3://${S3_BUCKET}/${S3_PREFIX}" \
        | awk '{print $NF}' | sort | tail -n 1)
fi

if [ -z "${BACKUP_FILE}" ]; then
    echo "ERROR: 해당 날짜/시각의 백업 파일 없음"
    exit 1
fi

echo "[restore] 복구 대상: ${BACKUP_FILE}"

read -r -p "정말 복구하시겠습니까? 기존 DB 가 덮어쓰입니다. (yes/no): " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "[restore] 취소됨"
    exit 0
fi

echo "[restore] S3 에서 다운로드 중..."
aws s3 cp "s3://${S3_BUCKET}/${S3_PREFIX}${BACKUP_FILE}" "${WORK_DIR}/"

LOCAL_FILE="${WORK_DIR}/${BACKUP_FILE}"
echo "[restore] gunzip 압축 해제..."
gunzip "${LOCAL_FILE}"
SQL_FILE="${LOCAL_FILE%.gz}"

echo "[restore] DB 컨테이너 에 복구 적용 (${CONTAINER})"
sudo docker exec -i -e PGPASSWORD="${PASS}" "${CONTAINER}" \
    psql -U postgres < "${SQL_FILE}"

echo "[restore] 복구 완료. DB 검증 권장:"
echo "  sudo docker exec ${CONTAINER} psql -U postgres -c '\\l'"

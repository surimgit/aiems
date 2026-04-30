#!/usr/bin/env bash
# EMS DB 일일 백업 스크립트
# - PostgreSQL 3 DB (state_write_db, ai_db, control_db) → pg_dumpall
# - TimescaleDB (timescale_db) → pg_dump
# - gzip 압축 → S3 업로드
# - 7일 retention 은 S3 lifecycle 정책으로 자동 처리
#
# 배포 위치: DB EC2 의 /opt/ems-backup/backup.sh
# cron 등록: 0 3 * * * /opt/ems-backup/backup.sh >> /var/log/ems-backup/cron.log 2>&1
# IAM Role:  ems-db-backup-role (DB EC2 에 부착, S3 PutObject/GetObject/ListBucket/DeleteObject)
set -euo pipefail

# ===== 설정 =====
S3_BUCKET="ssafy-s305-ems-backup"
ENV_FILE="/home/ubuntu/app/.env"
WORK_DIR="/tmp/ems-backup-$$"
LOG_DIR="/var/log/ems-backup"
DATE=$(date +%Y-%m-%d)
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="${LOG_DIR}/backup-${DATE}.log"

POSTGRES_CONTAINER="app-postgres-1"
TIMESCALE_CONTAINER="app-timescaledb-1"

# ===== 사전 준비 =====
sudo mkdir -p "${LOG_DIR}"
sudo chown ubuntu:ubuntu "${LOG_DIR}"
mkdir -p "${WORK_DIR}"
trap "rm -rf ${WORK_DIR}" EXIT

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

# ===== .env 로드 (root 비밀번호) =====
if [ ! -f "${ENV_FILE}" ]; then
    log "ERROR: .env 파일 없음: ${ENV_FILE}"
    exit 1
fi
# shellcheck disable=SC1090
source "${ENV_FILE}"

log "===== EMS 백업 시작 (${TIMESTAMP}) ====="

# ===== 1. PostgreSQL 3 DB 백업 =====
log "[1/2] PostgreSQL pg_dumpall 시작"
PG_DUMP_FILE="${WORK_DIR}/postgres-${TIMESTAMP}.sql"
sudo docker exec -e PGPASSWORD="${POSTGRES_ROOT_PASSWORD}" \
    "${POSTGRES_CONTAINER}" \
    pg_dumpall -U postgres --clean --if-exists \
    > "${PG_DUMP_FILE}"

PG_SIZE=$(du -h "${PG_DUMP_FILE}" | cut -f1)
log "  덤프 완료 (${PG_SIZE})"

log "  gzip 압축 중..."
gzip -9 "${PG_DUMP_FILE}"
PG_DUMP_GZ="${PG_DUMP_FILE}.gz"
PG_GZ_SIZE=$(du -h "${PG_DUMP_GZ}" | cut -f1)
log "  압축 완료 (${PG_GZ_SIZE})"

log "  S3 업로드 중..."
aws s3 cp "${PG_DUMP_GZ}" "s3://${S3_BUCKET}/postgres/${DATE}/" \
    --storage-class STANDARD
log "  PostgreSQL 백업 완료 → s3://${S3_BUCKET}/postgres/${DATE}/$(basename ${PG_DUMP_GZ})"

# ===== 2. TimescaleDB 백업 =====
log "[2/2] TimescaleDB pg_dump 시작"
TS_DUMP_FILE="${WORK_DIR}/timescale-${TIMESTAMP}.sql"
sudo docker exec -e PGPASSWORD="${TIMESCALE_ROOT_PASSWORD}" \
    "${TIMESCALE_CONTAINER}" \
    pg_dump -U postgres --clean --if-exists --format=plain "${TIMESCALE_DB}" \
    > "${TS_DUMP_FILE}"

TS_SIZE=$(du -h "${TS_DUMP_FILE}" | cut -f1)
log "  덤프 완료 (${TS_SIZE})"

log "  gzip 압축 중..."
gzip -9 "${TS_DUMP_FILE}"
TS_DUMP_GZ="${TS_DUMP_FILE}.gz"
TS_GZ_SIZE=$(du -h "${TS_DUMP_GZ}" | cut -f1)
log "  압축 완료 (${TS_GZ_SIZE})"

log "  S3 업로드 중..."
aws s3 cp "${TS_DUMP_GZ}" "s3://${S3_BUCKET}/timescale/${DATE}/" \
    --storage-class STANDARD
log "  TimescaleDB 백업 완료 → s3://${S3_BUCKET}/timescale/${DATE}/$(basename ${TS_DUMP_GZ})"

log "===== EMS 백업 정상 종료 ====="

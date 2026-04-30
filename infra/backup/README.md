# EMS DB 백업/복구

## 개요

DB EC2 의 PostgreSQL + TimescaleDB 를 매일 새벽 3시 (KST) S3 에 자동 백업.
7일 retention 은 S3 lifecycle 정책으로 자동 처리.

## 인프라

| 항목 | 값 |
|------|-----|
| S3 버킷 | `ssafy-s305-ems-backup` |
| 리전 | `ap-northeast-2` (서울) |
| IAM Role | `ems-db-backup-role` (DB EC2 에 부착) |
| IAM Policy | `ems-s3-backup-policy` |
| Retention | 7일 (S3 lifecycle) |
| 압축 | gzip -9 |

## S3 폴더 구조

```
s3://ssafy-s305-ems-backup/
├── postgres/
│   ├── 2026-04-30/
│   │   └── postgres-20260430-030001.sql.gz
│   └── 2026-05-01/
│       └── postgres-20260501-030001.sql.gz
└── timescale/
    ├── 2026-04-30/
    │   └── timescale-20260430-030001.sql.gz
    └── 2026-05-01/
        └── timescale-20260501-030001.sql.gz
```

## 배포

DB EC2 의 `/opt/ems-backup/` 에 `backup.sh`, `restore.sh` 배치.
cron 등록:

```cron
# EMS DB 백업 (매일 새벽 3시 KST)
0 3 * * * /opt/ems-backup/backup.sh >> /var/log/ems-backup/cron.log 2>&1
```

## 사용법

### 백업 (수동)

```bash
ssh ubuntu@<DB_EC2_PUBLIC_IP>
/opt/ems-backup/backup.sh
```

### 백업 확인

```bash
aws s3 ls s3://ssafy-s305-ems-backup/postgres/$(date +%Y-%m-%d)/
aws s3 ls s3://ssafy-s305-ems-backup/timescale/$(date +%Y-%m-%d)/
cat /var/log/ems-backup/backup-$(date +%Y-%m-%d).log
```

### 복구

```bash
ssh ubuntu@<DB_EC2_PUBLIC_IP>

# PostgreSQL 복구 (해당 날짜 가장 최근 백업)
/opt/ems-backup/restore.sh postgres 2026-04-30

# 특정 시각 백업으로 복구
/opt/ems-backup/restore.sh postgres 2026-04-30 20260430-030001

# TimescaleDB 복구
/opt/ems-backup/restore.sh timescale 2026-04-30
```

⚠️ **운영 DB 에 직접 복구하지 말 것.** 별도 검증 컨테이너에서 테스트 후 적용 권장.

## 모니터링

현재 알림 X. 운영 중 점검:

```bash
# 어제 백업 로그
cat /var/log/ems-backup/backup-$(date -d yesterday +%Y-%m-%d).log

# S3 사용량
aws s3 ls --summarize --human-readable --recursive s3://ssafy-s305-ems-backup/
```

추후 모니터링 스택 (Prometheus + Grafana) 구축 시 통합 예정.

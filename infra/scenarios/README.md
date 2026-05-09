# 시나리오 정책 시드

마이크로그리드 환경별로 EMS 운영 정책 (control_policy) 시드 SQL 모음.

## 적용 방법

```bash
# 시나리오 적용
docker exec -i s14p31s305-ems-postgres-1 psql -U postgres -d control_db < infra/scenarios/manjae.sql

# 또는 control_user 권한으로
docker exec -i s14p31s305-ems-postgres-1 psql -U control_user -d control_db < infra/scenarios/manjae.sql
```

## 시나리오 목록

| 파일 | 설명 | 출처 문서 |
|---|---|---|
| `manjae.sql` | 도서지역(만재도) 하이브리드 마이크로그리드 | `세영마이크로그리드.md` |

## 적용 후 확인

```sql
-- 적용된 정책 확인
SELECT key, value, unit, description FROM control_policy ORDER BY key;

-- 부하 우선순위 확인
SELECT key, value FROM control_policy WHERE key LIKE 'LOAD_PRIORITY_%';
```

## 기본 정책으로 복원

`infra/init_postgres.sh` 의 시드를 다시 적용하려면 컨테이너 재기동 후
시드 스크립트를 수동 실행하거나, 아래 백업 시드를 적용:

```bash
docker exec -i s14p31s305-ems-postgres-1 psql -U postgres -d control_db < infra/scenarios/_default.sql
```

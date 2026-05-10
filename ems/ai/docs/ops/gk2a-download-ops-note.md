# GK2A Download Ops Note

Last updated: 2026-05-04 KST

## Scope

- 대상 스크립트:
  - `ems/ai/scripts/collect_gk2a_le2_archive.py`
  - `ems/ai/scripts/run_gk2a_le2_archive_monthly.py`
- 대상 설정:
  - `ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml`
- 저장 경로:
  - `G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2`

## What This Download Is

- 이 수집은 엑셀/CSV가 아니라 `.nc` NetCDF/HDF5 바이너리 원본 다운로드다.
- 설정 기준:
  - 기간: `2025-01-01 00:00+09:00 ~ 2025-12-31 23:00+09:00`
  - 주기: `1시간`
  - 영역: `KO`
  - 상품: `CLA`, `CLD`
- 연간 기대 파일 수:
  - `365 * 24 * 2 = 17,520`
- 파일 헤더 샘플:
  - first bytes: `89 48 44 46`
  - meaning: HDF5-based binary payload

## Size Reality

- `.nc`는 숫자 몇 줄짜리 표가 아니라 격자 전체를 담는 바이너리다.
- 1파일 평균 크기 관측값:
  - 약 `0.67 MB`
- 중간 관측 총량:
  - 약 `9 GB`
- 따라서 연간 `10~12 GB` 수준은 이상하지 않다.

## Confirmed Runtime Behavior

- `collect_gk2a_le2_archive.py`
  - 성공 시 `.part`를 최종 `.nc`로 rename
  - 실패 시 `.part` 삭제
  - 실패 항목은 manifest에만 `FAILED` 기록
- 따라서 `404` 실패 시점은 빈 파일이 남지 않고 실제 파일이 없는 hole 상태가 된다.

## Confirmed Failure Pattern

- 일부 `CLA` 시각에서 `404 Client Error: Not Found`가 실제로 관측됨.
- 예시:
  - `2025-07-31 22:00`
  - `2025-08-31 21:00`
  - `2025-08-31 22:00`
  - `2025-08-31 23:00`
- 이런 실패는 자동으로 placeholder를 만들지 않는다.
- 같은 기간을 다시 실행하면, 없는 파일만 다시 다운로드 시도 대상이 된다.

## Why Restart Was Slow

- 원인:
  - `G:` 드라이브 메타데이터 순회 비용
  - 기존 로직은 재시작 시 월별 subprocess를 1월부터 다시 태움
  - 이미 존재하는 파일도 존재 확인 비용이 누적됨
- 핵심:
  - CPU 계산이 아니라 파일 시스템 I/O와 동기화 드라이브 metadata scan이 병목이다.

## Applied Change

- `run_gk2a_le2_archive_monthly.py`를 다음 방식으로 수정함:
  - 월별 `expected_records` 계산
  - 월 폴더 내 `.nc` 개수만 먼저 셈
  - 이미 다 찬 달은 subprocess를 아예 실행하지 않음
  - `--start-month`를 안 주면 `첫 미완료 달`부터 자동 재개
- 의도:
  - 재시작 때 1월부터 전체 API/file loop를 다시 도는 비용 제거

## Operational Interpretation

- process가 살아 있어도 곧바로 새 `.nc`가 생긴다는 뜻은 아니다.
- 먼저 월별 완료 여부를 보고, 미완료 달이 나오면 그 달부터 실제 다운로드를 시작한다.
- 그래서 재시작 직후에는:
  - process alive
  - manifest updated
  - new `.nc` not yet written
  상태가 잠시 발생할 수 있다.

## Logs To Check

- 운영 로그 디렉터리:
  - `C:/Users/tkatn/PycharmProjects/S14P31S305/ems/ai/logs`
- 예시 파일:
  - `gk2a_single_run*.log`
  - `gk2a_restart_*.log`
  - `gk2a_monthloop_*.log`

## Folder Paths To Inspect Manually

- root:
  - `G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2`
- product paths:
  - `G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2/CLA/KO/2025`
  - `G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2/CLD/KO/2025`
- manifests:
  - `G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2/manifests`

## Known Good Manual Checks

- 새 다운로드가 실제로 진행 중인지 보려면:
  - 최신 `.nc` 파일 `LastWriteTime`
  - 최신 manifest `LastWriteTime`
  - 로그 tail
  - running python process
- APIHub 호출 횟수 UI가 비어 있어도:
  - manifest 갱신만으로는 충분하지 않음
  - 새 `.nc` 생성 또는 기존 최신 파일 시각 갱신이 있어야 다운로드 진행으로 판단

## Recommended Next Step

- 최적화 1:
  - 월별 파일 수 cache 또는 manifest 기반 완료 cache 추가
- 최적화 2:
  - `FAILED` / missing timestamp만 재시도하는 별도 스크립트 작성
- 최적화 3:
  - 재시작 시 `첫 미완료 달`보다 더 좁게 `실패가 많던 달`부터 시작 가능하게 옵션화

## 2026-05-04 Incident Note

- Runtime policy used in this run:
  - `404` -> permanent missing (`SKIPPED_404`)
  - `200` -> save `.nc`
  - retriable timeout / `5xx` -> retry up to 2 extra times
- A mixed foreground probe proved the missing list was mixed:
  - many early `2025-08` `CLA` gaps were true `404`
  - several `2025-11` gaps returned `200` and downloaded normally
- Because of that, a whole-list background retry looked stuck whenever it spent a long time inside a dense `404` region.

## Chunked Retry Strategy

- Added runner:
  - `ems/ai/scripts/run_gk2a_missing_chunks.py`
- Worker:
  - `ems/ai/scripts/retry_missing_gk2a_le2.py`
- Source list:
  - `ems/ai/logs/gk2a_missing_202508_202512.jsonl`
- Run mode used:
  - sequential chunks
  - `chunk-size = 200`
  - `extra-attempts = 2`

## APIHub Limit / Ban Suspicion

- Downloads progressed normally for a while, then repeated `403 Forbidden` appeared.
- Around the same time, APIHub web access also failed from the current network.
- User-observed APIHub counters:
  - calls: about `1824 / 20000`
  - usage: about `5.00626 / 5 GB`
- Operational interpretation:
  - likely daily transfer quota exhaustion and/or temporary IP-based blocking
  - not an `.env` loading bug
  - not a local disk write bug

## Stop / Resume Rule

- Stop the current runner when:
  - repeated `403 Forbidden` starts appearing
  - APIHub site/API is no longer reachable from the current network
- Resume on the next day or after cooldown.
- Important:
  - files that were downloaded before the `403` event are done
  - files that failed after `403` must be retried later
  - `404` entries stay as permanent missing unless upstream behavior changes

## Snapshot At Stop Time

- local `.nc` files: `15,550 / 17,520`
- nominal remaining count: `1,970`
- note:
  - this remaining count still includes permanent `404` holes
  - real downloadable remaining count should be smaller after the next retry pass

# KPI 데이터 계약 요청서 (시뮬레이터/백엔드 담당자용)

## 목적
- 프론트 KPI를 추정치가 아닌 **월 누적 실측 기준**으로 고정하기 위해 필요한 데이터 계약을 정리한다.

## 현재 프론트 구현 상태
- 총 발전량: `SOLAR + DIESEL_GENERATOR` 실시간 `p_kw` 적분(MTD)
- 총 소비량: `LOAD p_kw` 적분(MTD)
- 자립률: `(1 - grid_import_kwh / consumption_kwh) * 100`
- 비용절감: `local_supply_kwh * tariff(150원/kWh)`
- 참고: 태양광 예상 기준치(설치용량×3.5h×경과일) 보조 표기

## 필요한 데이터 (우선순위 순)
1. 월 누적 전력량(kWh) 실측값
   - 장비별 `monthly_generation_kwh`, `monthly_consumption_kwh`, `monthly_grid_import_kwh`, `monthly_grid_export_kwh`
   - 기준 월: KST 00:00~말일 23:59
2. 장비 누적 계량기 값(kWh)
   - `lifetime_kwh` 또는 `meter_total_kwh`
   - 리셋 정책(재기동/월초) 명시 필요
3. 설치용량(capacity)
   - 특히 SOLAR `installed_capacity_kw`
4. 부호 규칙
   - `p_kw`의 +/− 의미를 리소스 타입별로 문서화
5. 데이터 신뢰 플래그
   - `quality`, `is_estimated`, `source` (meter/simulated/inferred)

## 제안 API 계약
### 1) 월 KPI 요약
- `GET /api/plants/{site_id}/kpi/monthly?month=YYYY-MM`

```json
{
  "site_id": "PLANT-ALPHA",
  "month": "2026-05",
  "generation_kwh": 0,
  "consumption_kwh": 0,
  "grid_import_kwh": 0,
  "grid_export_kwh": 0,
  "self_sufficiency_pct": 0,
  "savings_won": 0,
  "tariff_won_per_kwh": 150,
  "quality": "meter"
}
```

### 2) 장비별 월 집계
- `GET /api/plants/{site_id}/resources/monthly-energy?month=YYYY-MM`

```json
[
  {
    "resource_id": "solar-01",
    "resource_type": "SOLAR",
    "generation_kwh": 0,
    "consumption_kwh": 0,
    "grid_import_kwh": 0,
    "grid_export_kwh": 0,
    "installed_capacity_kw": 0,
    "quality": "meter"
  }
]
```

## 확인 요청 질문
1. `telemetry.kwh`는 누적값인지, 월초 리셋인지, 재기동 시 리셋되는지?
2. `DIESEL_GENERATOR`의 실제 발전량은 어떤 필드가 기준인지?
3. `grid_power_kw`는 수입(+) / 수출(-) 규칙이 항상 보장되는지?
4. 월경계 기준 시간대가 KST인지 UTC인지?
5. 시뮬레이터가 의도적으로 jitter/noise를 넣는지?

## 합의 전 임시 규칙 (프론트)
- 월 누적값은 적분 기반으로 유지
- 데이터 단절/재시작 구간은 과적분 방지 상한 적용
- 알람 건수는 비용절감 계산에 절대 사용하지 않음

# AI API 정의서

---

## 1. 목적

본 문서는 Flask AI MSA가 EMS에 제공하는 예측 API 경계를 정의한다.

AI API는 Flask + flask-smorest + Marshmallow Schema를 기준으로 구현하며, OpenAPI 문서는 코드에서 자동 생성한다.

AI API는 예측과 추천 후보를 제공하는 Input adapter이다. 실제 제어 실행은 Control/Rule Engine과 운영자 승인 흐름에서 처리한다.

---

## 2. 문서 제공 경로

| 항목 | 경로 |
| --- | --- |
| Swagger UI | `/docs` |
| OpenAPI JSON | `/openapi.json` |
| Health Check | `/health` |

Docker Compose 기준 서비스 주소:

```text
http://localhost:5004
```

---

## 3. 현재 구현 API

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/ai/models` | 모델 artifact 상태 조회 |
| POST | `/api/ai/site-profile/structure` | 자연어/운영자 설명을 `site_profile.v1`로 구조화 |
| POST | `/api/ai/predict-solar` | 기존 solar kW model feature 직접 예측 |
| POST | `/api/ai/predict-capacity-factor` | legacy tabular capacity factor 기반 태양광 발전 예측 |
| POST | `/api/ai/predict-satellite-capacity-factor` | satellite image tensor/features를 caller가 직접 넣는 태양광 capacity factor 예측 |
| POST | `/api/ai/predict-live-satellite-capacity-factor` | KMA APIHub weather/GK2A area 값을 AI 서비스가 조회해 v10 satellite 모델로 `1h~24h` 예측 |
| POST | `/api/ai/predict-load` | load prior 기반 소비 예측 |
| POST | `/api/ai/forecast` | 발전/소비 통합 forecast. 현재 기본 구현은 legacy capacity-factor + load prior 조합 |

아래 API는 설계상 필요하지만 현재 Flask MSA에는 아직 구현되지 않았다.

| Method | Path | 상태 |
| --- | --- | --- |
| POST | `/api/ai/inference-requests` | 미구현 |
| GET | `/api/ai/inference-results/{inference_id}` | 미구현 |
| GET | `/api/ai/forecasts/{forecast_id}` | 미구현 |
| GET | `/api/ai/recommendations/{recommendation_id}` | 미구현 |
| GET | `/api/plants/{site_id}/ai/latest` | 미구현 |

---

## 4. site_profile.v1 구조화

`POST /api/ai/site-profile/structure`는 운영자 설명을 검증된 `site_profile.v1`로 변환한다.

핵심 요청 필드:

| 필드 | 설명 |
| --- | --- |
| `site_id` | 사이트 ID |
| `site` | 사이트 metadata |
| `text` | 운영자 또는 현장 설명 |
| `profile` | 이미 구조화된 profile을 검증할 때 사용 |
| `use_openai` | OpenAI Responses API 사용 여부 |

응답은 `ok`, `source`, `profile`을 반환한다. OpenAI가 비활성화되거나 key가 없을 때는 rule fallback profile을 사용할 수 있다.

`site_profile.v1`은 예측 prior로만 사용한다. Rule Engine 임계값, 안전 margin, 제어 명령을 직접 생성하지 않는다.

---

## 5. 통합 Forecast

`POST /api/ai/forecast`는 같은 `target_time` 축에서 태양광 발전, 소비, 순부하를 묶어 반환한다.

주의: 현재 코드의 `/api/ai/forecast`는 `ForecastService`가 legacy capacity-factor payload와 load prior를 조합한다. v10 live satellite를 자동으로 `1h~24h` 반복 호출해 저장하는 Forecast-AI 오케스트레이션은 아직 별도 연결 대상이다. 프런트 예측 그래프가 v10 값을 바로 받아야 하면 `/api/ai/predict-live-satellite-capacity-factor`를 horizon별로 호출한다.

최소 horizon 요청 필드:

| 필드 | 설명 |
| --- | --- |
| `site` | `latitude`, `longitude`, `timezone`, `installed_capacity_kw`, `base_load_kw` 포함 |
| `start_time` | 예측 시작 시각 |
| `periods` | 생성할 예측 행 수 |
| `frequency_hours` | 예측 간격. `1`이면 1시간 간격 |

`periods=3`, `frequency_hours=1`이면 1시간 간격 3개 `target_time` 행이 생성된다.

응답 핵심 필드:

| 필드 | 설명 |
| --- | --- |
| `forecasts[].predicted_solar_kw` | capacity factor 기반 태양광 발전 예측 |
| `forecasts[].predicted_load_kw` | load prior 기반 소비 예측 |
| `forecasts[].safe_predicted_load_kw` | safety reserve 포함 소비 예측 |
| `forecasts[].predicted_net_load_kw` | 소비 minus 태양광 |
| `recommendations[].requires_operator_approval` | 운영자 승인 필요 여부 |

추천은 보조 판단 결과이며 제어 명령이 아니다.

---

## 6. v10 Live Satellite 예측

`POST /api/ai/predict-live-satellite-capacity-factor`는 프런트 예측 그래프 또는 Forecast-AI 오케스트레이션이 현재 바로 사용할 수 있는 v10 태양광 예측 API다.

요청 핵심 필드:

| 필드 | 설명 |
| --- | --- |
| `site_id` | 사이트 ID. 없으면 `null` 가능 |
| `region` | 지원 지역. 기본값 `대전시`. 현재 `서울시`, `부산시`, `대전시`, `울산시`, `제주도` |
| `latitude`, `longitude` | 사이트 좌표. 없으면 region 중심좌표 사용 |
| `dong_code` | KMA GK2A area API 행정동 코드. 없으면 region 기본값 사용 |
| `installed_capacity_kw` | 설비용량. 응답의 `predicted_generation_kw` 계산에 사용 |
| `horizon_hours` | `1`부터 `24`까지 |
| `target_time` | ISO-8601 target timestamp. 없으면 현재 KST 정시 + `horizon_hours` |

최소 요청 예:

```json
{
  "region": "대전시",
  "horizon_hours": 24,
  "target_time": "2026-05-09T12:00:00+09:00",
  "installed_capacity_kw": 100
}
```

응답에서 프런트/Control 쪽이 우선 쓰는 필드:

| 필드 | 설명 |
| --- | --- |
| `prediction.predicted_capacity_factor` | v10 capacity factor 예측값 |
| `prediction.predicted_generation_kw` | 설비용량을 곱한 발전량 kW |
| `prediction.model_version` | 모델 버전 |
| `target.target_time` | 예측 대상 시각 |
| `target.horizon_hours` | horizon |
| `warnings` | KMA/GK2A 조회 또는 nearest-time 보정 경고 |
| `satellite.frames[].source_date_time` | 실제 사용된 GK2A product 시각 |

운영 상태:

```text
default model: satellite_wind_safe_multihorizon_24h_v10
checkpoint: ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt
runtime image: tkatnsdl1996/s305-ems-ai-inference:satellite-v10-24h
RunPod task: predict_live_satellite_capacity_factor
```

Control 서비스는 이 API 응답을 제어 명령으로 직접 해석하지 않는다. 필요한 값은 `predicted_generation_kw`, `confidence`, `model_version`, `warnings`를 forecast 저장소나 EMS 판단 입력으로 넘긴다.

## 7. 예측 API 원칙

1. AI API는 추천과 예측 결과를 제공한다.
2. AI API는 제어 명령을 생성하지 않는다.
3. AI 추천 실행은 Control API와 운영자 승인 후 처리한다.
4. `/api/ai/forecast`는 현재 동기 HTTP 응답을 반환한다.
5. Forecast 저장과 조회 API는 `forecast_result` 저장 구현 이후 확정한다.
6. Forecast와 Recommendation 구조는 `10-ai-contracts/`의 계약을 따른다.

---

## 8. OPS 잔여 범위

다음 항목은 현재 API 계약에는 남아 있지만 코드 구현은 완료되지 않았다.

- `forecast_result` 저장
- `forecast_actual_log` 실측 매칭
- forecast 결과 조회 API
- recommendation 상세 조회 API
- Plant 최신 AI 결과 조회 API

---

## 9. 결론

AI API는 예측과 추천 후보를 시스템에 제공하는 경계이다.

실행 권한은 없으며, Control과 운영자 승인 흐름을 통해서만 후속 제어로 이어진다.

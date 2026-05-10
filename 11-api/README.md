# API Guide

이 폴더는 프론트, Control, 외부 서비스가 호출하는 HTTP API 경계를 정리한다.

## AI API

- [AI API 정의서](./ai-api.md)

현재 프론트 예측 그래프 또는 Forecast-AI가 바로 호출할 v10 태양광 endpoint:

```http
POST /api/ai/predict-live-satellite-capacity-factor
```

핵심 응답 필드:

- `prediction.predicted_capacity_factor`
- `prediction.predicted_generation_kw`
- `prediction.model_version`
- `target.target_time`
- `target.horizon_hours`
- `warnings`

Control 서비스는 AI 응답을 직접 제어 명령으로 해석하지 않고, EMS 판단 입력 또는 forecast 저장 대상으로 사용한다.

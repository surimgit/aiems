# EMS AI Service

Flask runtime service for EMS AI prediction.

This folder is the deployable MSA boundary. Offline collection, preprocessing,
and training jobs remain outside this service .

## Run Locally

```bash
cd ems/ai/service
python -m flask --app app.main:app run --host 0.0.0.0 --port 5004
```

## Endpoints

- `GET /health`
- `GET /docs`
- `GET /openapi.json`
- `GET /api/ai/models`
- `POST /api/ai/predict-solar`
- `POST /api/ai/predict-capacity-factor`
- `POST /api/ai/forecast`

## Bundled Forecast Request

`/api/ai/forecast` can build solar and load forecasts on the same target
timeline from one request.

```json
{
  "site_id": "PLANT-ALPHA",
  "site": {
    "site_id": "PLANT-ALPHA",
    "region": "daejeon",
    "latitude": 36.3504,
    "longitude": 127.3845,
    "timezone": "Asia/Seoul",
    "installed_capacity_kw": 1000,
    "base_load_kw": 300
  },
  "start_time": "2025-07-01T09:00:00+09:00",
  "periods": 3,
  "frequency_hours": 1,
  "history_defaults": {
    "past_capacity_factor": 0.42,
    "past_capacity_factor_lag_1": 0.38,
    "past_capacity_factor_lag_24": 0.40,
    "rolling_mean_cf_3h": 0.35,
    "rolling_mean_cf_24h": 0.12
  }
}
```

`periods: 3` and `frequency_hours: 1` returns three rows:

- `09:00`
- `10:00`
- `11:00`

Each row includes solar, load, safe load, and net load fields.

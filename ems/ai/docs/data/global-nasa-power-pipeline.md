# Global NASA POWER Pipeline

## Goal

This pipeline proves that the EMS AI solar baseline can run for sites in different countries without collecting every global power plant dataset.

The system uses site coordinates and NASA POWER global weather/solar data to build hourly features and a simple solar baseline. When a site cache is missing, the collector fills it from NASA POWER and stores the result locally.

## Demo Sites

The default config contains five global sites:

| site_id | Country | Purpose |
| --- | --- | --- |
| KR_SEOUL | Korea | local demo baseline |
| US_ARIZONA | United States | high-irradiance dry climate |
| DE_BERLIN | Germany | northern temperate climate |
| AE_DUBAI | UAE | desert climate |
| AU_SYDNEY | Australia | southern hemisphere seasonality |

## Data Source Strategy

Provider order:

```text
local processed CSV cache
  -> NASA POWER S3/Zarr, if dependencies and remote store are available
  -> NASA POWER Hourly API fallback
```

S3/Zarr is preferred for large-scale slicing because it avoids many point API requests. The API fallback stays in place because it has no extra dependency and is enough for the five-site demo.

## Local DB

The default config writes to the local TimescaleDB/PostgreSQL container:

```yaml
database:
  enabled: true
  use_env_overrides: false
  host: localhost
  port: 5432
  database: emsdb
  user: ems
  password: ems1234
```

These values are intentionally isolated in `ems/ai/configs/data_sources/nasa_power_global_sites.yaml`.
For AWS RDS or another PostgreSQL target, override the YAML values directly. If you prefer environment variables, set `use_env_overrides: true` and provide:

```text
AI_DB_HOST
AI_DB_PORT
AI_DB_NAME
AI_DB_USER
AI_DB_PASSWORD
```

The collector creates/upserts:

| Table | Role |
| --- | --- |
| `ai_site_mapping` | registered global demo sites |
| `ai_site_weather_hourly` | hourly NASA POWER features and baseline solar prediction |

File output still remains enabled, so DB can be rebuilt from local CSV cache if needed.

## Command

```bash
python ems/ai/scripts/collect_nasa_power_global_sites.py \
  --config ems/ai/configs/data_sources/nasa_power_global_sites.yaml
```

For a short smoke test:

```bash
python ems/ai/scripts/collect_nasa_power_global_sites.py \
  --config ems/ai/configs/data_sources/nasa_power_global_sites.yaml \
  --start-date 2025-01-01 \
  --end-date 2025-01-07
```

## Outputs

Raw responses:

```text
ems/ai/data/raw/weather/nasa_power_global/{site_id}/{start}_{end}.json
```

Processed hourly features:

```text
ems/ai/data/processed/weather/nasa_power_global/{site_id}/{start}_{end}.csv
```

Each processed row contains:

- `timestamp_utc`
- site metadata
- NASA POWER parameters
- `clear_sky_ratio`
- `temperature_factor`
- `predicted_solar_kw_baseline`
- `source_provider`

## Why This Is Not Full Global Training

The pipeline does not download the entire world and train one giant model. That would be expensive and weak for site-specific prediction.

Instead:

```text
registered site coordinate
  -> global NASA POWER feature cache
  -> baseline solar prediction
  -> prediction vs actual logging
  -> later site correction model
```

This keeps the demo global while still matching the long-term site-customized retraining plan.

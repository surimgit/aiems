# Load Profile And LLM Structuring

## Purpose

Solar prediction uses weather, time, capacity, and historical generation.

User environment descriptions are mainly useful for load prediction.

Initial load prediction cannot use supervised ML because the site-specific
actual load history is not available yet. The initial approach is:

```text
recent telemetry base load
+ structured user profile
+ weather/calendar adjustment
```

## Base Load

Recommended source order:

1. recent 7-day hourly average load
2. recent 24-hour load pattern
3. monthly_kwh or contract_power_kw
4. equipment catalog estimate
5. site-type fallback

Preferred formula:

```text
base_load_by_hour[h]
= average actual_load_kw at hour h during the recent 7 days
```

Forecast formula:

```text
predicted_load_kw[t]
= base_load_by_hour[t.hour]
× profile_weight[t]
× weather_adjustment[t]
× calendar_adjustment[t]
```

This means the system can be site-aware before one-year retraining if edge/EMS
telemetry is already available.

## LLM Role

LLM is called only when the site profile is created or updated.

LLM does:

- parse user free text
- extract site type
- extract equipment/components
- extract schedules
- extract seasonal conditions
- output schema-valid JSON

LLM does not:

- control EMS assets
- generate final control commands
- run every 30 minutes
- directly predict final solar/load values

Current script:

```bash
python ems/ai/scripts/structure_site_profile_with_llm.py --config ems/ai/configs/ops/llm_site_profile_example.yaml
```

The generated profile uses schema `site_profile.v1` and can be validated with:

```bash
python ems/ai/scripts/structure_site_profile_with_llm.py --config ems/ai/configs/ops/llm_site_profile_example.yaml --output ems/ai/configs/ops/site_profile_example.json --validate-only
```

## Component-Based Profile

Residential example:

```json
{
  "site_type": "residential",
  "components": [
    {
      "type": "air_conditioner",
      "count": 2,
      "schedule": {
        "season": "summer",
        "hours": [21, 22, 23, 0, 1, 2],
        "usage_level": "high"
      }
    },
    {
      "type": "refrigerator",
      "count": 1,
      "schedule": {
        "hours": "all_day",
        "usage_level": "medium"
      }
    }
  ]
}
```

Hospital example:

```json
{
  "site_type": "hospital",
  "components": [
    {
      "type": "operating_room",
      "count": 3,
      "schedule": {
        "days": "weekday",
        "hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
        "usage_level": "high"
      }
    },
    {
      "type": "emergency_room",
      "count": 1,
      "schedule": {
        "days": "daily",
        "hours": "all_day",
        "usage_level": "high"
      }
    }
  ]
}
```

## Numeric Source

Numeric load weights should come from controlled sources:

```text
equipment_catalog
profile_rule_table
recent telemetry
calendar/weather rules
```

The LLM output is a structured description. The load profile builder turns it
into hourly weights.

## Suggested Tables

```text
structured_profile
- site_id
- profile_version
- site_type
- components_json
- created_at
- updated_at

equipment_catalog
- component_type
- default_power_kw
- standby_power_kw
- duty_cycle
- criticality

load_profile_rule
- rule_key
- condition_json
- hourly_weight_json
```

## Operation

The 30-minute forecast cycle uses stored profile data:

```text
Forecast-AI scheduler
→ read structured_profile
→ read recent telemetry load
→ calculate base_load_by_hour
→ apply profile/weather/calendar weights
→ predicted_load_kw
```

LLM is not called during this cycle.

`run_operational_solar_forecast.py` now reads the stored profile and attaches
`profile_*` context fields to the forecast payload. The current solar model may
ignore those fields if they are not in its trained feature list, but downstream
load prior logic and future retraining can consume them.


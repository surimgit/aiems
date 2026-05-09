from __future__ import annotations

import json
import urllib.request


payload = {
    "region": "대전시",
    "horizon_hours": 24,
    "target_time": "2026-05-09T12:00:00+09:00",
    "installed_capacity_kw": 100,
}

request = urllib.request.Request(
    "http://localhost:5504/api/ai/predict-live-satellite-capacity-factor",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)

with urllib.request.urlopen(request, timeout=240) as response:
    result = json.load(response)

prediction = result.get("prediction", {})
target = result.get("target", {})
site = result.get("site", {})

print(
    json.dumps(
        {
            "ok": result.get("ok"),
            "task": result.get("task"),
            "region": site.get("region"),
            "horizon": target.get("horizon_hours"),
            "target_time": target.get("target_time"),
            "capacity_factor": prediction.get("predicted_capacity_factor"),
            "generation_kw": prediction.get("predicted_generation_kw"),
            "model_version": prediction.get("model_version"),
            "warnings": result.get("warnings", []),
        },
        ensure_ascii=False,
        indent=2,
    )
)

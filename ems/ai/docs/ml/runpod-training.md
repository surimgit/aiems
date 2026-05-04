# RunPod Serverless Training

## Purpose

RunPod is used as the service-friendly GPU path. The SSAFY GPU server is useful
for manual experiments, but it is tied to VPN/Jupyter/SSH access. RunPod
Serverless gives the backend a normal HTTP job API.

## Current State

- `RUNPOD_KEY` is read from `.env`; do not commit it.
- The account can authenticate against RunPod.
- No Serverless endpoint exists yet, so jobs cannot be submitted until a
  Docker image/template/endpoint is created.
- During tests, use the team Google Drive folder named `S3` as the temporary
  upload location:
  `https://drive.google.com/drive/folders/1Ex0M6QFooN46ndDP_J7FlEbfrNHMXo2x?usp=sharing`

## Worker Flow

1. Backend or local script sends a small JSON payload to RunPod.
2. Payload contains a downloadable `data_zip_url`, not the dataset bytes.
3. Worker downloads and extracts the training data into `/workspace/s305-ai-data`.
4. Worker runs:
   - stage 1: MLP baseline
   - stage 2: LightGBM baseline
   - stage 3: site correction LightGBM, skipped until actual site data exists
5. Worker zips `/workspace/runs`.
6. Worker uploads the result zip to `result_upload_url` if provided.
7. Worker returns stage status and small metrics JSON.

For inference, the worker returns postprocessed solar predictions. EMS must use
`predicted_solar_kw`, not `raw_predicted_solar_kw`.

Predict payloads must include explicit postprocessing fields in each feature row:

- `target_time`
- `target_hour`
- `installed_capacity_kw`

Optional postprocessing fields:

- `latitude`
- `longitude`
- `timezone`
- `is_daylight`
- `estimated_irradiance` in W/m2 scale, not the normalized training feature
- `solar_elevation`

These fields are not model training columns. They are safety inputs for
postprocessing only.

When `target_time`, `latitude`, `longitude`, and `timezone` are present, the
worker computes `solar_elevation` with `astral`. Keep `target_time` aligned to
the forecast target horizon, not the source telemetry timestamp.

Postprocessing rules:

- night or very low irradiance: `predicted_solar_kw = 0`
- negative prediction: `predicted_solar_kw = 0`
- capacity overflow: `predicted_solar_kw = installed_capacity_kw`
- keep `raw_predicted_solar_kw` and `postprocess_reason` for logging/retraining

## Files

- `ems/ai/runpod/Dockerfile`
- `ems/ai/runpod/handler.py`
- `ems/ai/scripts/runpod_client.py`
- `ems/ai/configs/runpod/training_job_example.yaml`
- `ems/ai/configs/runpod/predict_job_example.yaml`

## Cost Guard

Use these endpoint settings for early tests:

- `workersMin: 0`
- `workersMax: 1`
- `gpuCount: 1`
- GPU type: `NVIDIA L4` or `NVIDIA RTX A4000`
- short idle timeout, for example `5`
- async `/run`, then poll `/status`

`workersMin > 0` should be avoided during development because it keeps paid
workers warm even when no job is running.

## Local Commands

List endpoints:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" list-endpoints
```

Check endpoint billing:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" billing --bucket-size day
```

Submit after an endpoint exists:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" submit --endpoint-id "<endpoint_id>" --data-zip-url "<https_data_zip_url>"
```

Submit a sync predict smoke test after an endpoint exists:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" submit --config ems\ai\configs\runpod\predict_job_example.yaml --endpoint-id "<endpoint_id>" --mode sync
```

Check a job:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" status --endpoint-id "<endpoint_id>" --job-id "<job_id>"
```

## Remaining Setup

RunPod needs an endpoint before real tests. That requires either:

1. Push the Docker image to Docker Hub/GHCR, then create a Serverless endpoint
   from that image.
2. Import the repo into RunPod/GitHub if the project is available there.

The dataset zip must also be available by URL. Local Google Drive paths like
`G:\...` cannot be read directly from RunPod.

For test runs, upload the zip file to the shared Google Drive folder first:

```text
S3 Google Drive folder
https://drive.google.com/drive/folders/1Ex0M6QFooN46ndDP_J7FlEbfrNHMXo2x?usp=sharing
```

Then copy the uploaded zip file link and convert it to a direct-download URL:

```text
https://drive.google.com/file/d/<FILE_ID>/view?usp=sharing
```

becomes:

```text
https://drive.google.com/uc?export=download&id=<FILE_ID>
```

That direct-download URL goes into `input.data_zip_url`.

## Endpoint Creation

Build and push the image from the repo root:

```powershell
docker build -f ems\ai\runpod\Dockerfile -t <registry>/s305-ems-ai-training:latest .
docker push <registry>/s305-ems-ai-training:latest
```

Create a Serverless template:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" create-template --image "<registry>/s305-ems-ai-training:latest"
```

Copy the returned template `id`, then create a zero-idle-cost endpoint:

```powershell
python ems\ai\scripts\runpod_client.py --env-file "G:\내 드라이브\s305-ai-data\.env" create-endpoint --template-id "<template_id>" --gpu-type "NVIDIA L4" --workers-max 1
```

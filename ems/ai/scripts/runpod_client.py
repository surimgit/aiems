from __future__ import annotations

import argparse
import json
import os
import base64
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


REST_BASE_URL = "https://rest.runpod.io/v1"
SERVERLESS_BASE_URL = "https://api.runpod.ai/v2"


def load_key(env_file: str | None) -> str:
    if load_dotenv is not None and env_file:
        load_dotenv(env_file)
    elif load_dotenv is not None:
        load_dotenv()
    elif env_file:
        with Path(env_file).open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))

    key = os.getenv("RUNPOD_KEY") or os.getenv("RUNPOD_API_KEY")
    if not key:
        raise RuntimeError("RUNPOD_KEY or RUNPOD_API_KEY is not set")
    return key


def request_json(method: str, url: str, key: str, **kwargs: Any) -> Any:
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {key}" if "rest.runpod.io" in url else key
    headers.setdefault("Content-Type", "application/json")
    response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text}")
    if not response.text.strip():
        return None
    return response.json()


def save_base64_artifact(response_payload: Any, output_zip: str | None) -> None:
    if not output_zip or not isinstance(response_payload, dict):
        return

    output = response_payload.get("output", response_payload)
    artifact = output.get("artifact") if isinstance(output, dict) else None
    if not isinstance(artifact, dict) or not artifact.get("base64"):
        return

    target = Path(output_zip)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(base64.b64decode(artifact["base64"]))
    print(f"\nSaved artifact zip: {target}")


def list_endpoints(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    endpoints = request_json(
        "GET",
        f"{REST_BASE_URL}/endpoints?includeTemplate={str(args.include_template).lower()}&includeWorkers={str(args.include_workers).lower()}",
        key,
    )
    print(json.dumps(endpoints, ensure_ascii=False, indent=2))


def billing(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json("GET", f"{REST_BASE_URL}/billing/endpoints?bucketSize={args.bucket_size}", key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def list_templates(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json(
        "GET",
        f"{REST_BASE_URL}/templates?includePublicTemplates=false&includeRunpodTemplates={str(args.include_runpod).lower()}",
        key,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def create_template(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    payload = {
        "name": args.name,
        "imageName": args.image,
        "category": "NVIDIA",
        "containerDiskInGb": args.container_disk_gb,
        "dockerEntrypoint": [],
        "dockerStartCmd": [],
        "env": {},
        "isPublic": False,
        "isServerless": True,
        "ports": [],
        "readme": "EMS AI training worker",
    }
    result = request_json("POST", f"{REST_BASE_URL}/templates", key, json=payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def create_endpoint(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    payload = {
        "name": args.name,
        "templateId": args.template_id,
        "computeType": "GPU",
        "gpuCount": 1,
        "gpuTypeIds": args.gpu_type or ["NVIDIA L4"],
        "workersMin": 0,
        "workersMax": args.workers_max,
        "idleTimeout": args.idle_timeout,
        "executionTimeoutMs": args.execution_timeout_ms,
        "scalerType": "QUEUE_DELAY",
        "scalerValue": 4,
    }
    result = request_json("POST", f"{REST_BASE_URL}/endpoints", key, json=payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def delete_template(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json("DELETE", f"{REST_BASE_URL}/templates/{args.template_id}", key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def delete_endpoint(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json("DELETE", f"{REST_BASE_URL}/endpoints/{args.endpoint_id}", key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def submit(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    with Path(args.config).open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    endpoint_id = args.endpoint_id or config.get("endpoint_id")
    if not endpoint_id:
        raise RuntimeError("endpoint_id is required. Create a RunPod endpoint first.")

    mode = args.mode or config.get("mode", "async")
    payload = {"input": config.get("input", {})}
    if args.data_zip_url:
        payload["input"]["data_zip_url"] = args.data_zip_url
    if args.result_upload_url:
        payload["input"]["result_upload_url"] = args.result_upload_url

    if not payload["input"].get("data_zip_url"):
        raise RuntimeError("input.data_zip_url is required unless the endpoint mounts data_root.")

    if mode == "sync":
        wait_ms = int(args.wait_ms or config.get("wait_ms", 300000))
        url = f"{SERVERLESS_BASE_URL}/{endpoint_id}/runsync?wait={wait_ms}"
    elif mode == "async":
        url = f"{SERVERLESS_BASE_URL}/{endpoint_id}/run"
    else:
        raise RuntimeError("mode must be async or sync")

    result = request_json("POST", url, key, json=payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    save_base64_artifact(result, args.output_zip)


def status(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json("GET", f"{SERVERLESS_BASE_URL}/{args.endpoint_id}/status/{args.job_id}", key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    save_base64_artifact(result, args.output_zip)


def health(args: argparse.Namespace) -> None:
    key = load_key(args.env_file)
    result = request_json("GET", f"{SERVERLESS_BASE_URL}/{args.endpoint_id}/health", key)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RunPod Serverless client for EMS AI training.")
    parser.add_argument("--env-file", default=None, help="Path to .env containing RUNPOD_KEY.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-endpoints")
    list_parser.add_argument("--include-template", action="store_true")
    list_parser.add_argument("--include-workers", action="store_true")
    list_parser.set_defaults(func=list_endpoints)

    billing_parser = subparsers.add_parser("billing")
    billing_parser.add_argument("--bucket-size", default="day", choices=["hour", "day", "week", "month"])
    billing_parser.set_defaults(func=billing)

    templates_parser = subparsers.add_parser("list-templates")
    templates_parser.add_argument("--include-runpod", action="store_true")
    templates_parser.set_defaults(func=list_templates)

    create_template_parser = subparsers.add_parser("create-template")
    create_template_parser.add_argument("--name", default="s305-ems-ai-training")
    create_template_parser.add_argument("--image", required=True, help="Docker image, for example ghcr.io/org/image:tag.")
    create_template_parser.add_argument("--container-disk-gb", type=int, default=30)
    create_template_parser.set_defaults(func=create_template)

    create_endpoint_parser = subparsers.add_parser("create-endpoint")
    create_endpoint_parser.add_argument("--name", default="s305-ems-ai-training")
    create_endpoint_parser.add_argument("--template-id", required=True)
    create_endpoint_parser.add_argument(
        "--gpu-type",
        action="append",
        default=None,
        help="Can be repeated. First available type is used.",
    )
    create_endpoint_parser.add_argument("--workers-max", type=int, default=1)
    create_endpoint_parser.add_argument("--idle-timeout", type=int, default=5)
    create_endpoint_parser.add_argument("--execution-timeout-ms", type=int, default=1_800_000)
    create_endpoint_parser.set_defaults(func=create_endpoint)

    delete_template_parser = subparsers.add_parser("delete-template")
    delete_template_parser.add_argument("--template-id", required=True)
    delete_template_parser.set_defaults(func=delete_template)

    delete_endpoint_parser = subparsers.add_parser("delete-endpoint")
    delete_endpoint_parser.add_argument("--endpoint-id", required=True)
    delete_endpoint_parser.set_defaults(func=delete_endpoint)

    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--config", default="ems/ai/configs/runpod/training_job_example.yaml")
    submit_parser.add_argument("--endpoint-id", default=None)
    submit_parser.add_argument("--mode", choices=["async", "sync"], default=None)
    submit_parser.add_argument("--wait-ms", default=None)
    submit_parser.add_argument("--data-zip-url", default=None)
    submit_parser.add_argument("--result-upload-url", default=None)
    submit_parser.add_argument("--output-zip", default=None)
    submit_parser.set_defaults(func=submit)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--endpoint-id", required=True)
    status_parser.add_argument("--job-id", required=True)
    status_parser.add_argument("--output-zip", default=None)
    status_parser.set_defaults(func=status)

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--endpoint-id", required=True)
    health_parser.set_defaults(func=health)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

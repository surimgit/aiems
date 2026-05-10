from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


BASE_URL = "https://ssafy.atlassian.net"
EMAIL = "tkatnsdl1996@daum.net"
PROJECT_KEY = "S14P31S305"
ENV_PATH = Path(__file__).resolve().parent / ".env"
OUTPUT_PATH = Path(__file__).resolve().parent / "outputs" / "jira_infer_completed_result.json"
DONE_TRANSITIONS = {"완료", "Done"}
SUMMARIES = [
    "infer 진입점 생성",
    "checkpoint 로드 로직 구현",
    "입력 데이터 로딩 로직 구현",
    "예측 실행 및 결과 반환 구현",
    "샘플 추론 테스트 작성",
    "예측 결과 검증 기준 정의",
    "배치 추론 실행 예시 작성",
    "향후 API화 또는 배치화 방향 정리",
]


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_session() -> requests.Session:
    token = load_env().get("JIRA_KEY")
    if not token:
        raise RuntimeError("JIRA_KEY is not set")
    session = requests.Session()
    session.auth = HTTPBasicAuth(EMAIL, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return session


def search_summary(session: requests.Session, summary: str) -> list[dict[str, Any]]:
    response = session.get(
        f"{BASE_URL}/rest/api/3/search/jql",
        params={
            "jql": f'project = "{PROJECT_KEY}" AND summary ~ "\\"{summary}\\""',
            "maxResults": 20,
            "fields": "summary,status",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("issues", [])


def transition_to_done(session: requests.Session, key: str) -> bool:
    response = session.get(f"{BASE_URL}/rest/api/3/issue/{key}/transitions", timeout=30)
    response.raise_for_status()
    transition_id = None
    for transition in response.json().get("transitions", []):
        if transition.get("name") in DONE_TRANSITIONS:
            transition_id = transition.get("id")
            break
    if not transition_id:
        return False
    response = session.post(
        f"{BASE_URL}/rest/api/3/issue/{key}/transitions",
        json={"transition": {"id": transition_id}},
        timeout=30,
    )
    response.raise_for_status()
    return True


def main() -> None:
    session = build_session()
    results = []
    for summary in SUMMARIES:
        issues = search_summary(session, summary)
        if not issues:
            results.append({"summary": summary, "found": False})
            continue
        for issue in issues:
            key = issue["key"]
            current = issue["fields"]["status"]["name"]
            applied = False
            if current not in DONE_TRANSITIONS:
                applied = transition_to_done(session, key)
            results.append(
                {
                    "summary": summary,
                    "key": key,
                    "previous_status": current,
                    "applied": applied,
                }
            )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

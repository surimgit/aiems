import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


JIRA_BASE_URL = "https://ssafy.atlassian.net"
JIRA_EMAIL = "tkatnsdl1996@daum.net"
JIRA_API_TOKEN = ""
PROJECT_KEY = "S14P31S305"
ENV_PATH = Path(__file__).resolve().parent / ".env"

# When True, only print planned changes.
DRY_RUN = True

DONE_STATUS_CANDIDATES = ["완료", "Done"]
TODO_STATUS_CANDIDATES = ["해야 할 일", "To Do", "미완료"]


DONE_SUMMARIES = {
    "예측 대상 정의",
    "입력/출력 컬럼 정의",
    "학습 시간 단위 결정",
    "성공 기준 및 평가 지표 정의",
    "기상 데이터 소스 조사",
    "발전량 데이터 소스 조사",
    "데이터 수집 가능 범위 확인",
    "데이터 수집 정책 문서화",
    "기상 데이터 수집 스크립트 작성",
    "발전량 데이터 수집 스크립트 작성",
    "원천 데이터 저장 구조 정의",
    "수집 실패 및 재시도 처리",
    "시간축 정렬 로직 구현",
    "결측치 및 이상치 처리 규칙 정의",
    "피처 엔지니어링 초안 작성",
    "학습/검증/테스트 분할 구현",
    "최종 데이터셋 저장 포맷 결정",
    "샘플 데이터셋 검토",
    "데이터셋 생성 가이드 작성",
    "AI 작업 디렉토리 구조 구성",
    "conda 환경 구성 절차 정리",
    "필수 패키지 목록 정의",
    "GPU device 0 고정 방식 반영",
    "GPU 사용 가능 확인 코드 작성",
    "train 진입점 생성",
    "config 로딩 구조 구현",
    "dataset/dataloader 구현",
    "모델 초기화 로직 구현",
    "loss/optimizer/training loop 구현",
    "checkpoint 저장 정책 정의",
    "학습 상태 저장 구현",
    "최신 checkpoint 탐색 로직 구현",
    "자동 resume 로직 구현",
    "로그 저장 정책 정의",
    "파일 기반 로깅 구현",
    "학습 실행 스크립트 작성",
    "실행 전 체크리스트 작성",
    "검증 루프 구현",
    "평가 지표 계산 구현",
    "실험 결과 저장 형식 정의",
    "학습 운영 가이드 작성",
    "추론 대상 시나리오 정의",
    "추론 입력 포맷 정의",
    "추론 출력 포맷 정의",
    "성공 기준 정의",
    "서비스 연계 지점 식별",
    "입력 데이터 공급 방식 검토",
    "추론 운영 절차 문서화",
    "향후 API화 또는 배치화 방향 정리",
}

TODO_SUMMARIES = {
    "데이터 분포 점검",
    "데이터셋 버전 관리 규칙 정의",
    "중단 후 재시작 테스트",
    "1차 베이스라인 모델 학습 수행",
    "infer 진입점 생성",
    "checkpoint 로드 로직 구현",
    "입력 데이터 로딩 로직 구현",
    "예측 실행 및 결과 반환 구현",
    "샘플 추론 테스트 작성",
    "예측 결과 검증 기준 정의",
    "추론 결과 저장 방식 구현",
    "배치 추론 실행 예시 작성",
}


def validate_config() -> None:
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        raise ValueError("Fill JIRA_EMAIL and JIRA_API_TOKEN before running.")


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_session() -> requests.Session:
    session = requests.Session()
    session.auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
    session.headers.update(
        {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    return session


def fetch_project_issues(session: requests.Session) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    next_page_token: str | None = None
    jql = f'project = "{PROJECT_KEY}" ORDER BY created ASC'

    while True:
        params = {
            "jql": jql,
            "maxResults": 50,
            "fields": "summary,status,issuetype,parent",
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        response = session.get(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        issues.extend(data.get("issues", []))
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return issues


def build_issue_index(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        summary = issue.get("fields", {}).get("summary", "")
        if summary:
            index[summary].append(issue)
    return index


def get_transitions(session: requests.Session, issue_key: str) -> list[dict[str, Any]]:
    response = session.get(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("transitions", [])


def pick_transition_id(transitions: list[dict[str, Any]], candidates: list[str]) -> str | None:
    transition_map = {t.get("name"): t.get("id") for t in transitions}
    for name in candidates:
        if name in transition_map:
            return transition_map[name]
    return None


def transition_issue(session: requests.Session, issue_key: str, transition_id: str) -> None:
    response = session.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
        json={"transition": {"id": transition_id}},
        timeout=30,
    )
    response.raise_for_status()


def plan_changes(index: dict[str, list[dict[str, Any]]]) -> tuple[list[dict[str, Any]], list[str]]:
    plans: list[dict[str, Any]] = []
    warnings: list[str] = []

    def append_plan(summary: str, target_group: str) -> None:
        matches = index.get(summary, [])
        if not matches:
            warnings.append(f"Summary not found: {summary}")
            return
        if len(matches) > 1:
            warnings.append(
                f"Duplicate summary found ({len(matches)} matches): {summary} -> "
                f"{', '.join(issue['key'] for issue in matches)}"
            )
        for issue in matches:
            plans.append(
                {
                    "key": issue["key"],
                    "summary": summary,
                    "current_status": issue["fields"]["status"]["name"],
                    "target_group": target_group,
                }
            )

    for summary in sorted(DONE_SUMMARIES):
        append_plan(summary, "done")

    for summary in sorted(TODO_SUMMARIES):
        append_plan(summary, "todo")

    return plans, warnings


def main() -> None:
    global JIRA_API_TOKEN

    env_values = load_env_file(ENV_PATH)
    if not JIRA_API_TOKEN:
        JIRA_API_TOKEN = env_values.get("JIRA_KEY", "")

    validate_config()
    session = build_session()
    issues = fetch_project_issues(session)
    issue_index = build_issue_index(issues)
    plans, warnings = plan_changes(issue_index)

    print(f"Loaded {len(issues)} issues from project {PROJECT_KEY}.")
    print(f"Planned updates: {len(plans)}")
    if warnings:
        print("\nWarnings:")
        print(json.dumps(warnings, ensure_ascii=False, indent=2))

    results = []

    for plan in plans:
        transitions = get_transitions(session, plan["key"])
        target_candidates = DONE_STATUS_CANDIDATES if plan["target_group"] == "done" else TODO_STATUS_CANDIDATES
        transition_id = pick_transition_id(transitions, target_candidates)
        transition_names = [t.get("name") for t in transitions]

        result = {
            "key": plan["key"],
            "summary": plan["summary"],
            "current_status": plan["current_status"],
            "target_group": plan["target_group"],
            "available_transitions": transition_names,
            "applied": False,
        }

        if transition_id is None:
            result["error"] = "No matching transition found"
            results.append(result)
            continue

        result["transition_id"] = transition_id

        if not DRY_RUN:
            transition_issue(session, plan["key"], transition_id)
            result["applied"] = True

        results.append(result)

    print("\nResults:")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

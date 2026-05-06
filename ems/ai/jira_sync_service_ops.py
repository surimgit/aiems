from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
from requests.auth import HTTPBasicAuth


JIRA_BASE_URL = "https://ssafy.atlassian.net"
JIRA_EMAIL = "tkatnsdl1996@daum.net"
PROJECT_KEY = "S14P31S305"
ENV_PATH = Path(__file__).resolve().parent / ".env"
DOC_PATHS = [
    Path(__file__).resolve().parent / "docs" / "jira" / "service.md",
    Path(__file__).resolve().parent / "docs" / "jira" / "ops.md",
]
DONE_STATUS_CANDIDATES = ["완료", "Done"]


@dataclass
class TaskPlan:
    summary: str
    estimate: int
    status: str


@dataclass
class StoryPlan:
    summary: str
    story_points: int
    status: str
    description: str
    tasks: list[TaskPlan] = field(default_factory=list)


@dataclass
class EpicPlan:
    summary: str
    description: str
    stories: list[StoryPlan] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/update AI service/ops Jira issues from docs.")
    parser.add_argument("--apply", action="store_true", help="Actually create issues and transition completed work.")
    parser.add_argument("--output", default="ems/ai/outputs/jira_service_ops_plan.json")
    return parser.parse_args()


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
    env = load_env_file(ENV_PATH)
    token = env.get("JIRA_KEY", "")
    if not token:
        raise RuntimeError("JIRA_KEY is not set in ems/ai/.env")
    session = requests.Session()
    session.auth = HTTPBasicAuth(JIRA_EMAIL, token)
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    return session


def parse_docs(paths: list[Path]) -> list[EpicPlan]:
    return [parse_doc(path.read_text(encoding="utf-8")) for path in paths]


def parse_doc(text: str) -> EpicPlan:
    epic_match = re.search(r"## Epic\s+`([^`]+)`", text)
    if not epic_match:
        raise ValueError("Epic summary not found")
    epic_summary = epic_match.group(1)
    epic_description = section_text(text, "### Epic Description", "## Stories")
    epic = EpicPlan(summary=epic_summary, description=epic_description)

    story_chunks = re.split(r"\n### Story \d+\n", text)
    for chunk in story_chunks[1:]:
        summary_match = re.search(r"`([^`]+)`", chunk)
        points_match = re.search(r"- 스토리포인트: `(\d+)`", chunk)
        status_match = re.search(r"- 상태: ([^\n]+)", chunk)
        description_match = re.search(r"- 설명: ([^\n]+)", chunk)
        if not (summary_match and points_match and status_match):
            continue
        story = StoryPlan(
            summary=summary_match.group(1),
            story_points=int(points_match.group(1)),
            status=status_match.group(1).strip(),
            description=description_match.group(1).strip() if description_match else "",
        )
        task_chunks = re.split(r"\n- `", chunk)
        for task_chunk in task_chunks[1:]:
            task_summary = task_chunk.split("`", 1)[0]
            estimate_match = re.search(r"estimate: `(\d+)`", task_chunk)
            task_status_match = re.search(r"상태: ([^\n]+)", task_chunk)
            if not estimate_match:
                continue
            story.tasks.append(
                TaskPlan(
                    summary=task_summary,
                    estimate=int(estimate_match.group(1)),
                    status=task_status_match.group(1).strip() if task_status_match else story.status,
                )
            )
        epic.stories.append(story)
    return epic


def section_text(text: str, start_header: str, end_header: str) -> str:
    start = text.find(start_header)
    if start < 0:
        return ""
    start += len(start_header)
    end = text.find(end_header, start)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def adf(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text or " "}],
            }
        ],
    }


def fetch_project(session: requests.Session) -> dict[str, Any]:
    response = session.get(f"{JIRA_BASE_URL}/rest/api/3/project/{PROJECT_KEY}", timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_issue_types(session: requests.Session, project_id: str) -> dict[str, dict[str, Any]]:
    response = session.get(
        f"{JIRA_BASE_URL}/rest/api/3/issuetype/project",
        params={"projectId": project_id},
        timeout=30,
    )
    response.raise_for_status()
    return {item["name"]: item for item in response.json()}


def fetch_fields(session: requests.Session) -> list[dict[str, Any]]:
    response = session.get(f"{JIRA_BASE_URL}/rest/api/3/field", timeout=30)
    response.raise_for_status()
    return response.json()


def pick_story_point_fields(fields: list[dict[str, Any]]) -> list[str]:
    candidates = {"story point estimate", "story points", "스토리 포인트", "story point"}
    result = []
    for item in fields:
        name = str(item.get("name", "")).lower()
        if name in candidates or "story point" in name:
            result.append(item["id"])
    return result


def search_existing(session: requests.Session) -> dict[str, dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    next_page_token: str | None = None
    while True:
        params = {
            "jql": f'project = "{PROJECT_KEY}" ORDER BY created ASC',
            "maxResults": 100,
            "fields": "summary,status,issuetype,parent",
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token
        response = session.get(f"{JIRA_BASE_URL}/rest/api/3/search/jql", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        issues.extend(payload.get("issues", []))
        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break
    return {issue["fields"]["summary"]: issue for issue in issues}


def issue_type_id(types: dict[str, dict[str, Any]], preferred: list[str], *, subtask: bool | None = None) -> str:
    for name in preferred:
        item = types.get(name)
        if item and (subtask is None or bool(item.get("subtask")) == subtask):
            return item["id"]
    for item in types.values():
        if subtask is None or bool(item.get("subtask")) == subtask:
            return item["id"]
    raise RuntimeError(f"No issue type found for {preferred}")


def create_issue(
    session: requests.Session,
    *,
    project_id: str,
    issue_type: str,
    summary: str,
    description: str,
    story_point_fields: list[str] | None = None,
    story_points: int | None = None,
    parent_key: str | None = None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"id": project_id},
        "issuetype": {"id": issue_type},
        "summary": summary,
        "description": adf(description),
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}
    point_fields = story_point_fields or []
    attempts: list[dict[str, Any]] = []
    if story_points is not None:
        for field_id in point_fields:
            with_points = dict(fields)
            with_points[field_id] = story_points
            attempts.append(with_points)
    attempts.append(fields)

    last_response = None
    for attempted_fields in attempts:
        response = session.post(f"{JIRA_BASE_URL}/rest/api/3/issue", json={"fields": attempted_fields}, timeout=30)
        if response.status_code < 400:
            return response.json()
        last_response = response

    if parent_key:
        no_parent = dict(fields)
        no_parent.pop("parent", None)
        response = session.post(f"{JIRA_BASE_URL}/rest/api/3/issue", json={"fields": no_parent}, timeout=30)
        if response.status_code < 400:
            return response.json()
        last_response = response

    assert last_response is not None
    last_response.raise_for_status()
    raise RuntimeError("Unreachable Jira create state")


def get_transitions(session: requests.Session, issue_key: str) -> list[dict[str, Any]]:
    response = session.get(f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions", timeout=30)
    response.raise_for_status()
    return response.json().get("transitions", [])


def complete_issue(session: requests.Session, issue_key: str) -> bool:
    transitions = get_transitions(session, issue_key)
    transition_map = {transition.get("name"): transition.get("id") for transition in transitions}
    transition_id = None
    for name in DONE_STATUS_CANDIDATES:
        if name in transition_map:
            transition_id = transition_map[name]
            break
    if not transition_id:
        return False
    response = session.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/transitions",
        json={"transition": {"id": transition_id}},
        timeout=30,
    )
    response.raise_for_status()
    return True


def plan_payload(epics: list[EpicPlan]) -> dict[str, Any]:
    return {
        "epics": [
            {
                "summary": epic.summary,
                "stories": [
                    {
                        "summary": story.summary,
                        "story_points": story.story_points,
                        "status": story.status,
                        "tasks": [
                            {"summary": task.summary, "estimate": task.estimate, "status": task.status}
                            for task in story.tasks
                        ],
                    }
                    for story in epic.stories
                ],
            }
            for epic in epics
        ]
    }


def main() -> None:
    args = parse_args()
    epics = parse_docs(DOC_PATHS)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan_payload(epics), indent=2, ensure_ascii=False), encoding="utf-8")

    if not args.apply:
        print(json.dumps({"dry_run": True, "output": str(output_path), **plan_payload(epics)}, indent=2, ensure_ascii=False))
        return

    session = build_session()
    project = fetch_project(session)
    types = fetch_issue_types(session, project["id"])
    story_point_fields = pick_story_point_fields(fetch_fields(session))
    existing = search_existing(session)

    epic_type = issue_type_id(types, ["Epic", "에픽"])
    story_type = issue_type_id(types, ["Story", "스토리"], subtask=False)
    task_type = issue_type_id(types, ["하위 작업", "Sub-task"], subtask=True)

    results = []
    for epic in epics:
        epic_issue = existing.get(epic.summary)
        if not epic_issue:
            epic_issue = create_issue(
                session,
                project_id=project["id"],
                issue_type=epic_type,
                summary=epic.summary,
                description=epic.description,
            )
            existing[epic.summary] = {"key": epic_issue["key"], "fields": {"summary": epic.summary}}
        epic_key = epic_issue["key"]
        epic_result = {"summary": epic.summary, "key": epic_key, "stories": []}

        for story in epic.stories:
            story_issue = existing.get(story.summary)
            if not story_issue:
                story_issue = create_issue(
                    session,
                    project_id=project["id"],
                    issue_type=story_type,
                    summary=story.summary,
                    description=story.description,
                    story_point_fields=story_point_fields,
                    story_points=story.story_points,
                    parent_key=epic_key,
                )
                existing[story.summary] = {"key": story_issue["key"], "fields": {"summary": story.summary}}
            story_key = story_issue["key"]
            if story.status == "완료":
                complete_issue(session, story_key)
            story_result = {"summary": story.summary, "key": story_key, "tasks": []}

            for task in story.tasks:
                task_summary = task.summary
                task_issue = existing.get(task_summary)
                description = f"estimate: {task.estimate}\nparent_story: {story.summary}"
                if not task_issue:
                    task_issue = create_issue(
                        session,
                        project_id=project["id"],
                        issue_type=task_type,
                        summary=task_summary,
                        description=description,
                        story_point_fields=story_point_fields,
                        story_points=task.estimate,
                        parent_key=story_key,
                    )
                    existing[task_summary] = {"key": task_issue["key"], "fields": {"summary": task_summary}}
                task_key = task_issue["key"]
                if task.status == "완료":
                    complete_issue(session, task_key)
                story_result["tasks"].append({"summary": task.summary, "key": task_key, "estimate": task.estimate})
            epic_result["stories"].append(story_result)
        results.append(epic_result)

    print(json.dumps({"applied": True, "story_point_fields": story_point_fields, "results": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

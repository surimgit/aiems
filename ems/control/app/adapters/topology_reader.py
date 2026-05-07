"""state-processor 의 topology API 를 비동기로 가져와 last-known 캐시로 보관.

설계 (PLAN_TOPOLOGY_AWARE_CONTROL.md Phase B / Q2):
- 매 control iteration 마다 HTTP 호출 — 부담 적음 (자원 십수 개).
- 응답 성공 → last-known 갱신 + age 0.
- 응답 실패 → last-known 그대로 반환 (단, 30초 초과 시 빈 그래프 + WARNING).
- 30초는 STATE_TTL 과 일치 — 일관성.

graph 인스턴스는 build_graph 로 만들어 반환한다 (TopologyGraph). 호출자는 구조 모름.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from ..domain.topology_graph import TopologyGraph, build_graph


# 마지막으로 알려진 정상 토폴로지가 30초 넘게 갱신 안 되면 stale 로 간주.
# STATE_TTL 정책 키와 같은 값이지만 여기선 상수로 둔다 (DB 라운드트립 절약).
_STALE_AFTER_SEC = 30.0


class TopologyReader:
    def __init__(self, base_url: str, site_id: str, *, timeout_sec: float = 1.5) -> None:
        self._base_url = base_url.rstrip("/")
        self._site_id = site_id
        self._timeout = timeout_sec
        self._client: Optional[httpx.AsyncClient] = None
        self._last_topology: Optional[dict] = None
        self._last_fetched_at: float = 0.0
        self._last_warned_stale: bool = False

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def fetch(self) -> TopologyGraph:
        """현재 토폴로지를 가져와 그래프로 반환.

        실패 시 last-known 사용. STALE_AFTER_SEC 초과 시 빈 그래프.
        """
        url = f"{self._base_url}/api/plants/{self._site_id}/topology"
        try:
            client = await self._ensure_client()
            resp = await client.get(url)
            resp.raise_for_status()
            self._last_topology = resp.json()
            self._last_fetched_at = time.monotonic()
            if self._last_warned_stale:
                print(f"[control][topology] 복구: state-processor 응답 정상")
                self._last_warned_stale = False
            return build_graph(self._last_topology)
        except Exception as exc:
            age = time.monotonic() - self._last_fetched_at if self._last_fetched_at else float("inf")
            if self._last_topology is not None and age <= _STALE_AFTER_SEC:
                # 일시 장애 — last-known 사용, 한 줄만 짧게 로그.
                print(f"[control][topology] fetch 실패, last-known 사용 (age={age:.1f}s): {exc}")
                return build_graph(self._last_topology)
            # 30초 초과 또는 캐시 없음 → 빈 그래프 + WARNING (한 번만).
            if not self._last_warned_stale:
                print(f"[control][topology][WARNING] state-processor 응답 {age:.0f}s 이상 두절. 모든 자원 isolated 로 간주: {exc}")
                self._last_warned_stale = True
            return build_graph(None)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

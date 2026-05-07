"""토폴로지 인식 제어를 위한 연결성 그래프.

state-processor 의 GET /api/plants/{site_id}/topology 응답을 입력 받아
"이 자원이 적어도 하나의 LOAD 와 통전 가능한가?" 를 빠르게 판정한다.

설계 원칙:
- 순수 함수. 외부 I/O 없음.
- TopologyDto (nodes, lines, switches) → TopologyGraph 빌드.
- 유효 선로 정의: line.status == "NORMAL" AND 해당 line 의 모든 switch.position == "CLOSED".
  (Q3 결정: 1 line 에 N switch 지원, 모두 CLOSED 일 때만 통전.)
"""

from __future__ import annotations

from collections import defaultdict, deque


_VALID_LINE_STATUS = {"NORMAL"}
_CLOSED_SWITCH_POSITIONS = {"CLOSED"}


class TopologyGraph:
    """토폴로지 응답을 들고 있다가 dispatchability 질의에 답하는 객체.

    의도적으로 작은 데이터 구조 + dict 기반으로 둠 (외부 라이브러리 없음).
    """

    def __init__(
        self,
        node_to_resource: dict[str, str | None],
        resource_to_node: dict[str, str],
        adjacency: dict[str, set[str]],
        load_resource_ids: set[str],
    ) -> None:
        self._node_to_resource = node_to_resource
        self._resource_to_node = resource_to_node
        self._adjacency = adjacency
        self._load_resource_ids = load_resource_ids
        # 매번 BFS 돌리지 않도록 reachable set 캐시
        self._reachable_cache: dict[str, set[str]] = {}

    @property
    def load_resource_ids(self) -> set[str]:
        return set(self._load_resource_ids)

    def reachable_resources(self, resource_id: str) -> set[str]:
        """이 자원에서 유효 선로만 따라 도달 가능한 모든 resource_id 집합 (자신 제외).

        - 자원이 토폴로지에 없으면 빈 set.
        - 모든 인접 노드가 device 와 매핑돼 있는 건 아니므로 resource_id 가 None 인 노드는 통과만 가능.
        """
        if resource_id in self._reachable_cache:
            return set(self._reachable_cache[resource_id])

        start_node = self._resource_to_node.get(resource_id)
        if start_node is None:
            self._reachable_cache[resource_id] = set()
            return set()

        visited_nodes = {start_node}
        queue: deque[str] = deque([start_node])
        reached_resources: set[str] = set()

        while queue:
            node = queue.popleft()
            for neighbor in self._adjacency.get(node, ()):
                if neighbor in visited_nodes:
                    continue
                visited_nodes.add(neighbor)
                neighbor_resource = self._node_to_resource.get(neighbor)
                if neighbor_resource and neighbor_resource != resource_id:
                    reached_resources.add(neighbor_resource)
                queue.append(neighbor)

        self._reachable_cache[resource_id] = set(reached_resources)
        return reached_resources

    def is_connected_to_any_load(self, resource_id: str) -> bool:
        """이 자원이 LOAD 노드 하나라도 통전 가능한가."""
        if not self._load_resource_ids:
            return False
        if resource_id in self._load_resource_ids:
            # LOAD 자원 본인은 자신과 통전됐다고 보지 않는다 — 다른 LOAD 와의 연결 여부로 판단.
            return bool(self.reachable_resources(resource_id) & self._load_resource_ids)
        return bool(self.reachable_resources(resource_id) & self._load_resource_ids)

    def is_isolated(self, resource_id: str) -> bool:
        """LOAD 와 통전되지 않으면 isolated. 토폴로지에 없는 자원도 isolated 로 간주."""
        if resource_id not in self._resource_to_node:
            return True
        return not self.is_connected_to_any_load(resource_id)


def _line_is_energized(line: dict, switches_by_line: dict[str, list[dict]]) -> bool:
    # Q3: line 의 모든 switch 가 CLOSED 여야 통전.
    if (line.get("status") or "").upper() not in _VALID_LINE_STATUS:
        return False
    sws = switches_by_line.get(line.get("line_id") or "", [])
    if not sws:
        # 스위치가 아예 없으면 라인 상태만으로 판단 (상시 통전 라인).
        return True
    for sw in sws:
        if (sw.get("position") or "").upper() not in _CLOSED_SWITCH_POSITIONS:
            return False
        if sw.get("interlock_blocked"):
            return False
    return True


def build_graph(topology: dict | None) -> TopologyGraph:
    """TopologyDto → TopologyGraph.

    None / 빈 응답이면 빈 그래프 반환 (모든 자원 isolated 로 평가됨).
    """
    if not topology:
        return TopologyGraph({}, {}, {}, set())

    nodes = topology.get("nodes") or []
    lines = topology.get("lines") or []
    switches = topology.get("switches") or []

    node_to_resource: dict[str, str | None] = {}
    resource_to_node: dict[str, str] = {}
    load_resource_ids: set[str] = set()

    for n in nodes:
        node_id = n.get("node_id")
        if not node_id:
            continue
        resource_id = n.get("resource_id")
        node_to_resource[node_id] = resource_id
        if resource_id:
            resource_to_node[resource_id] = node_id
        if (n.get("node_type") or "").upper() == "LOAD" and resource_id:
            load_resource_ids.add(resource_id)

    switches_by_line: dict[str, list[dict]] = defaultdict(list)
    for sw in switches:
        line_id = sw.get("line_id")
        if line_id:
            switches_by_line[line_id].append(sw)

    adjacency: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if not _line_is_energized(line, switches_by_line):
            continue
        a = line.get("from_node_id")
        b = line.get("to_node_id")
        if not a or not b:
            continue
        adjacency[a].add(b)
        adjacency[b].add(a)

    return TopologyGraph(
        node_to_resource=node_to_resource,
        resource_to_node=resource_to_node,
        adjacency=dict(adjacency),
        load_resource_ids=load_resource_ids,
    )

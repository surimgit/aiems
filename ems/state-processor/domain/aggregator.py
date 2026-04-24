from collections import defaultdict


_MAX_BUFFER_SIZE = 100  # 장치당 최대 버퍼 크기 — burst 시 메모리 보호


class WindowAggregator:
    """1초 윈도우 내 수신된 메시지를 집계하여 avg/max/min 반환"""

    def __init__(self):
        self._buffers: dict[str, list[dict]] = defaultdict(list)

    def add(self, snapshot: dict) -> None:
        key = snapshot["device_id"]
        buf = self._buffers[key]
        if len(buf) >= _MAX_BUFFER_SIZE:
            buf.pop(0)  # 가장 오래된 항목 제거
        buf.append(snapshot)

    def flush(self) -> list[dict]:
        # 버퍼를 atomic하게 교체 - 교체 후 add()는 새 버퍼에 쌓여 유실 없음
        current, self._buffers = self._buffers, defaultdict(list)

        results = []
        for device_id, snapshots in current.items():
            if not snapshots:
                continue
            p_values = [s["reported_state"].get("P") for s in snapshots if s["reported_state"].get("P") is not None]
            q_values = [s["reported_state"].get("Q") for s in snapshots if s["reported_state"].get("Q") is not None]
            v_values = [s["reported_state"].get("V") for s in snapshots if s["reported_state"].get("V") is not None]
            f_values = [s["reported_state"].get("f") for s in snapshots if s["reported_state"].get("f") is not None]
            pf_values = [s["reported_state"].get("PF") for s in snapshots if s["reported_state"].get("PF") is not None]
            soc_values = [s["reported_state"].get("SOC") for s in snapshots if s["reported_state"].get("SOC") is not None]

            latest = snapshots[-1]
            results.append({
                "time": latest["timestamp"],
                "site_id": latest["site_id"],
                "device_id": device_id,
                "resource_type": latest["resource_type"],
                "p_avg": _avg(p_values),
                "p_max": max(p_values) if p_values else None,
                "p_min": min(p_values) if p_values else None,
                "q_avg": _avg(q_values),
                "v_avg": _avg(v_values),
                "f_avg": _avg(f_values),
                "pf_avg": _avg(pf_values),
                "soc": soc_values[-1] if soc_values else None,
                "sample_count": len(snapshots),
            })
        return results


def _avg(values: list) -> float | None:
    return sum(values) / len(values) if values else None

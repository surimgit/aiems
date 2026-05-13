from __future__ import annotations

import asyncio
import copy
from collections import Counter
from typing import TYPE_CHECKING

from ..config import TELEMETRY_FLUSH_INTERVAL_SEC

if TYPE_CHECKING:
    from .redis_publisher import RedisPublisher


class TelemetryCoalescer:
    """Publish one latest telemetry envelope per device for each flush window."""

    def __init__(
        self,
        publisher: RedisPublisher,
        interval_sec: float = TELEMETRY_FLUSH_INTERVAL_SEC,
    ) -> None:
        self._publisher = publisher
        self._interval_sec = interval_sec
        self._windows: dict[tuple[str, str, str, str, str], _TelemetryWindow] = {}
        self._lock = asyncio.Lock()

    async def add(self, stream: str, envelope: dict) -> None:
        async with self._lock:
            key = _key(stream, envelope)
            if key not in self._windows:
                self._windows[key] = _TelemetryWindow(stream=stream)
            self._windows[key].add(envelope)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._interval_sec)
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            pending = {
                key: (window.stream, window.to_envelope(self._interval_sec))
                for key, window in self._windows.items()
            }
            self._windows = {}

        if not pending:
            return

        failed: dict[tuple[str, str, str, str, str], tuple[str, dict]] = {}
        counts: Counter[str] = Counter()

        items = list(pending.items())
        for index, (key, (stream, envelope)) in enumerate(items):
            try:
                await self._publisher.publish(stream, envelope)
                counts[stream] += 1
            except asyncio.CancelledError:
                await self._restore_pending(dict(items[index:]) | failed)
                raise
            except Exception as e:
                failed[key] = (stream, envelope)
                print(
                    f"[ingestion] telemetry flush 실패 "
                    f"device={envelope.get('resource_id')} stream={stream} error={e}"
                )

        if failed:
            await self._restore_pending(failed)

        if counts:
            summary = ", ".join(f"{stream}={count}" for stream, count in counts.items())
            print(f"[ingestion] telemetry flush: {summary}")

    async def _restore_pending(
        self,
        pending: dict[tuple[str, str, str, str, str], tuple[str, dict]],
    ) -> None:
        async with self._lock:
            for key, (stream, envelope) in pending.items():
                if key not in self._windows:
                    self._windows[key] = _TelemetryWindow(stream=stream)
                self._windows[key].add(envelope)


class _TelemetryWindow:
    def __init__(self, stream: str) -> None:
        self.stream = stream
        self.latest: dict | None = None
        self.sample_count = 0
        self.started_at: str | None = None
        self.ended_at: str | None = None
        self.instantaneous_stats: dict[str, _NumericStat] = {}
        self.status_stats: dict[str, _NumericStat] = {}

    def add(self, envelope: dict) -> None:
        self.latest = envelope
        self.sample_count += 1
        timestamp = envelope.get("timestamp")
        if self.started_at is None:
            self.started_at = timestamp
        self.ended_at = timestamp

        payload = envelope.get("payload") or {}
        self._add_numeric_fields(self.instantaneous_stats, payload.get("instantaneous") or {})
        self._add_numeric_fields(self.status_stats, payload.get("status") or {})

    def to_envelope(self, interval_sec: float) -> dict:
        if self.latest is None:
            raise ValueError("cannot flush an empty telemetry window")

        envelope = copy.deepcopy(self.latest)
        payload = envelope.setdefault("payload", {})
        payload["window"] = {
            "interval_sec": interval_sec,
            "sample_count": self.sample_count,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "stats": _without_empty({
                "instantaneous": _serialize_stats(self.instantaneous_stats),
                "status": _serialize_stats(self.status_stats),
            }),
        }
        return envelope

    @staticmethod
    def _add_numeric_fields(target: dict[str, "_NumericStat"], values: dict) -> None:
        for field, value in values.items():
            numeric = _to_number(value)
            if numeric is None:
                continue
            if field not in target:
                target[field] = _NumericStat()
            target[field].add(numeric)


class _NumericStat:
    def __init__(self) -> None:
        self.count = 0
        self.total = 0.0
        self.min_value: float | None = None
        self.max_value: float | None = None
        self.latest: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.latest = value
        self.min_value = value if self.min_value is None else min(self.min_value, value)
        self.max_value = value if self.max_value is None else max(self.max_value, value)

    def to_dict(self) -> dict:
        return {
            "avg": self.total / self.count,
            "min": self.min_value,
            "max": self.max_value,
            "latest": self.latest,
            "count": self.count,
        }


def _key(stream: str, envelope: dict) -> tuple[str, str, str, str, str]:
    return (
        stream,
        str(envelope.get("site_id") or ""),
        str(envelope.get("edge_id") or ""),
        str(envelope.get("resource_type") or ""),
        str(envelope.get("resource_id") or ""),
    )


def _to_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _serialize_stats(stats: dict[str, _NumericStat]) -> dict:
    return {field: stat.to_dict() for field, stat in stats.items()}


def _without_empty(values: dict[str, dict]) -> dict:
    return {key: value for key, value in values.items() if value}

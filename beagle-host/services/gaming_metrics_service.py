"""Gaming Metrics Service — stream health + GPU metrics per gaming session.

GoEnterprise Plan 03, Schritt 4
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GamingSessionMetrics:
    session_id: str
    vmid: int
    pool_id: str
    user_id: str
    started_at: str
    samples: list[dict[str, Any]] = field(default_factory=list)

    def add_sample(
        self,
        timestamp: str,
        fps: float,
        rtt_ms: float,
        dropped_frames: int,
        gpu_util_pct: float,
        gpu_temp_c: float,
        encoder_util_pct: float,
    ) -> None:
        self.samples.append({
            "ts": timestamp,
            "fps": fps,
            "rtt_ms": rtt_ms,
            "dropped_frames": dropped_frames,
            "gpu_util_pct": gpu_util_pct,
            "gpu_temp_c": gpu_temp_c,
            "encoder_util_pct": encoder_util_pct,
        })

    def avg_fps(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s["fps"] for s in self.samples) / len(self.samples)

    def avg_rtt_ms(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s["rtt_ms"] for s in self.samples) / len(self.samples)

    def max_gpu_temp(self) -> float:
        if not self.samples:
            return 0.0
        return max(s["gpu_temp_c"] for s in self.samples)

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pool_id": self.pool_id,
            "vmid": self.vmid,
            "avg_fps": round(self.avg_fps(), 1),
            "avg_rtt_ms": round(self.avg_rtt_ms(), 2),
            "max_gpu_temp_c": round(self.max_gpu_temp(), 1),
            "sample_count": len(self.samples),
        }


class GamingMetricsService:
    """Collects and aggregates gaming session metrics."""

    STATE_DIR = Path("/var/lib/beagle/gaming-metrics")

    def __init__(self, state_dir: Path | None = None, utcnow: Any = None) -> None:
        self._state_dir = state_dir or self.STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or self._default_utcnow
        self._sessions: dict[str, GamingSessionMetrics] = {}

    def start_session(
        self, session_id: str, vmid: int, pool_id: str, user_id: str
    ) -> GamingSessionMetrics:
        m = GamingSessionMetrics(
            session_id=session_id,
            vmid=vmid,
            pool_id=pool_id,
            user_id=user_id,
            started_at=self._utcnow(),
        )
        self._sessions[session_id] = m
        return m

    def record_sample(
        self,
        session_id: str,
        *,
        fps: float,
        rtt_ms: float,
        dropped_frames: int = 0,
        gpu_util_pct: float = 0.0,
        gpu_temp_c: float = 0.0,
        encoder_util_pct: float = 0.0,
    ) -> None:
        if session_id not in self._sessions:
            raise KeyError(f"Session {session_id!r} not found")
        self._sessions[session_id].add_sample(
            self._utcnow(), fps, rtt_ms, dropped_frames,
            gpu_util_pct, gpu_temp_c, encoder_util_pct,
        )

    def end_session(self, session_id: str) -> dict[str, Any]:
        """Persist session summary and return it."""
        if session_id not in self._sessions:
            return {}
        m = self._sessions.pop(session_id)
        summary = m.summary()
        summary["ended_at"] = self._utcnow()
        out = self._state_dir / f"{session_id}.json"
        out.write_text(json.dumps(summary, indent=2))
        return summary

    def get_active_sessions(self) -> list[dict[str, Any]]:
        return [m.summary() for m in self._sessions.values()]

    def check_alerts(
        self,
        session_id: str,
        *,
        fps_threshold: float = 30.0,
        rtt_threshold_ms: float = 50.0,
    ) -> list[str]:
        """Return list of alert messages for the session."""
        m = self._sessions.get(session_id)
        if not m:
            return []
        alerts = []
        if m.avg_fps() < fps_threshold and m.samples:
            alerts.append(f"low_fps: avg={m.avg_fps():.1f} < {fps_threshold}")
        if m.avg_rtt_ms() > rtt_threshold_ms and m.samples:
            alerts.append(f"high_rtt: avg={m.avg_rtt_ms():.1f}ms > {rtt_threshold_ms}ms")
        return alerts

    @staticmethod
    def _default_utcnow() -> str:
        import datetime
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

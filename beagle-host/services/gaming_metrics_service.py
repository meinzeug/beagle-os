"""Gaming Metrics Service — stream health + GPU metrics per gaming session.

GoEnterprise Plan 03, Schritt 4
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from core.persistence.json_state_store import JsonStateStore


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
            "user_id": self.user_id,
            "started_at": self.started_at,
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
        self, session_id: str, vmid: int, pool_id: str, user_id: str, *, started_at: str | None = None
    ) -> GamingSessionMetrics:
        m = GamingSessionMetrics(
            session_id=session_id,
            vmid=vmid,
            pool_id=pool_id,
            user_id=user_id,
            started_at=str(started_at or self._utcnow()),
        )
        self._sessions[session_id] = m
        return m

    def ensure_session(
        self,
        session_id: str,
        *,
        vmid: int,
        pool_id: str,
        user_id: str,
        started_at: str | None = None,
    ) -> GamingSessionMetrics:
        current = self._sessions.get(session_id)
        if current is not None:
            return current
        return self.start_session(
            session_id,
            vmid=vmid,
            pool_id=pool_id,
            user_id=user_id,
            started_at=started_at,
        )

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
        JsonStateStore(out, default_factory=dict).save(summary)
        return summary

    def get_active_sessions(self) -> list[dict[str, Any]]:
        return [m.summary() for m in self._sessions.values()]

    def get_active_session_details(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for metrics in self._sessions.values():
            latest = dict(metrics.samples[-1]) if metrics.samples else {}
            items.append(
                {
                    **metrics.summary(),
                    "latest_sample": latest,
                    "alerts": self.check_alerts(metrics.session_id),
                }
            )
        items.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return items

    def observe_session(self, session: dict[str, Any]) -> dict[str, Any]:
        session_id = str(session.get("session_id") or "").strip()
        pool_id = str(session.get("pool_id") or "").strip()
        vmid = int(session.get("vmid") or 0)
        user_id = str(session.get("user_id") or "").strip()
        if not session_id or not pool_id or vmid <= 0:
            raise ValueError("session_id, pool_id and vmid are required")
        started_at = str(session.get("assigned_at") or session.get("started_at") or self._utcnow())
        metrics = self.ensure_session(
            session_id,
            vmid=vmid,
            pool_id=pool_id,
            user_id=user_id,
            started_at=started_at,
        )
        sample = session.get("stream_health") if isinstance(session.get("stream_health"), dict) else {}
        sample_ts = str(sample.get("updated_at") or self._utcnow())
        last_ts = str(metrics.samples[-1].get("ts") or "") if metrics.samples else ""
        if sample and sample_ts != last_ts:
            metrics.add_sample(
                sample_ts,
                float(sample.get("fps") or 0.0),
                float(sample.get("rtt_ms") or 0.0),
                int(sample.get("dropped_frames") or 0),
                float(sample.get("gpu_util_pct") or 0.0),
                float(sample.get("gpu_temp_c") or 0.0),
                float(sample.get("encoder_util_pct") or sample.get("encoder_load") or 0.0),
            )
        return {
            **metrics.summary(),
            "latest_sample": dict(metrics.samples[-1]) if metrics.samples else {},
            "alerts": self.check_alerts(session_id),
        }

    def finalize_missing_sessions(self, active_session_ids: list[str] | set[str]) -> list[dict[str, Any]]:
        active = {str(value or "").strip() for value in active_session_ids if str(value or "").strip()}
        finalized: list[dict[str, Any]] = []
        for session_id in list(self._sessions.keys()):
            if session_id in active:
                continue
            summary = self.end_session(session_id)
            if summary:
                finalized.append(summary)
        return finalized

    def list_recent_reports(self, limit: int = 24) -> list[dict[str, Any]]:
        files = sorted(
            self._state_dir.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        items: list[dict[str, Any]] = []
        for path in files:
            try:
                payload = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                items.append(payload)
            if len(items) >= max(1, int(limit or 24)):
                break
        return items

    def build_dashboard(
        self,
        *,
        visible_pool_ids: list[str] | set[str] | None = None,
        recent_limit: int = 24,
    ) -> dict[str, Any]:
        allowed = None
        if visible_pool_ids is not None:
            allowed = {str(value or "").strip() for value in visible_pool_ids if str(value or "").strip()}
        active_sessions = [
            item
            for item in self.get_active_session_details()
            if allowed is None or str(item.get("pool_id") or "") in allowed
        ]
        recent_reports = [
            item
            for item in self.list_recent_reports(limit=recent_limit)
            if allowed is None or str(item.get("pool_id") or "") in allowed
        ]
        summary_source = recent_reports if recent_reports else active_sessions
        fps_values = [float(item.get("avg_fps") or 0.0) for item in summary_source if item.get("avg_fps") is not None]
        rtt_values = [float(item.get("avg_rtt_ms") or 0.0) for item in summary_source if item.get("avg_rtt_ms") is not None]
        gpu_temp_values = [float(item.get("max_gpu_temp_c") or 0.0) for item in summary_source if item.get("max_gpu_temp_c") is not None]
        trend = []
        trend_source = recent_reports[:12] if recent_reports else active_sessions[:12]
        for item in list(reversed(trend_source)):
            label = str(item.get("ended_at") or item.get("started_at") or item.get("session_id") or "-")
            trend.append(
                {
                    "label": label[-8:] if "T" in label else label,
                    "avg_fps": float(item.get("avg_fps") or 0.0),
                    "avg_rtt_ms": float(item.get("avg_rtt_ms") or 0.0),
                    "max_gpu_temp_c": float(item.get("max_gpu_temp_c") or 0.0),
                }
            )
        return {
            "generated_at": self._utcnow(),
            "overview": {
                "active_sessions": len(active_sessions),
                "recent_sessions": len(recent_reports),
                "avg_fps_recent": round(sum(fps_values) / len(fps_values), 1) if fps_values else 0.0,
                "avg_rtt_ms_recent": round(sum(rtt_values) / len(rtt_values), 2) if rtt_values else 0.0,
                "max_gpu_temp_c_recent": round(max(gpu_temp_values), 1) if gpu_temp_values else 0.0,
                "alert_count_active": sum(len(item.get("alerts") or []) for item in active_sessions),
            },
            "active_sessions": active_sessions,
            "recent_reports": recent_reports,
            "trend": trend,
        }

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

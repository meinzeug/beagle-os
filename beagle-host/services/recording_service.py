from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Callable


class RecordingService:
    def __init__(
        self,
        *,
        load_json_file: Callable[[Path, Any], Any],
        now_utc: Callable[[], str],
        popen: Callable[..., Any],
        recordings_dir: Callable[[], Path],
        safe_slug: Callable[[str, str], str],
        write_json_file: Callable[..., None],
    ) -> None:
        self._load_json_file = load_json_file
        self._now_utc = now_utc
        self._popen = popen
        self._recordings_dir = recordings_dir
        self._safe_slug = safe_slug
        self._write_json_file = write_json_file

    def _index_path(self) -> Path:
        return self._recordings_dir() / "index.json"

    def _load_index(self) -> dict[str, Any]:
        payload = self._load_json_file(self._index_path(), {"sessions": {}})
        if not isinstance(payload, dict):
            return {"sessions": {}}
        sessions = payload.get("sessions")
        if not isinstance(sessions, dict):
            payload["sessions"] = {}
        return payload

    def _save_index(self, index_payload: dict[str, Any]) -> None:
        self._write_json_file(self._index_path(), index_payload, mode=0o600)

    @staticmethod
    def _codec_args(codec: str) -> list[str]:
        c = str(codec or "h264").strip().lower()
        if c in {"h265", "hevc"}:
            return ["-c:v", "libx265"]
        return ["-c:v", "libx264"]

    def _build_ffmpeg_command(
        self,
        *,
        output_path: Path,
        input_url: str,
        codec: str,
        test_source: bool,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y"]
        if test_source:
            cmd += ["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30"]
        elif input_url:
            cmd += ["-i", input_url]
        else:
            # Fallback for Linux hosts without explicit stream URL.
            cmd += ["-f", "x11grab", "-framerate", "30", "-i", ":0.0"]
        cmd += self._codec_args(codec)
        # Keep deterministic short recordings in test_source mode to allow
        # immediate API validation without asynchronous wait loops.
        duration_seconds = "2" if test_source else "10"
        cmd += ["-pix_fmt", "yuv420p", "-movflags", "+faststart", "-t", duration_seconds, str(output_path)]
        return cmd

    def start_recording(
        self,
        *,
        session_id: str,
        input_url: str = "",
        codec: str = "h264",
        test_source: bool = False,
    ) -> dict[str, Any]:
        sid = self._safe_slug(str(session_id or "").strip(), "session")
        index_payload = self._load_index()
        sessions = index_payload.setdefault("sessions", {})
        existing = sessions.get(sid)
        if isinstance(existing, dict) and str(existing.get("status") or "") == "recording":
            return {"ok": True, "recording": existing, "already_active": True}

        ts = self._now_utc().replace(":", "").replace("-", "").replace("T", "-").replace("Z", "")
        filename = f"{sid}-{ts}.mp4"
        output_path = self._recordings_dir() / filename
        cmd = self._build_ffmpeg_command(
            output_path=output_path,
            input_url=str(input_url or "").strip(),
            codec=codec,
            test_source=bool(test_source),
        )
        proc = self._popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        status = "recording"
        pid = int(getattr(proc, "pid", 0) or 0)
        ended_at = ""
        if test_source and hasattr(proc, "wait"):
            try:
                proc.wait(timeout=20)
                status = "stopped"
                pid = 0
                ended_at = self._now_utc()
            except Exception:
                status = "recording"
        item = {
            "session_id": sid,
            "status": status,
            "codec": str(codec or "h264").strip().lower() or "h264",
            "path": str(output_path),
            "filename": filename,
            "pid": pid,
            "started_at": self._now_utc(),
            "ended_at": ended_at,
        }
        sessions[sid] = item
        self._save_index(index_payload)
        return {"ok": True, "recording": item, "already_active": False}

    def stop_recording(self, *, session_id: str) -> dict[str, Any]:
        sid = self._safe_slug(str(session_id or "").strip(), "session")
        index_payload = self._load_index()
        sessions = index_payload.setdefault("sessions", {})
        item = sessions.get(sid)
        if not isinstance(item, dict):
            return {"ok": False, "error": "recording not found"}
        pid = int(item.get("pid") or 0)
        if pid > 1:
            try:
                os.killpg(pid, signal.SIGTERM)
            except Exception:
                pass
        item["status"] = "stopped"
        item["ended_at"] = self._now_utc()
        item["pid"] = 0
        sessions[sid] = item
        self._save_index(index_payload)
        return {"ok": True, "recording": item}

    def get_recording(self, *, session_id: str) -> dict[str, Any] | None:
        sid = self._safe_slug(str(session_id or "").strip(), "session")
        index_payload = self._load_index()
        sessions = index_payload.setdefault("sessions", {})
        item = sessions.get(sid)
        return item if isinstance(item, dict) else None

    def read_recording_bytes(self, *, session_id: str) -> tuple[bytes, str] | None:
        item = self.get_recording(session_id=session_id)
        if not isinstance(item, dict):
            return None
        path = Path(str(item.get("path") or "").strip())
        if not path.exists() or not path.is_file():
            return None
        return path.read_bytes(), str(item.get("filename") or path.name)

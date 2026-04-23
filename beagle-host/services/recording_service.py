from __future__ import annotations

import os
import signal
import subprocess
from datetime import datetime, timedelta, timezone
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
        storage_backend: str = "local",
        storage_path: str = "",
        s3_bucket: str = "",
        s3_prefix: str = "recordings",
        s3_region: str = "us-east-1",
        s3_endpoint: str = "",
        s3_access_key: str = "",
        s3_secret_key: str = "",
        safe_slug: Callable[[str, str], str],
        write_json_file: Callable[..., None],
        now_epoch: Callable[[], float] | None = None,
    ) -> None:
        self._load_json_file = load_json_file
        self._now_utc = now_utc
        self._popen = popen
        self._recordings_dir = recordings_dir
        self._storage_backend = str(storage_backend or "local").strip().lower() or "local"
        self._storage_path = str(storage_path or "").strip()
        self._s3_bucket = str(s3_bucket or "").strip()
        self._s3_prefix = str(s3_prefix or "recordings").strip().strip("/") or "recordings"
        self._s3_region = str(s3_region or "us-east-1").strip() or "us-east-1"
        self._s3_endpoint = str(s3_endpoint or "").strip()
        self._s3_access_key = str(s3_access_key or "").strip()
        self._s3_secret_key = str(s3_secret_key or "").strip()
        self._safe_slug = safe_slug
        self._write_json_file = write_json_file
        self._now_epoch = now_epoch or (lambda: datetime.now(timezone.utc).timestamp())

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

    def _base_storage_dir(self) -> Path:
        if self._storage_path:
            p = Path(self._storage_path)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return self._recordings_dir()

    @staticmethod
    def _pool_id_from_session_id(session_id: str) -> str:
        sid = str(session_id or "").strip()
        if ":" in sid:
            return sid.split(":", 1)[0].strip()
        return ""

    @staticmethod
    def _parse_iso8601_utc(value: str) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

    def _s3_client(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 not installed for S3 recording storage") from exc
        kwargs: dict[str, Any] = {"region_name": self._s3_region}
        if self._s3_endpoint:
            kwargs["endpoint_url"] = self._s3_endpoint
        if self._s3_access_key and self._s3_secret_key:
            kwargs["aws_access_key_id"] = self._s3_access_key
            kwargs["aws_secret_access_key"] = self._s3_secret_key
        return boto3.client("s3", **kwargs)

    def _s3_key_for_filename(self, filename: str) -> str:
        return f"{self._s3_prefix}/{filename}"

    def _maybe_push_to_s3(self, item: dict[str, Any]) -> None:
        if self._storage_backend != "s3":
            return
        if not self._s3_bucket:
            raise RuntimeError("S3 backend selected but BEAGLE_RECORDING_S3_BUCKET is empty")
        path = Path(str(item.get("path") or "").strip())
        if not path.exists() or not path.is_file():
            return
        filename = str(item.get("filename") or path.name)
        key = self._s3_key_for_filename(filename)
        client = self._s3_client()
        body = path.read_bytes()
        client.put_object(Bucket=self._s3_bucket, Key=key, Body=body, ContentType="video/mp4")
        item["storage_backend"] = "s3"
        item["s3_bucket"] = self._s3_bucket
        item["s3_key"] = key

    def _read_from_s3(self, item: dict[str, Any]) -> bytes | None:
        bucket = str(item.get("s3_bucket") or self._s3_bucket).strip()
        key = str(item.get("s3_key") or "").strip()
        if not bucket or not key:
            return None
        client = self._s3_client()
        result = client.get_object(Bucket=bucket, Key=key)
        body = result.get("Body")
        if hasattr(body, "read"):
            return body.read()
        return None

    @staticmethod
    def _codec_args(codec: str) -> list[str]:
        c = str(codec or "h264").strip().lower()
        if c in {"h265", "hevc"}:
            return ["-c:v", "libx265"]
        return ["-c:v", "libx264"]

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        raw = str(text or "")
        raw = raw.replace("\\", "\\\\")
        raw = raw.replace(":", "\\:")
        raw = raw.replace("'", "\\'")
        raw = raw.replace("%", "\\%")
        return raw

    def _build_watermark_filter(self, *, username: str, custom_text: str, show_timestamp: bool) -> str:
        parts: list[str] = []
        user = str(username or "").strip()
        custom = str(custom_text or "").strip()
        if user:
            parts.append(f"user={user}")
        if custom:
            parts.append(custom)
        text = " | ".join(parts)
        if not show_timestamp and not text:
            return ""
        if show_timestamp:
            if text:
                text += " | "
            text += "%{gmtime\\:%Y-%m-%d %H\\:%M\\:%S UTC}"
        escaped = self._escape_drawtext(text)
        return (
            "drawtext="
            f"text='{escaped}':"
            "x=w-tw-28:y=h-th-24:"
            "fontcolor=white:fontsize=22:"
            "box=1:boxcolor=black@0.45:boxborderw=12"
        )

    def _build_ffmpeg_command(
        self,
        *,
        output_path: Path,
        input_url: str,
        codec: str,
        test_source: bool,
        watermark_enabled: bool,
        watermark_username: str,
        watermark_custom_text: str,
        watermark_show_timestamp: bool,
    ) -> list[str]:
        cmd = ["ffmpeg", "-y"]
        if test_source:
            cmd += ["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30"]
        elif input_url:
            cmd += ["-i", input_url]
        else:
            # Fallback for Linux hosts without explicit stream URL.
            cmd += ["-f", "x11grab", "-framerate", "30", "-i", ":0.0"]
        if watermark_enabled:
            watermark_filter = self._build_watermark_filter(
                username=watermark_username,
                custom_text=watermark_custom_text,
                show_timestamp=watermark_show_timestamp,
            )
            if watermark_filter:
                cmd += ["-vf", watermark_filter]
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
        watermark_enabled: bool = False,
        watermark_username: str = "",
        watermark_custom_text: str = "",
        watermark_show_timestamp: bool = True,
    ) -> dict[str, Any]:
        sid = self._safe_slug(str(session_id or "").strip(), "session")
        index_payload = self._load_index()
        sessions = index_payload.setdefault("sessions", {})
        existing = sessions.get(sid)
        if isinstance(existing, dict) and str(existing.get("status") or "") == "recording":
            return {"ok": True, "recording": existing, "already_active": True}

        ts = self._now_utc().replace(":", "").replace("-", "").replace("T", "-").replace("Z", "")
        filename = f"{sid}-{ts}.mp4"
        output_path = self._base_storage_dir() / filename
        cmd = self._build_ffmpeg_command(
            output_path=output_path,
            input_url=str(input_url or "").strip(),
            codec=codec,
            test_source=bool(test_source),
            watermark_enabled=bool(watermark_enabled),
            watermark_username=str(watermark_username or "").strip(),
            watermark_custom_text=str(watermark_custom_text or "").strip(),
            watermark_show_timestamp=bool(watermark_show_timestamp),
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
            "pool_id": self._pool_id_from_session_id(sid),
            "status": status,
            "codec": str(codec or "h264").strip().lower() or "h264",
            "path": str(output_path),
            "filename": filename,
            "pid": pid,
            "started_at": self._now_utc(),
            "ended_at": ended_at,
            "storage_backend": "local" if self._storage_backend in {"local", "nfs"} else self._storage_backend,
            "watermark_enabled": bool(watermark_enabled),
            "watermark_username": str(watermark_username or "").strip(),
            "watermark_custom_text": str(watermark_custom_text or "").strip(),
            "watermark_show_timestamp": bool(watermark_show_timestamp),
        }
        if status == "stopped":
            try:
                self._maybe_push_to_s3(item)
            except Exception:
                pass
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
        try:
            self._maybe_push_to_s3(item)
        except Exception:
            pass
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
        if str(item.get("storage_backend") or "").strip().lower() == "s3":
            try:
                s3_bytes = self._read_from_s3(item)
            except Exception:
                s3_bytes = None
            if s3_bytes is not None:
                return s3_bytes, str(item.get("filename") or "recording.mp4")
        path = Path(str(item.get("path") or "").strip())
        if not path.exists() or not path.is_file():
            return None
        return path.read_bytes(), str(item.get("filename") or path.name)

    def cleanup_expired_recordings(
        self,
        *,
        retention_days_for_pool: Callable[[str], int] | None = None,
        default_retention_days: int = 30,
    ) -> dict[str, Any]:
        index_payload = self._load_index()
        sessions = index_payload.setdefault("sessions", {})
        if not isinstance(sessions, dict):
            return {"ok": True, "deleted": []}

        now_dt = datetime.fromtimestamp(float(self._now_epoch()), tz=timezone.utc)
        deleted: list[dict[str, Any]] = []
        for sid, item in list(sessions.items()):
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "").strip().lower() == "recording":
                continue
            pool_id = str(item.get("pool_id") or self._pool_id_from_session_id(sid)).strip()
            if retention_days_for_pool is not None:
                try:
                    retention_days = int(retention_days_for_pool(pool_id))
                except Exception:
                    retention_days = int(default_retention_days)
            else:
                retention_days = int(default_retention_days)
            retention_days = max(1, min(retention_days, 3650))

            ended_at = self._parse_iso8601_utc(str(item.get("ended_at") or ""))
            if ended_at is None:
                ended_at = self._parse_iso8601_utc(str(item.get("started_at") or ""))
            if ended_at is None:
                continue
            if now_dt < ended_at + timedelta(days=retention_days):
                continue

            # Delete local file
            local_path = Path(str(item.get("path") or "").strip())
            if local_path.exists() and local_path.is_file():
                try:
                    local_path.unlink()
                except Exception:
                    pass

            # Delete S3 object if present
            if str(item.get("storage_backend") or "").strip().lower() == "s3":
                bucket = str(item.get("s3_bucket") or self._s3_bucket).strip()
                key = str(item.get("s3_key") or "").strip()
                if bucket and key:
                    try:
                        self._s3_client().delete_object(Bucket=bucket, Key=key)
                    except Exception:
                        pass

            deleted.append(
                {
                    "session_id": sid,
                    "pool_id": pool_id,
                    "filename": str(item.get("filename") or ""),
                    "retention_days": retention_days,
                }
            )
            del sessions[sid]

        if deleted:
            self._save_index(index_payload)
        return {"ok": True, "deleted": deleted}

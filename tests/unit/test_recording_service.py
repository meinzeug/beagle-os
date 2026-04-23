from __future__ import annotations

import sys
from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from recording_service import RecordingService


class _Proc:
    def __init__(self, pid: int) -> None:
        self.pid = pid


class _PopenStub:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        out_path = Path(cmd[-1])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"FAKE-MP4")
        return _Proc(4242)


def _load_json_file(path: Path, default):
    if not path.exists():
        return default
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_file(path: Path, payload, *, mode=0o600):
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _safe_slug(value: str, fallback: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(value or "").strip())
    text = text.strip("-._")
    return text or fallback


def test_start_stop_and_read_recording(tmp_path: Path) -> None:
    popen = _PopenStub()
    service = RecordingService(
        load_json_file=_load_json_file,
        now_utc=lambda: "2026-04-21T12:00:00Z",
        popen=popen,
        recordings_dir=lambda: tmp_path,
        safe_slug=_safe_slug,
        write_json_file=_write_json_file,
    )

    start = service.start_recording(session_id="sess-1", test_source=True, codec="h264")
    assert start["ok"] is True
    assert start["already_active"] is False
    assert start["recording"]["filename"].endswith(".mp4")
    assert len(popen.calls) == 1
    assert "ffmpeg" in popen.calls[0][0]

    read_back = service.read_recording_bytes(session_id="sess-1")
    assert read_back is not None
    data, filename = read_back
    assert data == b"FAKE-MP4"
    assert filename.endswith(".mp4")

    stop = service.stop_recording(session_id="sess-1")
    assert stop["ok"] is True
    assert stop["recording"]["status"] == "stopped"


def test_second_start_returns_already_active(tmp_path: Path) -> None:
    popen = _PopenStub()
    service = RecordingService(
        load_json_file=_load_json_file,
        now_utc=lambda: "2026-04-21T12:00:00Z",
        popen=popen,
        recordings_dir=lambda: tmp_path,
        safe_slug=_safe_slug,
        write_json_file=_write_json_file,
    )

    first = service.start_recording(session_id="sess-2", test_source=True)
    second = service.start_recording(session_id="sess-2", test_source=True)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["already_active"] is True
    assert len(popen.calls) == 1


def test_cleanup_expired_recordings_respects_pool_retention(tmp_path: Path) -> None:
    popen = _PopenStub()
    service = RecordingService(
        load_json_file=_load_json_file,
        now_utc=lambda: "2026-04-21T12:00:00Z",
        popen=popen,
        recordings_dir=lambda: tmp_path,
        storage_backend="local",
        storage_path=str(tmp_path),
        safe_slug=_safe_slug,
        write_json_file=_write_json_file,
        now_epoch=lambda: 1_777_000_000.0,
    )

    # Old recording (should be deleted for 7-day retention)
    old_path = tmp_path / "pool-a-1-old.mp4"
    old_path.write_bytes(b"old")
    # Recent recording (should survive)
    new_path = tmp_path / "pool-a-2-new.mp4"
    new_path.write_bytes(b"new")

    index_payload = {
        "sessions": {
            "pool-a:1": {
                "session_id": "pool-a:1",
                "pool_id": "pool-a",
                "status": "stopped",
                "path": str(old_path),
                "filename": "pool-a-1-old.mp4",
                "ended_at": "2025-12-01T00:00:00Z",
                "storage_backend": "local",
            },
            "pool-a:2": {
                "session_id": "pool-a:2",
                "pool_id": "pool-a",
                "status": "stopped",
                "path": str(new_path),
                "filename": "pool-a-2-new.mp4",
                "ended_at": "2026-04-20T00:00:00Z",
                "storage_backend": "local",
            },
        }
    }
    _write_json_file(tmp_path / "index.json", index_payload)

    cleanup = service.cleanup_expired_recordings(
        retention_days_for_pool=lambda pool_id: 7,
        default_retention_days=30,
    )
    assert cleanup["ok"] is True
    assert len(cleanup["deleted"]) == 1
    assert cleanup["deleted"][0]["session_id"] == "pool-a:1"
    assert not old_path.exists()
    assert new_path.exists()

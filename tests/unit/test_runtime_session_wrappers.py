from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SESSION_WRAPPER = ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "bin" / "start-pve-thin-client-session"
KIOSK_WRAPPER = ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "bin" / "start-pve-thin-client-kiosk-session"


def test_session_wrapper_starts_lock_screen_watcher() -> None:
    content = SESSION_WRAPPER.read_text(encoding="utf-8")
    assert "device_lock_screen.sh" in content
    assert "run_device_lock_screen_watcher" in content
    assert "lock-screen.log" in content


def test_kiosk_wrapper_starts_lock_screen_watcher() -> None:
    content = KIOSK_WRAPPER.read_text(encoding="utf-8")
    assert "device_lock_screen.sh" in content
    assert "run_device_lock_screen_watcher" in content
    assert "lock-screen.log" in content

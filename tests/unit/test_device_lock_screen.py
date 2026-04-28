from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "device_lock_screen.sh"


def test_lock_screen_watcher_creates_marker_when_locked(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "device.locked").write_text("locked\n", encoding="utf-8")
    marker_file = tmp_path / "lock.marker"

    env = os.environ.copy()
    env["BEAGLE_STATE_DIR"] = str(state_dir)
    env["BEAGLE_LOCK_SCREEN_SIMULATE"] = "1"
    env["BEAGLE_LOCK_SCREEN_ONCE"] = "1"
    env["BEAGLE_LOCK_SCREEN_MARKER_FILE"] = str(marker_file)

    cmd = f"source {SCRIPT}\nrun_device_lock_screen_watcher\n"
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, check=True)

    assert marker_file.read_text(encoding="utf-8").strip() == "active"


def test_lock_screen_watcher_clears_marker_when_unlocked(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    marker_file = tmp_path / "lock.marker"
    marker_file.write_text("active\n", encoding="utf-8")

    env = os.environ.copy()
    env["BEAGLE_STATE_DIR"] = str(state_dir)
    env["BEAGLE_LOCK_SCREEN_SIMULATE"] = "1"
    env["BEAGLE_LOCK_SCREEN_ONCE"] = "1"
    env["BEAGLE_LOCK_SCREEN_MARKER_FILE"] = str(marker_file)

    cmd = f"source {SCRIPT}\nrun_device_lock_screen_watcher\n"
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, check=True)

    assert not marker_file.exists()


def test_lock_screen_backend_prefers_wayland_lockers(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    swaylock = bindir / "swaylock"
    swaylock.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    swaylock.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["XDG_SESSION_TYPE"] = "wayland"

    cmd = f"source {SCRIPT}\nlock_screen_backend\n"
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)

    assert result.stdout.strip() == "wayland"


def test_lock_screen_backend_falls_back_to_x11_tools(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    zenity = bindir / "zenity"
    zenity.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    zenity.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["XDG_SESSION_TYPE"] = "x11"

    cmd = f"source {SCRIPT}\nlock_screen_backend\n"
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)

    assert result.stdout.strip() == "x11"

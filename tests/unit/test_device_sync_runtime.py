from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "device_sync.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_apply_runtime_sync_response_sets_lock_wipe_and_policy(tmp_path: Path) -> None:
    response = tmp_path / "sync.json"
    state_dir = tmp_path / "state"
    response.write_text(
        json.dumps(
            {
                "commands": {"lock_screen": True, "wipe_pending": True},
                "policy": {"policy_id": "corp", "screen_lock_timeout_seconds": 300},
            }
        ),
        encoding="utf-8",
    )

    cmd = (
        f"source {SCRIPT}\n"
        f"export BEAGLE_STATE_DIR={state_dir}\n"
        f"apply_runtime_sync_response {response}\n"
    )
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), check=True)

    assert (state_dir / "device.locked").exists()
    assert (state_dir / "device.wipe-pending").exists()
    policy = json.loads((state_dir / "device-policy.json").read_text(encoding="utf-8"))
    assert policy["policy_id"] == "corp"


def test_runtime_device_sync_payload_marks_wireguard_state(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    _write_stub(
        bindir / "nproc",
        "#!/usr/bin/env bash\nprintf '4\\n'\n",
    )

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    cmd = (
        f"source {SCRIPT}\n"
        "runtime_device_sync_payload endpoint-001 thin-01 wg-beagle 1 10.88.0.10/32\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["device_id"] == "endpoint-001"
    assert payload["vpn"]["active"] is True
    assert payload["vpn"]["assigned_ip"] == "10.88.0.10/32"
    assert "uptime_hours" in payload["metrics"]
    assert "reboot_count_7d" in payload["metrics"]
    assert "cpu_temp_c" in payload["metrics"]
    assert "network_errors" in payload["metrics"]


def test_runtime_device_sync_payload_includes_wipe_report(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    _write_stub(
        bindir / "nproc",
        "#!/usr/bin/env bash\nprintf '4\\n'\n",
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "device-wipe-report.json").write_text(
        json.dumps({"status": "completed", "artifacts_removed": 2}),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    cmd = (
        f"source {SCRIPT}\n"
        f"export BEAGLE_STATE_DIR={state_dir}\n"
        "runtime_device_sync_payload endpoint-001 thin-01 wg-beagle 0 ''\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    assert payload["reports"]["wipe"]["status"] == "completed"
    assert payload["reports"]["wipe"]["artifacts_removed"] == 2


def test_runtime_device_sync_payload_includes_runtime_report(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    _write_stub(
        bindir / "nproc",
        "#!/usr/bin/env bash\nprintf '4\\n'\n",
    )

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "device.locked").write_text("locked\n", encoding="utf-8")
    (state_dir / "device-lock-screen.marker").write_text("active\n", encoding="utf-8")
    (state_dir / "device-lock-screen.pid").write_text("1234\n", encoding="utf-8")
    (state_dir / "device-lock-screen.env").write_text(
        "BEAGLE_LOCK_SCREEN_RUNTIME_BACKEND=zenity\n"
        "BEAGLE_LOCK_SCREEN_RUNTIME_SESSION_TYPE=x11\n"
        "BEAGLE_LOCK_SCREEN_RUNTIME_DISPLAYS=:0,:1\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    cmd = (
        f"source {SCRIPT}\n"
        f"export BEAGLE_STATE_DIR={state_dir}\n"
        "runtime_device_sync_payload endpoint-001 thin-01 wg-beagle 0 ''\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)
    payload = json.loads(result.stdout)
    runtime_report = payload["reports"]["runtime"]
    assert runtime_report["lock_active"] is True
    assert runtime_report["lock_marker_present"] is True
    assert runtime_report["lock_watcher_pid_present"] is True
    assert runtime_report["lock_screen_backend"] == "zenity"
    assert runtime_report["session_type"] == "x11"
    assert runtime_report["x11_displays"] == [":0", ":1"]

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "device_state_enforcement.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def test_perform_device_wipe_clears_runtime_state_and_confirms(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    curl_log = tmp_path / "curl.log"
    _write_stub(
        bindir / "curl",
        "#!/usr/bin/env bash\n"
        "out=\"\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output\" ]]; then out=\"$2\"; shift 2; continue; fi\n"
        "  printf '%s\\n' \"$1\" >>\"" + str(curl_log) + "\"\n"
        "  shift\n"
        "done\n"
        "[[ -n \"$out\" ]] && printf '{}' >\"$out\"\n"
        "printf '200'\n",
    )

    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    user_home = tmp_path / "home" / "thinclient"
    config_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    user_home.mkdir(parents=True, exist_ok=True)
    (config_dir / "thinclient.conf").write_text("PVE_THIN_CLIENT_MODE=BEAGLE_STREAM_CLIENT\n", encoding="utf-8")
    (config_dir / "credentials.env").write_text("PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN=test\n", encoding="utf-8")
    (state_dir / "device.wipe-pending").write_text("wipe_pending\n", encoding="utf-8")
    (state_dir / "device.locked").write_text("locked\n", encoding="utf-8")
    (state_dir / "device-policy.json").write_text("{\"policy_id\":\"corp\"}\n", encoding="utf-8")
    (user_home / ".config" / "Beagle Stream Client Game Streaming Project").mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["CONFIG_DIR"] = str(config_dir)
    env["BEAGLE_STATE_DIR"] = str(state_dir)
    env["PVE_THIN_CLIENT_RUNTIME_USER"] = "tcstub"
    env["HOME"] = str(user_home)
    env["PVE_THIN_CLIENT_BEAGLE_MANAGER_URL"] = "https://manager.example"
    env["PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN"] = "manager-token"
    env["PVE_THIN_CLIENT_BEAGLE_DEVICE_ID"] = "endpoint-001"
    env["PVE_THIN_CLIENT_HOSTNAME"] = "thin-01"
    env["BEAGLE_WIPE_REBOOT"] = "0"

    cmd = f"source {SCRIPT}\nperform_device_wipe\n"
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, check=True)

    assert not (config_dir / "thinclient.conf").exists()
    assert not (config_dir / "credentials.env").exists()
    assert not (state_dir / "device.wipe-pending").exists()
    assert not (state_dir / "device.locked").exists()
    assert not (state_dir / "device-policy.json").exists()
    assert (state_dir / "device-wipe-report.json").exists()
    assert "/api/v1/endpoints/device/confirm-wiped" in curl_log.read_text(encoding="utf-8")
    report = json.loads((state_dir / "device-wipe-report.json").read_text(encoding="utf-8"))
    assert report["status"] in {"completed", "partial"}
    assert any(item["action"] == "runtime_secret_clear" for item in report["actions"])


def test_enforce_device_state_before_session_returns_wipe_marker_code(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "device.wipe-pending").write_text("wipe_pending\n", encoding="utf-8")

    env = os.environ.copy()
    env["BEAGLE_STATE_DIR"] = str(state_dir)
    env["BEAGLE_WIPE_REBOOT"] = "0"
    cmd = (
        f"source {SCRIPT}\n"
        "set +e\n"
        "enforce_device_state_before_session\n"
        "status=$?\n"
        "printf '%s' \"$status\"\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)

    assert result.stdout.strip() == "10"


def test_perform_device_wipe_attempts_storage_and_tpm_when_configured(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    install_device = tmp_path / "install.img"
    install_device.write_bytes(b"\0" * 1024)
    _write_stub(bindir / "sudo", "#!/usr/bin/env bash\nshift\n\"$@\"\n")
    _write_stub(bindir / "blkdiscard", "#!/usr/bin/env bash\nexit 1\n")
    _write_stub(bindir / "wipefs", "#!/usr/bin/env bash\nexit 0\n")
    _write_stub(bindir / "dd", "#!/usr/bin/env bash\nexit 0\n")
    _write_stub(bindir / "tpm2_clear", "#!/usr/bin/env bash\nexit 0\n")
    _write_stub(
        bindir / "curl",
        "#!/usr/bin/env bash\n"
        "out=\"\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ \"$1\" == \"--output\" ]]; then out=\"$2\"; shift 2; continue; fi\n"
        "  shift\n"
        "done\n"
        "[[ -n \"$out\" ]] && printf '{}' >\"$out\"\n"
        "printf '200'\n",
    )

    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    user_home = tmp_path / "home" / "thinclient"
    config_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    user_home.mkdir(parents=True, exist_ok=True)
    (config_dir / "thinclient.conf").write_text(
        f"PVE_THIN_CLIENT_INSTALL_DEVICE={install_device}\n",
        encoding="utf-8",
    )
    (config_dir / "credentials.env").write_text("PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN=test\n", encoding="utf-8")
    (state_dir / "device.wipe-pending").write_text("wipe_pending\n", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["CONFIG_DIR"] = str(config_dir)
    env["BEAGLE_STATE_DIR"] = str(state_dir)
    env["PVE_THIN_CLIENT_RUNTIME_USER"] = "tcstub"
    env["HOME"] = str(user_home)
    env["PVE_THIN_CLIENT_BEAGLE_MANAGER_URL"] = "https://manager.example"
    env["PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN"] = "manager-token"
    env["PVE_THIN_CLIENT_BEAGLE_DEVICE_ID"] = "endpoint-001"
    env["PVE_THIN_CLIENT_HOSTNAME"] = "thin-01"
    env["BEAGLE_WIPE_REBOOT"] = "0"
    env["BEAGLE_WIPE_ALLOW_REGULAR_FILE"] = "1"

    cmd = f"source {SCRIPT}\nperform_device_wipe\n"
    subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, check=True)

    report = json.loads((state_dir / "device-wipe-report.json").read_text(encoding="utf-8"))
    actions = {item["action"]: item for item in report["actions"]}
    assert actions["storage_wipe"]["status"] == "completed"
    assert actions["tpm_clear"]["status"] == "completed"

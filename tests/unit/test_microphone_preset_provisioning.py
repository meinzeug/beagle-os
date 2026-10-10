from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "thin-client-assistant/runtime"
sys.path.insert(0, str(ROOT / "beagle-host/services"))
sys.path.insert(0, str(RUNTIME))
from generate_config_from_preset import generate_config_dir_from_preset
from installer_script import InstallerScriptService
from materialize_usb_tunnel_keys import materialize_keys


def service() -> InstallerScriptService:
    # Opaque test data, never a deployed credential.
    return InstallerScriptService(
        build_profile=lambda vm: {},
        ensure_vm_secret=lambda vm: {
            "usb_tunnel_port": 43107,
            "usb_tunnel_audio_input_port": 43207,
            "usb_tunnel_camera_port": 53107,
            "usb_tunnel_private_key": "test-only-key\n",
        },
        fetch_beagle_stream_server_identity=lambda vm, user: {},
        get_vm_config=lambda node, vmid: {},
        hosted_installer_iso_file=Path("unused"),
        hosted_installer_template_file=Path("unused"),
        hosted_live_usb_template_file=Path("unused"),
        issue_enrollment_token=lambda vm: ("", {}),
        issue_installer_log_context=lambda **kw: {},
        manager_pinned_pubkey="",
        parse_description_meta=lambda text: {},
        patch_installer_defaults=lambda *a: "",
        patch_windows_installer_defaults=lambda *a: "",
        public_bootstrap_latest_download_url=lambda: "",
        public_installer_iso_url=lambda: "",
        public_manager_url="https://manager.example",
        public_payload_latest_download_url=lambda: "",
        public_server_name="tunnel.example",
        raw_shell_installer_template_file=Path("unused"),
        raw_windows_installer_template_file=Path("unused"),
        safe_hostname=lambda name, vmid: "test-vm",
        beagle_stream_server_guest_user=lambda vm, config: "",
        usb_tunnel_user="custom-tunnel",
        usb_tunnel_attach_host="192.0.2.1",
        usb_tunnel_known_host_line=lambda: "tunnel.example ssh-ed25519 TEST-ONLY\n",
    )


def test_generated_preset_bootstraps_mic_without_enrollment(tmp_path: Path) -> None:
    import shlex

    vm = SimpleNamespace(vmid=107, node="node", name="test", status="stopped")
    preset = service().build_preset(
        vm, {}, {}, enrollment_token="", manager_token="", thinclient_password=""
    )
    preset_file = tmp_path / "preset.env"
    preset_file.write_text(
        "".join(f"{k}={shlex.quote(v)}\n" for k, v in preset.items())
    )
    config = tmp_path / "state"
    generate_config_dir_from_preset(
        preset_file=preset_file,
        state_dir=config,
        installer_script=ROOT / "thin-client-assistant/installer/write-config.sh",
        runtime_user="thinclient",
    )
    tunnel_dir = tmp_path / "keys"
    # Exercise the runtime loader with the same generated files as first boot.
    command = 'source "$1/config_loader.sh"; find_config_dir() { printf "%s" "$2"; }; apply_runtime_mode_overrides() { :; }; load_runtime_config; printf "%s\\n" "$(cat "$PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_FILE")" "$PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PORT" "$PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT" "$PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_USER" "$PVE_THIN_CLIENT_BEAGLE_USB_ATTACH_HOST"'
    # The function's positional args differ from the outer shell: use env for discovery.
    command = command.replace('printf "%s" "$2"', 'printf "%s" "$TEST_CONFIG"')
    env = {
        **os.environ,
        "TEST_CONFIG": str(config),
        "RUNTIME_SCRIPT_DIR": str(RUNTIME),
        "PVE_THIN_CLIENT_USB_TUNNEL_KEY_DIR": str(tunnel_dir),
    }
    p = subprocess.run(
        ["bash", "-euc", command, "test", str(RUNTIME)],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == [
        "test-only-key",
        "43107",
        "43207",
        "custom-tunnel",
        "192.0.2.1",
    ]
    assert (tunnel_dir / "usb-tunnel.key").stat().st_mode & 0o777 == 0o600
    assert (config / "credentials.env").stat().st_mode & 0o777 == 0o600
    assert "PRIVATE_KEY_B64" not in (config / "thinclient.conf").read_text()
    assert (
        tunnel_dir / "usb-tunnel-known_hosts"
    ).read_text() == "tunnel.example ssh-ed25519 TEST-ONLY\n"


def test_materializer_preserves_enrolled_key(tmp_path: Path) -> None:
    cred = tmp_path / "credentials.env"
    cred.write_text(
        'PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_B64="'
        + base64.b64encode(b"old-preset").decode()
        + '"\n'
    )
    target = tmp_path / "keys"
    target.mkdir()
    p = target / "usb-tunnel.key"
    p.write_text("new-enrolled-key")
    materialize_keys(cred, target)
    assert p.read_text() == "new-enrolled-key"


@pytest.mark.parametrize(
    "value", ["!!!", base64.b64encode(b"\x00").decode(), "A" * 131073]
)
def test_invalid_material_is_rejected_without_writing_keys(
    tmp_path: Path, value: str
) -> None:
    cred = tmp_path / "credentials.env"
    cred.write_text(
        'PVE_THIN_CLIENT_BEAGLE_USB_TUNNEL_PRIVATE_KEY_B64="' + value + '"\n'
    )
    target = tmp_path / "keys"
    with pytest.raises(ValueError):
        materialize_keys(cred, target)
    assert not target.exists()


@pytest.mark.parametrize(
    "host,key,expected", [("", "", 75), ("tunnel.example", "/nonexistent", 75)]
)
def test_incomplete_tunnel_reports_retryable_failure(
    host: str, key: str, expected: int
) -> None:
    command = 'source "$1/beagle_usb_runtime_env.sh"; source "$1/beagle_usb_runtime_actions.sh"; usb_enabled() { echo 1; }; usb_host() { printf "%s" "$TEST_HOST"; }; usb_port() { echo 43100; }; usb_user() { echo test; }; usb_key_file() { printf "%s" "$TEST_KEY"; }; run_usb_tunnel_daemon'
    p = subprocess.run(
        ["bash", "-euc", command, "test", str(RUNTIME)],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "RUNTIME_SCRIPT_DIR": str(RUNTIME),
            "TEST_HOST": host,
            "TEST_KEY": key,
        },
    )
    assert p.returncode == expected
    assert "waiting for enrollment/heartbeat repair" in p.stderr


def test_linux_live_usb_writer_preserves_mic_credentials(tmp_path: Path) -> None:
    import shlex

    vm = SimpleNamespace(vmid=107, node="node", name="test", status="stopped")
    preset = service().build_preset(
        vm, {}, {}, enrollment_token="", manager_token="", thinclient_password=""
    )
    preset.update(
        PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_USERNAME="test-user",
        PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_SERVER_PASSWORD="test-only",
    )
    payload = "".join(f"{k}={shlex.quote(v)}\n" for k, v in preset.items())
    script = ROOT / "thin-client-assistant/usb/usb_writer_write_stage.sh"
    command = 'source "$1"; write_live_state_config "$2"'
    p = subprocess.run(
        ["bash", "-euc", command, "test", str(script), str(tmp_path)],
        env={
            **os.environ,
            "REPO_ROOT": str(ROOT),
            "PVE_THIN_CLIENT_PRESET_B64": base64.b64encode(payload.encode()).decode(),
        },
        check=False,
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    config = tmp_path / "pve-thin-client/state"
    keys = tmp_path / "keys"
    materialize_keys(config / "credentials.env", keys)
    assert (keys / "usb-tunnel.key").read_text() == "test-only-key\n"
    assert (
        'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT="43207"'
        in (config / "thinclient.conf").read_text()
    )


def test_explicitly_disabled_usb_exits_without_retry() -> None:
    command = 'source "$1/beagle_usb_runtime_env.sh"; source "$1/beagle_usb_runtime_actions.sh"; run_usb_tunnel_daemon'
    p = subprocess.run(
        ["bash", "-euc", command, "test", str(RUNTIME)],
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "RUNTIME_SCRIPT_DIR": str(RUNTIME),
            "PVE_THIN_CLIENT_BEAGLE_USB_ENABLED": "0",
        },
    )
    assert p.returncode == 0
    assert "usb disabled" in p.stderr

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

RUNTIME_DIR = ROOT_DIR / "thin-client-assistant" / "runtime"
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from thin_client_preset import build_runtime_extension_fields
from generate_config_from_preset import build_installer_env


def test_runtime_extension_fields_mark_broker_presets_with_broker_connection_method() -> None:
    payload = build_runtime_extension_fields(
        beagle_stream_mode="broker",
        beagle_stream_allocation_id="vm-100",
    )
    assert payload["PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD"] == "broker"


def test_build_installer_env_derives_broker_connection_method_from_stream_mode() -> None:
    env = build_installer_env(
        preset={
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_MODE": "broker",
            "PVE_THIN_CLIENT_PRESET_PROFILE_NAME": "vm-100",
        },
        runtime_user="thinclient",
    )
    assert env["CONNECTION_METHOD"] == "broker"


def test_build_installer_env_preserves_explicit_connection_method_override() -> None:
    env = build_installer_env(
        preset={
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_MODE": "broker",
            "PVE_THIN_CLIENT_PRESET_CONNECTION_METHOD": "direct",
        },
        runtime_user="thinclient",
    )
    assert env["CONNECTION_METHOD"] == "direct"


def test_build_installer_env_maps_stream_fallback_hosts_into_runtime_env() -> None:
    env = build_installer_env(
        preset={
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST": "46.4.96.80",
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL": "https://46.4.96.80:50001",
        },
        runtime_user="thinclient",
    )
    assert env["BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST"] == "46.4.96.80"
    assert env["BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL"] == "https://46.4.96.80:50001"


def test_build_installer_env_keeps_broker_mode_even_with_fallback_hosts() -> None:
    env = build_installer_env(
        preset={
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_MODE": "broker",
            "PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST": "46.4.96.80",
        },
        runtime_user="thinclient",
    )
    assert env["CONNECTION_METHOD"] == "broker"


def test_hostless_runtime_uses_enrollment_config_for_broker_mode() -> None:
    script = (RUNTIME_DIR / "beagle_stream_client_runtime_exec.sh").read_text(encoding="utf-8")

    assert 'if [[ "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOSTLESS:-0}" == "1" ]]; then' in script
    assert "control_plane=\"$(beagle_stream_enrollment_value control_plane" in script
    assert "token=\"$(beagle_stream_enrollment_value enrollment_token" in script
    assert "device_id=\"$(beagle_stream_enrollment_value device_id" in script
    assert "pool_id=\"$(beagle_stream_enrollment_value pool_id" not in script

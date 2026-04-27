from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICE_REGISTRY = ROOT / "beagle-host" / "services" / "service_registry.py"
PREPARE_HOST_DOWNLOADS = ROOT / "scripts" / "prepare-host-downloads.sh"
REFRESH_HOST_ARTIFACTS = ROOT / "scripts" / "refresh-host-artifacts.sh"
CHECK_BEAGLE_HOST = ROOT / "scripts" / "check-beagle-host.sh"
INSTALL_BEAGLE_PROXY = ROOT / "scripts" / "install-beagle-proxy.sh"


def test_service_registry_allows_beagle_proxy_env_to_override_host_env() -> None:
    script = SERVICE_REGISTRY.read_text(encoding="utf-8")

    assert "def load_env_defaults(path: str, *, override: bool = False) -> None:" in script
    assert 'load_env_defaults("/etc/beagle/host.env")' in script
    assert 'load_env_defaults("/etc/beagle/beagle-proxy.env", override=True)' in script


def test_host_download_scripts_load_proxy_env_after_host_env() -> None:
    prepare = PREPARE_HOST_DOWNLOADS.read_text(encoding="utf-8")
    refresh = REFRESH_HOST_ARTIFACTS.read_text(encoding="utf-8")
    check = CHECK_BEAGLE_HOST.read_text(encoding="utf-8")

    assert 'PROXY_ENV_FILE="${PVE_DCV_PROXY_ENV_FILE:-$CONFIG_DIR/beagle-proxy.env}"' in prepare
    assert 'source "$PROXY_ENV_FILE"' in prepare
    assert 'PROXY_ENV_FILE="${PVE_DCV_PROXY_ENV_FILE:-$CONFIG_DIR/beagle-proxy.env}"' in refresh
    assert 'source "$PROXY_ENV_FILE"' in refresh
    assert 'PROXY_ENV_FILE="${PVE_DCV_PROXY_ENV_FILE:-$CONFIG_DIR/beagle-proxy.env}"' in check
    assert 'source "$PROXY_ENV_FILE"' in check


def test_install_beagle_proxy_self_heals_stale_host_env_proxy_settings() -> None:
    script = INSTALL_BEAGLE_PROXY.read_text(encoding="utf-8")

    assert "sync_host_env_proxy_defaults()" in script
    assert 'PVE_DCV_PROXY_LISTEN_PORT' in script
    assert 'PVE_DCV_DOWNLOADS_BASE_URL' in script
    assert 'sync_host_env_proxy_defaults' in script.split("write_env_file", 1)[1]

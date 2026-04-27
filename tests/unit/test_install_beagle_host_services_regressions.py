from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install-beagle-host-services.sh"


def test_legacy_host_runtime_dir_uses_underscore_alias() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'HOST_RUNTIME_DIR="$INSTALL_DIR/beagle-host"' in script
    assert 'LEGACY_HOST_RUNTIME_DIR="$INSTALL_DIR/beagle_host"' in script


def test_host_runtime_repair_handles_self_symlink_and_uses_relative_alias() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "repair_host_runtime_links()" in script
    assert 'if [[ -L "$HOST_RUNTIME_DIR" ]]; then' in script
    assert 'rm -f "$HOST_RUNTIME_DIR"' in script
    assert 'install -d -m 0755 "$HOST_RUNTIME_DIR"' in script
    assert 'ln -sfn "beagle-host" "$LEGACY_HOST_RUNTIME_DIR"' in script

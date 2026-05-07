from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECK_SCRIPT = ROOT / "scripts" / "check-beaglestream-production-baseline.sh"


def test_baseline_checker_verifies_guest_stream_config_and_scheduler() -> None:
    content = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert 'VMID="${BEAGLE_STREAM_VMID:-100}"' in content
    assert 'SKIP_GUEST_CONFIG_CHECK="${BEAGLE_SKIP_GUEST_CONFIG_CHECK:-0}"' in content
    assert "---guest-stream-config---" in content
    assert "guest_exec_text(vmid, script)" in content
    assert "^encoder = software$" in content
    assert "^sw_preset = ultrafast$" in content
    assert "^sw_tune = zerolatency$" in content
    assert "^capture = kms$" in content
    assert "^minimum_fps_target = 60$" in content
    assert "^max_bitrate = 35000$" in content
    assert "^service=active$" in content
    assert "^nice=-10$" in content


def test_baseline_checker_supports_explicit_guest_config_skip() -> None:
    content = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert "--skip-guest-config-check" in content
    assert "BEAGLE_SKIP_GUEST_CONFIG_CHECK" in content
    assert 'if [[ "$SKIP_GUEST_CONFIG_CHECK" != "1" ]]; then' in content


def test_baseline_checker_can_require_wireguard_peer_handshake() -> None:
    content = CHECK_SCRIPT.read_text(encoding="utf-8")

    assert 'REQUIRE_WG_HANDSHAKE="${BEAGLE_REQUIRE_WG_HANDSHAKE:-0}"' in content
    assert 'WG_REQUIRED_ALLOWED_IP="${BEAGLE_WG_REQUIRED_ALLOWED_IP:-10.88.1.1/32}"' in content
    assert "--require-wg-handshake" in content
    assert "--wg-peer-allowed-ip" in content
    assert "wg_peer_latest_handshake=" in content
    assert "wg_peer_endpoint=" in content
    assert "NR > 1 && $4 == allowed" in content
    assert "NR > 1 && $5 == allowed" in content
    assert 'if [[ "$REQUIRE_WG_HANDSHAKE" == "1" ]]; then' in content
    assert "has no latest handshake" in content
    assert "has no endpoint" in content

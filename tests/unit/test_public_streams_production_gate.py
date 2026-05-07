from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECONCILE_SCRIPT = ROOT / "scripts" / "reconcile-public-streams.sh"
INSTALL_SCRIPT = ROOT / "scripts" / "install-beagle-host-services.sh"


def test_public_stream_reconciler_is_opt_in_and_cleans_legacy_table_by_default() -> None:
    content = RECONCILE_SCRIPT.read_text(encoding="utf-8")

    assert 'PUBLIC_STREAMS_ENABLED="${BEAGLE_PUBLIC_STREAMS_ENABLED:-0}"' in content
    assert 'if [[ ! "$PUBLIC_STREAMS_ENABLED" =~ ^(1|true|yes|on)$ ]]; then' in content
    assert 'nft delete table inet "$NFT_TABLE_NAME" >/dev/null 2>&1 || true' in content
    assert 'public_streams_enabled=0 legacy_public_stream_table_removed=1' in content


def test_host_service_installer_does_not_enable_public_stream_timer_by_default() -> None:
    content = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert 'if [[ "${BEAGLE_PUBLIC_STREAMS_ENABLED:-0}" =~ ^(1|true|yes|on)$ ]]; then' in content
    assert 'systemctl disable "$BEAGLE_PUBLIC_STREAM_TIMER"' in content
    assert 'start_units=("$TIMER_NAME" "$BEAGLE_CONTROL_SERVICE" "$BEAGLE_CLUSTER_AUTO_JOIN_SERVICE" "$BEAGLE_WIREGUARD_RECONCILE_PATH")' in content
    assert 'start_units+=("$BEAGLE_PUBLIC_STREAM_TIMER" "$BEAGLE_PUBLIC_STREAM_SERVICE")' in content
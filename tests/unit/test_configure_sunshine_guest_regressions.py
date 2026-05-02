from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "configure-sunshine-guest.sh"


def test_configure_sunshine_guest_disables_display_idle_and_lockers() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "/etc/X11/Xsession.d/19-beagle-lightdm-session-compat" in content
    assert 'if ! type has_option >/dev/null 2>&1; then' in content
    assert ': "${OPTIONFILE:=/etc/X11/Xsession.options}"' in content
    assert "/etc/X11/Xsession.d/90-beagle-disable-display-idle" in content
    assert 'xset -dpms >/dev/null 2>&1 || true' in content
    assert 'xset s off >/dev/null 2>&1 || true' in content
    assert 'xset s noblank >/dev/null 2>&1 || true' in content
    assert '/home/\\$GUEST_USER/.local' in content
    assert '/home/\\$GUEST_USER/.local/state' in content
    assert '/home/\\$GUEST_USER/.local/state/wireplumber' in content
    assert 'chown -R "\\$GUEST_USER:\\$GUEST_USER" "/home/\\$GUEST_USER/.config" "/home/\\$GUEST_USER/.local"' in content
    assert (
        '/home/$GUEST_USER/.config/autostart/light-locker.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/light-locker.desktop' in content
    )
    assert (
        '/home/$GUEST_USER/.config/autostart/xfce4-power-manager.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/xfce4-power-manager.desktop' in content
    )
    assert (
        '/home/$GUEST_USER/.config/autostart/xfce4-screensaver.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/xfce4-screensaver.desktop' in content
    )


def test_configure_sunshine_guest_prefers_beaglestream_server_package() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"' in content
    assert 'write_stream_runtime_status() {' in content
    assert "BEAGLE_STREAM_SERVER_DEFAULT_URL" in content
    assert "beagle-stream-server-latest-ubuntu-24.04-amd64.deb" in content
    assert "BeagleStream server package unavailable, falling back to upstream Sunshine package." in content
    assert 'stream_runtime_variant="beagle-stream-server"' in content
    assert 'stream_runtime_variant="sunshine-fallback"' in content
    assert 'write_stream_runtime_status "\\$stream_runtime_variant" "\\$stream_runtime_package_url"' in content
    assert 'curl -fsSLo "\\$tmpdir/sunshine.deb" "\\$BEAGLE_STREAM_SERVER_URL"' in content


def test_configure_sunshine_guest_detects_sunshine_exec_path_dynamically() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    # Binary path is detected at runtime — not hardcoded.
    # The script generates a guest script via heredoc, so $ is escaped as \$.
    assert 'SUNSHINE_EXEC="\\$(command -v sunshine 2>/dev/null || echo /usr/bin/sunshine)"' in content
    assert 'ExecStart=\\$SUNSHINE_EXEC' in content
    assert 'ExecStart=/usr/bin/sunshine' not in content
    assert 'ExecStart=/usr/local/bin/sunshine' not in content

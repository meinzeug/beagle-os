from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "configure-sunshine-guest.sh"


def test_configure_sunshine_guest_disables_display_idle_and_lockers() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "/etc/X11/Xsession.d/90-beagle-disable-display-idle" in content
    assert 'xset -dpms >/dev/null 2>&1 || true' in content
    assert 'xset s off >/dev/null 2>&1 || true' in content
    assert 'xset s noblank >/dev/null 2>&1 || true' in content
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

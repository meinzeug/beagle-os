from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIRSTBOOT_TEMPLATE = ROOT / "beagle-host" / "templates" / "ubuntu-beagle" / "firstboot-provision.sh.tpl"


def test_firstboot_repairs_interrupted_dpkg_between_apt_retries() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "for attempt in $(seq 1 4); do" in script
    assert 'repair_interrupted_dpkg || true\n    if "$@"; then' in script
    assert 'if repair_interrupted_dpkg; then\n        return 0' in script
    assert "audit_output=\"$(dpkg --audit 2>&1 || true)\"" in script
    assert "apt-get install -f -y || true" in script


def test_firstboot_repairs_dpkg_after_each_desktop_install_phase() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "x11vnc\n  repair_interrupted_dpkg\n  if [[ -n \"$DESKTOP_PACKAGES\" ]]; then" in script
    assert "apt_retry apt-get install -y --fix-missing ${DESKTOP_PACKAGES}\n    repair_interrupted_dpkg" in script
    assert "apt_retry apt-get install -y --fix-missing ${SOFTWARE_PACKAGES}\n    repair_interrupted_dpkg" in script
    assert "apt_retry apt-get install -y \"$TMPDIR_WORK/sunshine.deb\"\n  repair_interrupted_dpkg" in script


def test_firstboot_disables_display_idle_and_lockers_for_streaming() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "/etc/X11/Xsession.d/90-beagle-disable-display-idle" in script
    assert "xset -dpms >/dev/null 2>&1 || true" in script
    assert "xset s off >/dev/null 2>&1 || true" in script
    assert "xset s noblank >/dev/null 2>&1 || true" in script
    assert '"/home/$GUEST_USER/.config/autostart/light-locker.desktop"' in script
    assert '"/home/$GUEST_USER/.config/autostart/xfce4-power-manager.desktop"' in script
    assert '"/home/$GUEST_USER/.config/autostart/xfce4-screensaver.desktop"' in script
    assert '"/home/$GUEST_USER/.xprofile"' in script

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

    assert "xdg-utils\n  repair_interrupted_dpkg\n  systemctl enable --now qemu-guest-agent.service" in script
    assert "x11vnc\n  repair_interrupted_dpkg\n  if [[ -n \"$DESKTOP_PACKAGES\" ]]; then" in script
    assert "apt_retry apt-get install -y --fix-missing --no-install-recommends ${DESKTOP_PACKAGES}\n    repair_interrupted_dpkg" in script
    assert "apt_retry apt-get install -y --fix-missing --no-install-recommends ${SOFTWARE_PACKAGES}\n    repair_interrupted_dpkg" in script
    assert "apt_retry apt-get install -y --no-install-recommends \"$TMPDIR_WORK/sunshine.deb\"\n  repair_interrupted_dpkg" in script


def test_firstboot_installs_guest_agent_before_heavy_desktop_payload() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "apt_retry apt-get install -y --fix-missing --no-install-recommends \\\n    qemu-guest-agent" in script
    assert "systemctl enable --now qemu-guest-agent.service >/dev/null 2>&1 || true" in script
    assert script.index("qemu-guest-agent.service") < script.index("if [[ -n \"$DESKTOP_PACKAGES\" ]]; then")


def test_firstboot_prefers_beaglestream_server_package() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert 'STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"' in script
    assert 'write_stream_runtime_status() {' in script
    assert 'BEAGLE_STREAM_SERVER_URL="__BEAGLE_STREAM_SERVER_URL__"' in script
    assert 'curl -fsSLo "$TMPDIR_WORK/sunshine.deb" "$BEAGLE_STREAM_SERVER_URL"' in script
    assert "BeagleStream server package unavailable, falling back to upstream Sunshine package." in script
    assert 'stream_runtime_variant="beagle-stream-server"' in script
    assert 'stream_runtime_variant="sunshine-fallback"' in script
    assert 'write_stream_runtime_status "$stream_runtime_variant" "$stream_runtime_package_url"' in script
    assert 'curl -fsSLo "$TMPDIR_WORK/sunshine.deb" "$SUNSHINE_URL"' in script


def test_firstboot_disables_display_idle_and_lockers_for_streaming() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "/etc/X11/Xsession.d/19-beagle-lightdm-session-compat" in script
    assert "if ! type has_option >/dev/null 2>&1; then" in script
    assert ': "${OPTIONFILE:=/etc/X11/Xsession.options}"' in script
    assert "/etc/X11/Xsession.d/90-beagle-disable-display-idle" in script
    assert "xset -dpms >/dev/null 2>&1 || true" in script
    assert "xset s off >/dev/null 2>&1 || true" in script
    assert "xset s noblank >/dev/null 2>&1 || true" in script
    assert '"/home/$GUEST_USER/.config/autostart/light-locker.desktop"' in script
    assert '"/home/$GUEST_USER/.config/autostart/xfce4-power-manager.desktop"' in script
    assert '"/home/$GUEST_USER/.config/autostart/xfce4-screensaver.desktop"' in script
    assert '"/home/$GUEST_USER/.xprofile"' in script


def test_firstboot_contains_plasma_profile_and_wallpaper_flow() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert 'DESKTOP_THEME_VARIANT="__DESKTOP_THEME_VARIANT__"' in script
    assert 'DESKTOP_WALLPAPER_FILENAME="__DESKTOP_WALLPAPER_FILENAME__"' in script
    assert '"/var/lib/beagle/seed/${DESKTOP_WALLPAPER_FILENAME}"' in script
    assert '"/var/lib/cloud/seed/nocloud/${DESKTOP_WALLPAPER_FILENAME}"' in script
    assert 'install -m 0644 "$source_path" "$BEAGLE_WALLPAPER_DIR/$DESKTOP_WALLPAPER_FILENAME"' in script
    assert 'configure_plasma_profile() {' in script
    assert r'plasma-apply-lookandfeel -a "\$LOOK_AND_FEEL"' in script
    assert r'plasma-apply-wallpaperimage "\$WALLPAPER_PATH"' in script
    assert 'OnlyShowIn=KDE;' in script


def test_user_data_template_embeds_wallpaper_asset_via_write_files() -> None:
    template = (ROOT / "beagle-host" / "templates" / "ubuntu-beagle" / "user-data.tpl").read_text(encoding="utf-8")

    assert "__DESKTOP_WALLPAPER_WRITE_FILE__" in template
    assert "write_files:" in template

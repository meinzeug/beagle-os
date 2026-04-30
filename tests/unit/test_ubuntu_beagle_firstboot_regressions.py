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

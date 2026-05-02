from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_trace_guard_script_disables_xtrace() -> None:
    content = (ROOT / "scripts" / "lib" / "trace-guard.sh").read_text(encoding="utf-8")

    assert "set +x" in content
    assert "BEAGLE_TRACE_GUARD_ACTIVE=1" in content
    assert "beagle-trace-guard" in content


def test_sensitive_scripts_source_trace_guard() -> None:
    files = [
        ROOT / "scripts" / "install-beagle-host.sh",
        ROOT / "scripts" / "install-beagle-host-services.sh",
        ROOT / "scripts" / "install-beagle-proxy.sh",
        ROOT / "scripts" / "install-beagle-host-postinstall.sh",
        ROOT / "scripts" / "configure-beagle-stream-server-guest.sh",
        ROOT / "scripts" / "build-beagle-os.sh",
        ROOT / "scripts" / "prepare-host-downloads.sh",
        ROOT / "thin-client-assistant" / "runtime" / "runtime_endpoint_enrollment.sh",
        ROOT / "thin-client-assistant" / "runtime" / "enrollment_wireguard.sh",
        ROOT / "thin-client-assistant" / "installer" / "setup-menu.sh",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "trace-guard.sh" in text, f"missing trace guard in {path}"
        assert "beagle_trace_guard_disable_xtrace_if_sensitive" in text, f"missing guard call in {path}"

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_install_beagle_proxy_disables_hsts_for_bootstrap_self_signed_tls() -> None:
    script = (ROOT / "scripts" / "install-beagle-proxy.sh").read_text(encoding="utf-8")

    assert 'BEAGLE_ENABLE_HSTS="${BEAGLE_ENABLE_HSTS:-auto}"' in script
    assert 'subject="$(openssl x509 -in "$CERT_FILE" -noout -subject' in script
    assert 'issuer="$(openssl x509 -in "$CERT_FILE" -noout -issuer' in script
    assert '[[ "$subject" != "$issuer" ]]' in script
    assert 'HSTS disabled until a CA-issued certificate replaces the bootstrap self-signed cert.' in script
    assert 'BEAGLE_ENABLE_HSTS=auto /opt/beagle/scripts/install-beagle-proxy.sh' in script


def test_control_plane_hsts_header_is_gated_by_runtime_flag() -> None:
    request_mixin = (ROOT / "beagle-host" / "services" / "request_handler_mixin.py").read_text(encoding="utf-8")
    service_registry = (ROOT / "beagle-host" / "services" / "service_registry.py").read_text(encoding="utf-8")

    assert 'if bool(getattr(_svc_registry, "HSTS_ENABLED", False)):' in request_mixin
    assert 'HSTS_ENABLED = os.environ.get("BEAGLE_ENABLE_HSTS", "0").strip().lower() in {"1", "true", "yes", "on"}' in service_registry

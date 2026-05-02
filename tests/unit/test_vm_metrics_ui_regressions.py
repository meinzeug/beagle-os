from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VM_METRICS_JS = ROOT / "website" / "ui" / "vm_metrics.js"


def test_vm_metrics_ui_renders_extended_cards_and_banner() -> None:
    js = VM_METRICS_JS.read_text(encoding="utf-8")

    assert "VM Status" in js
    assert "Gast-Agent" in js
    assert "vCPU" in js
    assert "vdp-m-disk-total-io" in js
    assert "vdp-m-net-total-io" in js
    assert "vdp-metrics-banner" in js


def test_vm_metrics_ui_handles_structured_sse_error_events() -> None:
    js = VM_METRICS_JS.read_text(encoding="utf-8")

    assert "es.addEventListener('error'" in js
    assert "Live-Metriken nicht verfuegbar:" in js
    assert "Live-SSE unterbrochen. Browser versucht die Verbindung erneut." in js
    assert "statusEl.textContent = 'Live';" in js

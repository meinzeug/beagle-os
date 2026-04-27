from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VIRTUALIZATION_JS = ROOT / "website" / "ui" / "virtualization.js"
EVENTS_JS = ROOT / "website" / "ui" / "events.js"
INDEX_HTML = ROOT / "website" / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_gpu_card_events_are_bound_to_current_card_container() -> None:
    events = _read(EVENTS_JS)

    assert "virtualization-gpu-cards" in events
    assert "virtualization-gpus-body" not in events
    assert "data-gpu-assign" in events
    assert "data-gpu-release" in events


def test_gpu_wizard_payload_and_safety_ack_are_rendered() -> None:
    js = _read(VIRTUALIZATION_JS)

    assert "gpu-wizard-steps" in js
    assert "gpu-action-ack" in js
    assert "gpu-action-payload" in js
    assert "Bestaetigung fehlt" in js
    assert "postJson(path, payload)" in js


def test_virtualization_gpu_mutations_use_api_relative_paths() -> None:
    js = _read(VIRTUALIZATION_JS)

    assert "postJson('/virtualization/mdev/create'" in js
    assert "postJson('/virtualization/sriov/'" in js
    assert "request('/virtualization/sriov'" in js
    assert "'/api/v1/virtualization/mdev" not in js
    assert "'/api/v1/virtualization/sriov" not in js


def test_vgpu_and_sriov_empty_states_are_cards_not_tables() -> None:
    html = _read(INDEX_HTML)

    assert 'class="gpu-subcard-grid" id="vgpu-types-body"' in html
    assert 'class="gpu-subcard-grid" id="vgpu-instances-body"' in html
    assert 'class="gpu-subcard-grid" id="sriov-devices-body"' in html
    assert '<tbody id="vgpu-types-body">' not in html
    assert '<tbody id="sriov-devices-body">' not in html

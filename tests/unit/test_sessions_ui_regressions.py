from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_sessions_stream_tuning_uses_canonical_netbridge_presets() -> None:
    script = (ROOT / "website" / "ui" / "sessions.js").read_text(encoding="utf-8")
    html = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "website" / "styles" / "_modals.css").read_text(encoding="utf-8")

    for preset in ("auto", "lan-ultra", "smooth", "balanced", "economy", "survival"):
        assert f'data-stream-preset="{preset}"' in html

    for legacy in ("slow_dsl", "fast", "sharp"):
        assert f'data-stream-preset="{legacy}"' not in html

    assert "fast: 'smooth'" in script
    assert "slow_dsl: 'economy'" in script
    assert "sharp: 'lan-ultra'" in script
    assert "function canonicalPreset" in script
    assert "function bitrateLabel" in script
    assert "function fpsLabel" in script
    assert "function checkedBool" in script
    assert '<option value="auto">Automatisch</option>' in html
    assert ".stream-preset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));" in css

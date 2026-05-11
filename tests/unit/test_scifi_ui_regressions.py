"""Regression guards for the Sci-Fi HUD layer and command palette."""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBSITE = REPO_ROOT / "website"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_styles_imports_scifi_layer_last():
    css = _read(WEBSITE / "styles.css")
    assert '_scifi.css' in css, "styles.css must import the sci-fi layer"
    # _scifi.css must come after _modern.css for highest precedence.
    assert css.index('_modern.css') < css.index('_scifi.css'), (
        "_scifi.css import must come after _modern.css"
    )


def test_scifi_css_contains_core_markers():
    css = _read(WEBSITE / "styles" / "_scifi.css")
    for marker in (
        ".scifi-hud",
        ".scifi-corner",
        ".scifi-statusbar",
        ".scifi-cmdk",
        ".scifi-cmdk-input",
        "@keyframes scifiGridShift",
        "prefers-reduced-motion",
    ):
        assert marker in css, f"_scifi.css missing marker: {marker}"


def test_scifi_hud_module_exports_initializer_and_palette():
    js = _read(WEBSITE / "ui" / "scifi_hud.js")
    for marker in (
        "export function initScifiHud",
        "data-scifi-command-palette",
        "Ctrl",
        "runProvisionQuickIntent",
        "setActivePanel",
        "Thinclient VM mieten",
        "Dedicated Server mieten",
    ):
        assert marker in js, f"scifi_hud.js missing marker: {marker}"


def test_main_js_initializes_scifi_hud():
    js = _read(WEBSITE / "main.js")
    assert "import { initScifiHud } from './ui/scifi_hud.js';" in js
    assert "initScifiHud();" in js

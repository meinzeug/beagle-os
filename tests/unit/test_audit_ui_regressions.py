from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "website" / "index.html"
AUDIT_JS = ROOT / "website" / "ui" / "audit.js"
AUDIT_CSS = ROOT / "website" / "styles" / "panels" / "_audit.css"


def test_audit_panel_contains_live_filter_builder_and_failure_sections() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="audit-section"' in html
    assert 'id="audit-filter-range"' in html
    assert 'id="audit-filter-user"' in html
    assert 'id="audit-filter-action"' in html
    assert 'id="audit-filter-resource"' in html
    assert 'id="audit-export-targets"' in html
    assert 'id="audit-builder-format"' in html
    assert 'id="audit-compliance-reports"' in html
    assert 'id="audit-failures-body"' in html


def test_audit_js_handles_redaction_targets_report_builder_and_replay() -> None:
    js = AUDIT_JS.read_text(encoding="utf-8")

    assert "function redactAuditDetail(value)" in js
    assert "renderAuditExportTargets(targets)" in js
    assert "renderAuditFailureQueue(failures)" in js
    assert "runAuditReportBuilder()" in js
    assert "testAuditExportTarget(target)" in js
    assert "replayAuditFailures()" in js
    assert "Audit-Exportziel getestet" in js
    assert "Audit-Replay abgeschlossen" in js
    assert "redacted" in js
    assert "request('/audit/export-targets/'" in js
    assert "request('/audit/failures/replay'" in js


def test_audit_styles_cover_targets_builder_and_reports() -> None:
    css = AUDIT_CSS.read_text(encoding="utf-8")

    assert ".audit-targets-list" in css
    assert ".audit-target-card" in css
    assert ".audit-builder-grid" in css
    assert ".audit-builder-step" in css
    assert ".audit-report-card" in css
    assert ".audit-compliance-list" in css

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
JOBS_PANEL_JS = ROOT / "website" / "ui" / "jobs_panel.js"


def test_jobs_panel_uses_backend_stream_endpoint_with_access_token() -> None:
    js = JOBS_PANEL_JS.read_text(encoding="utf-8")

    assert "'/jobs/' + encodeURIComponent(jobId) + '/stream'" in js
    assert "searchParams.set('access_token', state.token)" in js
    assert "/events" not in js


def test_jobs_panel_handles_generic_and_named_sse_events() -> None:
    js = JOBS_PANEL_JS.read_text(encoding="utf-8")

    assert "addEventListener('message', handleMessage)" in js
    assert "addEventListener('job_update', handleMessage)" in js
    assert "addEventListener('job_done', handleMessage)" in js
    assert "status === 'completed'" in js

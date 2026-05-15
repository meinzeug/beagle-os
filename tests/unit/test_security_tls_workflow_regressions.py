from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_security_tls_workflow_ignores_binary_matches_while_scanning() -> None:
    workflow = (ROOT / ".github" / "workflows" / "security-tls-check.yml").read_text(encoding="utf-8")

    assert "grep -RInI --binary-files=without-match \\" in workflow
    assert "grep -RInI --binary-files=without-match 'verify=False' \\" in workflow
    assert "tls-bypass-allowlist:" in workflow

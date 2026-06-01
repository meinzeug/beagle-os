from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_security_secrets_check_enforces_agents_md_untracked() -> None:
    script = (ROOT / "scripts" / "security-secrets-check.sh").read_text(encoding="utf-8")

    assert "ls-files --error-unmatch AGENTS.md" in script
    assert "AGENTS.md must stay untracked" in script


def test_gitignore_keeps_agents_md_local_only() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "/AGENTS.md" in gitignore

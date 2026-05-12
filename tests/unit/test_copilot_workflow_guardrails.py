from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_copilot_autofix_only_creates_issues_for_main_failures() -> None:
    workflow = (ROOT / ".github" / "workflows" / "copilot-autofix.yml").read_text(encoding="utf-8")

    assert "- lint" in workflow
    assert "- tests" in workflow
    assert "- build-iso" not in workflow
    assert "- release" not in workflow
    assert "- public-website" not in workflow
    assert "github.event.workflow_run.conclusion == 'failure' && github.event.workflow_run.head_branch == 'main'" in workflow


def test_copilot_automerge_only_runs_for_copilot_branches() -> None:
    workflow = (ROOT / ".github" / "workflows" / "copilot-automerge.yml").read_text(encoding="utf-8")

    assert "- lint" in workflow
    assert "- tests" in workflow
    assert "- build-iso" not in workflow
    assert "- release" not in workflow
    assert "- public-website" not in workflow
    assert "github.event.workflow_run.conclusion == 'success' && startsWith(github.event.workflow_run.head_branch, 'copilot/')" in workflow
    assert "github.event.workflow_run.conclusion == 'action_required' && startsWith(github.event.workflow_run.head_branch, 'copilot/')" in workflow


def test_copilot_automerge_requires_full_pr_check_set_before_merge() -> None:
    script = (ROOT / "scripts" / "merge-copilot-autofix-pr.sh").read_text(encoding="utf-8")

    assert "statusCheckRollup" in script
    assert 'if [[ "$checks_ready" != "ok" ]]; then' in script
    assert "not auto-approving or merging" in script
    assert "pytest (Python 3.11)" in script
    assert "pytest (Python 3.12)" in script
    assert "eslint (JS lint)" in script
    assert "Reject new legacy provider references" in script
    assert "No insecure TLS bypass" in script


def test_lint_workflow_knows_webextension_globals() -> None:
    workflow = (ROOT / ".github" / "workflows" / "lint.yml").read_text(encoding="utf-8")

    assert "extension/*.js" in workflow
    assert "...globals.webextensions" in workflow

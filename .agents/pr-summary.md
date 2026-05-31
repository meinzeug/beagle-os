# PR Summary (draft)

## Title

feat(release): support prerelease semver in resolve-release-version and expose release_class

## Summary

- Extend `scripts/resolve-release-version.sh` to accept:
  - stable: `x.y.z`
  - prerelease: `x.y.z-alpha.N`, `x.y.z-beta.N`, `x.y.z-rc.N`
- Add `release_class` GitHub output with values `stable` or `prerelease`.
- Keep auto-bump fallback on stable SemVer core.
- Add regression tests for stable, prerelease, tag-ref prerelease, and invalid four-part versions.

## Test Evidence

- `bash -n scripts/resolve-release-version.sh`
- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_release_workflow_regressions.py`
- Result: `8 passed`

## Risks

- Workflow wiring for prerelease publishing behavior is still pending (`release.yml`, `public-website.yml`).
- `sync-release-version.py` currently still enforces strict `x.y.z` and must be adapted in a follow-up PR slice.

## Follow-up

1. Consume `release_class` in release workflow and enforce `--prerelease --latest=false`.
2. Skip public stable deployment for prerelease runs.
3. Extend version sync logic and tests for extension `version_name` handling.
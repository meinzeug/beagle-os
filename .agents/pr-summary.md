# PR Summary (draft)

## Title

feat(release): wire prerelease channels across resolver, workflows, and version sync

## Summary

- Extend `scripts/resolve-release-version.sh` to support stable + prerelease SemVer and emit `release_class`.
- Wire `release_class` through `.github/workflows/release.yml`:
  - prerelease releases use `--prerelease --latest=false`.
  - public deploy job is blocked for prerelease runs.
- Update `.github/workflows/public-website.yml` to skip deployment/verification for prerelease versions.
- Extend `scripts/sync-release-version.py`:
  - accepts prerelease SemVer,
  - writes full product version to `VERSION`, kiosk metadata, and web cache-busting,
  - keeps extension `manifest.version` numeric core and writes full product version to `version_name`.
- Harden `scripts/create-github-release.sh` with release class detection/validation and stable/prerelease release mode args.

## Additional Tasks Delivered

1. Added `tests/unit/test_sync_release_version.py`.
2. Added `tests/unit/test_public_website_workflow_regressions.py`.
3. Added `tests/unit/test_create_github_release_script_regressions.py`.
4. Extended `tests/unit/test_release_workflow_regressions.py` for release-class/deploy guards.
5. Added strict `BEAGLE_RELEASE_CLASS` validation in manual release helper.

## Test Evidence

- `bash -n scripts/resolve-release-version.sh`
- `bash -n scripts/create-github-release.sh`
- `python3 -m pytest -q tests/unit/test_resolve_release_version_script.py tests/unit/test_sync_release_version.py tests/unit/test_release_workflow_regressions.py tests/unit/test_public_website_workflow_regressions.py tests/unit/test_create_github_release_script_regressions.py`
- Result: `17 passed`

## Risks

- End-to-end behavior on real GitHub Actions prerelease tag runs should be observed once after merge.

## Follow-up

1. Trigger one prerelease workflow run and document evidence for no stable mirror overwrite.
2. Verify release edit path for existing tags in CI logs.
# Contributing to Beagle OS

## Overview

Beagle OS is an open-source virtualization platform built on libvirt/KVM.
This document describes how to set up a development environment, run tests,
follow the branching strategy, and submit changes.

---

## Development Environment

### Requirements

- Debian 12 (Bookworm) or Ubuntu 22.04+
- Python 3.11 or 3.12
- `libvirt-dev`, `pkg-config` (for libvirt Python bindings in integration tests)
- `pytest`, `pytest-cov`, `cryptography`, `aiohttp` (install via pip)

### Setup

```bash
git clone https://github.com/beagle-os/beagle-os.git
cd beagle-os

pip install pytest pytest-cov pytest-timeout cryptography aiohttp
```

No build step is required — Python source is run directly.

---

## Running Tests

### Unit Tests (no external dependencies)

```bash
PYTHONPATH=. python -m pytest tests/unit/ -q --timeout=60
```

Expected: all tests pass except for GPU-related tests (require NVIDIA hardware).

### Smoke Tests (requires a running control plane)

```bash
BEAGLE_CONTROL_PLANE_BASE_URL=http://127.0.0.1:9088 bash scripts/smoke-control-plane-api.sh
```

Expected: 31/31 checks pass.

### Linting

```bash
bash .github/scripts/lint.sh        # or run the lint CI workflow locally via act
```

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code. All PRs target `main`. |
| `feature/<name>` | New features or refactoring |
| `fix/<name>` | Bug fixes |
| `docs/<name>` | Documentation-only changes |

Direct pushes to `main` are restricted. All changes go through pull requests.

### Branch Protection Rules (GitHub)

- Require PR before merging
- Require status checks: `pytest (3.11)`, `pytest (3.12)`, `lint`, `no-proxmox-references`
- Require branches to be up to date before merging
- No force pushes

---

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`

**Scopes:** `control-plane`, `beagle-host`, `beagle-kiosk`, `ci`, `gofuture`, `goadvanced`, `scripts`, `docs`

**Examples:**
```
feat(control-plane): add backups HTTP surface
fix(beagle-host): correct auth check in network POST endpoints
docs(gofuture): mark plan05 schritt4 complete
ci: add build-iso.yml workflow
```

---

## CI Pipeline Overview

All pipelines live in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `tests.yml` | push/PR to `main` | pytest (Python 3.11 + 3.12) |
| `lint.yml` | push/PR to `main` | flake8 + shellcheck |
| `no-proxmox-references.yml` | push/PR to `main` | Ensures no new Proxmox-specific code |
| `security-audit.yml` | push/PR to `main` | Dependency vulnerability scan |
| `security-tls-check.yml` | push/PR to `main` | TLS configuration checks |
| `security-subprocess-check.yml` | push/PR to `main` | Subprocess safety checks |
| `security-secrets-check.yml` | push/PR to `main` | Secret leakage detection |
| `build-iso.yml` | push to `main` (installer paths), manual | Build installimage tarball (auto) or ISO (manual) |
| `release.yml` | push tag `v*` | Build ISO + installimage, create GitHub Release |

### Creating a Release

1. Update `VERSION` with the new version number (e.g. `6.8.0`)
2. Update `CHANGELOG.md` with release notes
3. Commit: `git commit -m "chore: release v6.8.0"`
4. Tag: `git tag v6.8.0 && git push origin v6.8.0`

The `release.yml` workflow will automatically build artifacts and create a GitHub Release.

---

## Architecture

See [`docs/architecture.md`](architecture.md) for the overall system design.

Key directories:

| Directory | Contents |
|-----------|---------|
| `beagle-host/bin/` | `beagle-control-plane.py` — HTTP API server |
| `beagle-host/services/` | Business logic + HTTP surface modules |
| `beagle-host/providers/` | Provider contract + registry |
| `providers/beagle/` | libvirt/KVM provider implementation |
| `core/` | Shared types and platform abstractions |
| `tests/unit/` | Unit tests (pytest) |
| `scripts/` | Build, install, and smoke test scripts |
| `docs/gofuture/` | Feature development plans (Plans 01–20) |

---

## Security

- No Proxmox code — see [`docs/gofuture/05-provider-abstraction.md`](gofuture/05-provider-abstraction.md)
- All HTTP endpoints require authentication (`_is_authenticated()`) except `/healthz`, `/api/v1/health`, `/api/v1/auth/login`, `/api/v1/auth/onboarding/status`
- Security findings are documented in [`docs/refactor/11-security-findings.md`](refactor/11-security-findings.md)
- Report vulnerabilities privately to the maintainers before opening a public issue

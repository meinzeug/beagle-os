# Beagle OS

Beagle OS is a standalone virtualization and streaming platform built around KVM/libvirt, a host control plane, and reproducible endpoint media.

This repository contains the host services, provider implementation, endpoint tooling, website/docs, and validation assets used to run and release Beagle OS.

## Product Scope

Beagle OS currently focuses on one primary operating model:

- Standalone Beagle host running KVM/libvirt
- WebUI and API for VM and endpoint operations
- Endpoint media generation and enrollment
- BeagleStream runtime validation and operations
- Release and security evidence workflows

The active virtualization provider path is providers/beagle.

## Repository Overview

- beagle-host: host control plane, web services, templates and runtime scripts
- core: shared contracts, provider interfaces, persistence, validation and security components
- providers/beagle: active provider implementation for KVM/libvirt
- thin-client-assistant: endpoint runtime and build helpers
- beagle-os: endpoint profile and overlay assets
- scripts: installation, build, healthcheck, artifact and operations tooling
- tests: unit, integration, bats and e2e test suites
- public-site and website: beagle-os.com content and frontend assets
- docs: engineering, operations, security, runbooks and release planning docs

## Quick Start For Contributors

1. Clone and inspect the repository.
2. Read docs/README.md and docs/lasthope/05-diamond-plan.md for active priorities.
3. Run local checks for the area you touched.
4. Keep changes incremental and reproducible.

Example baseline commands:

```bash
git clone https://github.com/meinzeug/beagle-os.git
cd beagle-os
python3 -m pytest -q tests/unit/test_storage_pool_path_regressions.py
node --check scripts/capture-webui-doc-assets.mjs
```

## Host Installation Path

For host installation and validation, use repository scripts and runbooks:

```bash
scripts/install-beagle-host.sh
scripts/check-beagle-host.sh
```

Reference docs:

- docs/runbooks/installation.md
- docs/deployment/hetzner-installimage.md
- public-site/docs/getting-started/index.html

## Build And Artifact Workflows

Common build entry points:

```bash
scripts/build-server-installer.sh
scripts/build-server-installimage.sh
scripts/build-thin-client-installer.sh
scripts/prepare-host-downloads.sh
```

These scripts support release artifacts, endpoint media, and host download metadata.

## Testing Strategy

Beagle OS uses multiple test layers:

- tests/unit: fast regression and helper tests
- tests/integration: cross-component behavior
- tests/bats: shell and installer/runtime checks
- tests/e2e: end-to-end workflows

Start with targeted tests for changed code, then run broader suites as needed.

## Documentation Map

Website operator docs:

- public-site/docs/index.html
- public-site/docs/webui/index.html
- public-site/docs/security/index.html
- public-site/docs/release-notes/index.html

Engineering and operations docs:

- docs/README.md
- docs/STATUS.md
- docs/checklists/
- docs/runbooks/
- docs/refactor/
- docs/lasthope/

## Contribution Principles

- Keep behavior changes reproducible in repo code.
- Add or update tests for bugfixes and important regressions.
- Do not introduce new Proxmox coupling in active paths.
- Prefer small PRs with clear evidence and rollback awareness.
- Update relevant docs when runtime behavior changes.

## Release And Validation Expectations

A stable release should not be treated as complete unless the clean-install and runtime gates are validated from published artifacts:

- Clean host install succeeds
- Host health checks are green
- WebUI VM lifecycle is verified
- First endpoint stream path is verified
- Security and backup baseline checks are recorded

## Links

- Website: https://beagle-os.com
- Docs Hub: https://beagle-os.com/docs/
- WebUI Guide: https://beagle-os.com/docs/webui/
- Releases: https://github.com/meinzeug/beagle-os/releases
- Changelog: https://github.com/meinzeug/beagle-os/blob/main/CHANGELOG.md


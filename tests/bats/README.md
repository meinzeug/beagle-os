# tests/bats/

Bats (Bash Automated Testing System) tests for critical Beagle OS shell scripts.

## Prerequisites

Install bats-core:
```bash
# Ubuntu/Debian
sudo apt-get install bats

# Or from source (recommended for latest):
git clone https://github.com/bats-core/bats-core.git /opt/bats-core
sudo /opt/bats-core/install.sh /usr/local
```

## Running Tests

```bash
# All bats tests
bats tests/bats/

# Single test file
bats tests/bats/post_install_check.bats

# With TAP output
bats --tap tests/bats/
```

## Test Files

| File | Tests |
|------|-------|
| `post_install_check.bats` | `server-installer/post-install-check.sh` — service checks, API health, curl failures |

## Stub Pattern

Tests use `PATH`-prepended stub scripts to avoid requiring real systemd/libvirt/curl. Stubs are created in `BATS_TEST_TMPDIR/bin/` and removed in `teardown()`.

Failure injection via environment variables:
- `STUB_FAILED_SERVICES="libvirtd"` — makes systemctl report that service as inactive
- `STUB_CURL_FAIL=1` — makes curl return exit 6 (connection refused)
- `STUB_PING_FAIL=1` — makes ping fail
- `STUB_VIRSH_FAIL=1` — makes virsh fail with connection error

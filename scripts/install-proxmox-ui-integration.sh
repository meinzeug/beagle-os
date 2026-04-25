#!/usr/bin/env bash
# DEPRECATED: Beagle OS no longer supports Proxmox UI integration.
#
# The proxmox-ui/ directory has been removed as part of the dauerhafte
# Proxmox-Endbeseitigung (see AGENTS.md and docs/goadvanced/11-proxmox-endbeseitigung.md).
#
# Use the standalone Beagle Web Console instead:
#   scripts/install-beagle-host.sh
#
# This stub remains only to preserve the script path for legacy automation
# and to surface a clear migration message instead of silently failing.
set -euo pipefail

cat >&2 <<'MSG'
ERROR: install-proxmox-ui-integration.sh is deprecated and disabled.
       Beagle OS is now standalone-only. Run scripts/install-beagle-host.sh
       to install the Beagle Web Console.
MSG
exit 1

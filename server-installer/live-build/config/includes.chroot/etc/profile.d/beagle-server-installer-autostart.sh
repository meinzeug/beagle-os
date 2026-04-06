#!/bin/sh
set -eu

[ -x /usr/local/bin/beagle-server-installer ] || return 0 2>/dev/null || exit 0
[ -f /run/beagle-server-installer.done ] && return 0 2>/dev/null || exit 0
[ "$(id -u)" -eq 0 ] || return 0 2>/dev/null || exit 0

tty_path="$(tty 2>/dev/null || true)"
[ "$tty_path" = "/dev/tty1" ] || return 0 2>/dev/null || exit 0

[ -n "${BEAGLE_SERVER_INSTALLER_STARTED:-}" ] && return 0 2>/dev/null || exit 0
export BEAGLE_SERVER_INSTALLER_STARTED=1

exec /usr/local/bin/beagle-server-installer

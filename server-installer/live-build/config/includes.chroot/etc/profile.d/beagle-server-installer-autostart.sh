#!/bin/sh
set -eu

[ -x /usr/local/bin/beagle-server-installer ] || return 0 2>/dev/null || exit 0

if [ -f /run/beagle-server-installer.done ]; then
  return 0 2>/dev/null || exit 0
fi

[ "$(id -u)" -eq 0 ] || return 0 2>/dev/null || exit 0

tty_path="$(tty 2>/dev/null || true)"
case "$tty_path" in
  /dev/tty1|/dev/ttyS0) ;;
  *) return 0 2>/dev/null || exit 0 ;;
esac

if [ -n "${BEAGLE_SERVER_INSTALLER_STARTED:-}" ]; then
  return 0 2>/dev/null || exit 0
fi
export BEAGLE_SERVER_INSTALLER_STARTED=1

exec /usr/local/bin/beagle-server-installer

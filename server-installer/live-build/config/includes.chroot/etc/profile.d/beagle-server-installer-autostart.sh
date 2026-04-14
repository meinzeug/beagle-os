#!/bin/sh
set -eu

[ -x /usr/local/bin/beagle-server-installer ] || return 0 2>/dev/null || exit 0

cmdline="$(cat /proc/cmdline 2>/dev/null || true)"

case " $cmdline " in
  *" beagle_server_live=1 "*)
    # Dedicated live-server boot mode: do not auto-launch the installer.
    return 0 2>/dev/null || exit 0
    ;;
esac

case " $cmdline " in
  *" beagle_server_text_mode=1 "*)
    export BEAGLE_SERVER_INSTALLER_FORCE_PLAIN=1
    ;;
esac

if [ -f /run/beagle-server-installer.done ]; then
  return 0 2>/dev/null || exit 0
fi

[ "$(id -u)" -eq 0 ] || return 0 2>/dev/null || exit 0

tty_path="$(tty 2>/dev/null || true)"
case "$tty_path" in
  /dev/tty1) ;;
  *) return 0 2>/dev/null || exit 0 ;;
esac

# Ensure curses can use colour on the Linux virtual console.
export TERM="${TERM:-linux}"

if [ -n "${BEAGLE_SERVER_INSTALLER_STARTED:-}" ]; then
  return 0 2>/dev/null || exit 0
fi
export BEAGLE_SERVER_INSTALLER_STARTED=1

exec /usr/local/bin/beagle-server-installer

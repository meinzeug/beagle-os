if [ "${USER:-}" = "thinclient" ] && [ -z "${DISPLAY:-}" ] && [ "$(tty 2>/dev/null || true)" = "/dev/tty1" ]; then
  BOOT_MODE="$("/usr/local/bin/pve-thin-client-boot-mode" 2>/dev/null || printf 'installer')"
  export PVE_THIN_CLIENT_BOOT_MODE="${BOOT_MODE}"
  exec /usr/local/bin/pve-thin-client-start-x11
fi

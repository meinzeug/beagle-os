#!/usr/bin/env bash

beagle_trace_guard_disable_xtrace_if_sensitive() {
  local shell_flags shell_xtrace ps4_value
  shell_flags="${-:-}"
  shell_xtrace=0
  case "$shell_flags" in
    *x*) shell_xtrace=1 ;;
  esac
  ps4_value="${PS4:-}"

  if [[ "$shell_xtrace" -eq 0 && "$ps4_value" != *'$'* ]]; then
    return 0
  fi

  if [[ -n "${BASH_XTRACEFD:-}" ]]; then
    exec 19>/dev/null || true
    export BASH_XTRACEFD=19
  fi

  if [[ "$shell_xtrace" -eq 1 ]]; then
    set +x
  fi

  export BEAGLE_TRACE_GUARD_ACTIVE=1
  export PS4='+ [beagle-redacted] '
  printf '[beagle-trace-guard] disabled shell xtrace for sensitive script %s\n' "${0##*/}" >&2
}


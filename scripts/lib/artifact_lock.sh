#!/usr/bin/env bash

beagle_artifact_lock_acquire() {
  local label="${1:-artifact-writer}"
  local lock_path="${BEAGLE_ARTIFACT_LOCK_FILE:-}"
  local timeout="${BEAGLE_ARTIFACT_LOCK_TIMEOUT_SECONDS:-7200}"
  local skip_if_busy="${BEAGLE_ARTIFACT_LOCK_SKIP_IF_BUSY:-0}"

  if [[ "${BEAGLE_ARTIFACT_LOCK_HELD:-0}" == "1" ]]; then
    return 0
  fi

  command -v flock >/dev/null 2>&1 || {
    echo "Missing required tool: flock" >&2
    return 1
  }

  if [[ -z "$lock_path" ]]; then
    if install -d -m 0755 /var/lock 2>/dev/null && [[ -w /var/lock ]]; then
      lock_path="/var/lock/beagle-os-artifacts.lock"
    else
      lock_path="${ROOT_DIR:-$(pwd)}/.beagle-artifacts.lock"
    fi
  fi

  install -d -m 0755 "$(dirname "$lock_path")"
  exec 8>"$lock_path"
  if [[ "$skip_if_busy" == "1" ]]; then
    echo "Checking Beagle artifact lock ($label): $lock_path"
    if ! flock -n 8; then
      echo "Beagle artifact lock is already held ($label): $lock_path" >&2
      return 75
    fi
  else
    echo "Waiting for Beagle artifact lock ($label): $lock_path"
    if ! flock -w "$timeout" 8; then
      echo "Timed out waiting for Beagle artifact lock after ${timeout}s: $lock_path" >&2
      return 1
    fi
  fi

  export BEAGLE_ARTIFACT_LOCK_HELD=1
  export BEAGLE_ARTIFACT_LOCK_FILE="$lock_path"
}

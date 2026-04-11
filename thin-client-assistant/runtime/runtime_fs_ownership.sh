#!/usr/bin/env bash

ensure_runtime_owned_dir() {
  local path="${1:-}"
  local mode="${2:-0700}"
  local owner group

  [[ -n "$path" ]] || return 1

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"

  if [[ "$(id -u)" == "0" ]]; then
    if install -d -m "$mode" -o "$owner" -g "$group" "$path" >/dev/null 2>&1 && touch "$path/.beagle-write-test" >/dev/null 2>&1; then
      rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
      return 0
    fi
  fi

  if install -d -m "$mode" "$path" >/dev/null 2>&1 && touch "$path/.beagle-write-test" >/dev/null 2>&1; then
    rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n install -d -m "$mode" -o "$owner" -g "$group" "$path" >/dev/null 2>&1; then
    if touch "$path/.beagle-write-test" >/dev/null 2>&1; then
      rm -f "$path/.beagle-write-test" >/dev/null 2>&1 || true
      return 0
    fi
  fi

  return 1
}

ensure_runtime_owned_file() {
  local path="${1:-}"
  local mode="${2:-0644}"
  local owner group parent

  [[ -n "$path" ]] || return 1

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"
  parent="$(dirname "$path")"

  ensure_runtime_owned_dir "$parent" 0755 || return 1

  if [[ -e "$path" ]]; then
    if [[ "$(id -u)" == "0" ]]; then
      chown "$owner:$group" "$path" >/dev/null 2>&1 || true
      chmod "$mode" "$path" >/dev/null 2>&1 || true
      [[ -w "$path" ]] && return 0
    fi

    if [[ -w "$path" ]]; then
      chmod "$mode" "$path" >/dev/null 2>&1 || true
      return 0
    fi

    if command -v sudo >/dev/null 2>&1 && sudo -n chown "$owner:$group" "$path" >/dev/null 2>&1 && sudo -n chmod "$mode" "$path" >/dev/null 2>&1; then
      [[ -w "$path" ]] && return 0
    fi
  fi

  if touch "$path" >/dev/null 2>&1; then
    chmod "$mode" "$path" >/dev/null 2>&1 || true
    return 0
  fi

  if [[ "$(id -u)" == "0" ]]; then
    install -m "$mode" -o "$owner" -g "$group" /dev/null "$path" >/dev/null 2>&1
    [[ -w "$path" ]] && return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n install -m "$mode" -o "$owner" -g "$group" /dev/null "$path" >/dev/null 2>&1; then
    [[ -w "$path" ]] && return 0
  fi

  return 1
}

ensure_runtime_owned_tree() {
  local path="${1:-}"
  local owner group

  [[ -n "$path" ]] || return 1
  [[ -e "$path" ]] || return 0

  owner="$(runtime_user_name)"
  group="$(runtime_group_name)"

  if [[ "$(id -u)" == "0" ]]; then
    chown -R "$owner:$group" "$path" >/dev/null 2>&1 || return 1
    return 0
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n chown -R "$owner:$group" "$path" >/dev/null 2>&1; then
    return 0
  fi

  return 1
}

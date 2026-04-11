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

prepare_geforcenow_environment() {
  local runtime_home="${1:-/home/$(runtime_user_name)}"
  local storage_root medium home_dir data_dir cache_dir config_dir tmp_dir

  storage_root="${PVE_THIN_CLIENT_GFN_STORAGE_ROOT:-}"
  if [[ -z "$storage_root" ]]; then
    medium="$(live_medium_dir 2>/dev/null || true)"
    if [[ -n "$medium" ]]; then
      storage_root="$medium/pve-thin-client/state/gfn"
    else
      storage_root="$(beagle_state_dir)/gfn"
    fi
  fi

  home_dir="$storage_root/home"
  data_dir="$home_dir/.local/share"
  cache_dir="$home_dir/.cache"
  config_dir="$home_dir/.config"
  tmp_dir="$storage_root/tmp"

  for dir in \
    "$storage_root" \
    "$home_dir" \
    "$home_dir/.local" \
    "$data_dir" \
    "$home_dir/.var/app" \
    "$cache_dir" \
    "$config_dir" \
    "$tmp_dir"
  do
    ensure_runtime_owned_dir "$dir" 0700 || return 1
  done

  ensure_runtime_owned_tree "$storage_root" || true

  export PVE_THIN_CLIENT_GFN_STORAGE_ROOT="$storage_root"
  export PVE_THIN_CLIENT_GFN_RUNTIME_HOME="$runtime_home"
  export HOME="$home_dir"
  export XDG_DATA_HOME="$data_dir"
  export XDG_CACHE_HOME="$cache_dir"
  export XDG_CONFIG_HOME="$config_dir"
  export FLATPAK_USER_DIR="$data_dir/flatpak"
  export FLATPAK_DOWNLOAD_TMPDIR="$tmp_dir"

  ensure_runtime_owned_dir "$FLATPAK_USER_DIR" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CACHE_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$XDG_CONFIG_HOME" 0700 || return 1
  ensure_runtime_owned_dir "$HOME/.var/app" 0700 || return 1

  return 0
}

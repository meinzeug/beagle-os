#!/usr/bin/env bash

beagle_format_gib_ceil() {
  local kib="${1:-0}"
  printf '%s' $(((kib + 1024 * 1024 - 1) / (1024 * 1024)))
}

beagle_path_available_kib() {
  local path="$1"
  mkdir -p "$path"
  df -Pk "$path" | awk 'NR==2 {print $4}'
}

beagle_is_safe_cleanup_path() {
  local root_dir="$1"
  local target="$2"
  local resolved=""
  local suffix=""

  [[ -e "$target" ]] || return 1

  resolved="$(readlink -f "$target" 2>/dev/null || true)"
  [[ -n "$resolved" ]] || return 1

  root_dir="$(readlink -f "$root_dir")"
  if [[ "$resolved" == "$root_dir" ]]; then
    return 1
  fi

  suffix="${resolved#"$root_dir"/}"
  if [[ "$suffix" == "$resolved" ]]; then
    return 1
  fi

  if [[ "$suffix" == ".build" || "$suffix" == .build/* ]]; then
    return 0
  fi

  if [[ "$suffix" == "dist" || "$suffix" == dist/* || "$suffix" == */dist || "$suffix" == */dist/* ]]; then
    return 0
  fi

  return 1
}

beagle_cleanup_reproducible_paths() {
  local root_dir="$1"
  shift
  local path=""
  local size_kib=0
  local cleaned_kib=0

  for path in "$@"; do
    [[ -n "$path" ]] || continue
    [[ -e "$path" ]] || continue

    if ! beagle_is_safe_cleanup_path "$root_dir" "$path"; then
      echo "Skipping unsafe cleanup path: $path" >&2
      continue
    fi

    size_kib="$(du -sk "$path" 2>/dev/null | awk 'NR==1 {print $1}')"
    size_kib="${size_kib:-0}"
    if ! rm -rf "$path" 2>/dev/null; then
      if command -v sudo >/dev/null 2>&1; then
        sudo rm -rf "$path"
      else
        echo "Unable to remove cleanup path without sudo: $path" >&2
        continue
      fi
    fi
    cleaned_kib=$((cleaned_kib + size_kib))
  done

  printf '%s\n' "$cleaned_kib"
}

ensure_free_space_with_cleanup() {
  local label="$1"
  local check_path="$2"
  local need_kib="$3"
  local root_dir="$4"
  shift 4
  local avail_kib=0
  local cleaned_kib=0
  local mount_point=""

  mkdir -p "$check_path"
  avail_kib="$(beagle_path_available_kib "$check_path")"
  avail_kib="${avail_kib:-0}"
  if (( avail_kib >= need_kib )); then
    return 0
  fi

  cleaned_kib="$(beagle_cleanup_reproducible_paths "$root_dir" "$@")"
  cleaned_kib="${cleaned_kib:-0}"
  avail_kib="$(beagle_path_available_kib "$check_path")"
  avail_kib="${avail_kib:-0}"
  if (( avail_kib >= need_kib )); then
    if (( cleaned_kib > 0 )); then
      echo "Recovered $(beagle_format_gib_ceil "$cleaned_kib") GiB for $label by removing reproducible artifacts." >&2
    fi
    return 0
  fi

  mount_point="$(df -Pk "$check_path" | awk 'NR==2 {print $6}')"
  echo "Insufficient free space for $label on $mount_point. Need at least $(beagle_format_gib_ceil "$need_kib") GiB free, have $(beagle_format_gib_ceil "$avail_kib") GiB after cleanup." >&2
  if (( cleaned_kib > 0 )); then
    echo "Removed $(beagle_format_gib_ceil "$cleaned_kib") GiB from reproducible artifact paths before failing." >&2
  fi
  return 1
}

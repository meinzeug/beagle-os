#!/usr/bin/env bash
set -euo pipefail

VMID=""
NICE_VALUE="-10"
APPLY_GOVERNOR="1"
declare -a PROCESS_NAMES=()

usage() {
  cat <<'USAGE'
Usage: apply-beagle-stream-latency-tuning.sh [--vmid <id>] [--process <name>] [--nice <value>] [--no-governor]

Applies conservative low-latency scheduling for BeagleStream hosts, guests, or thinclients:
- sets available CPU frequency governors to performance
- renices matching process main/thread IDs
- if --vmid is set, renices the matching qemu-system process for beagle-<vmid>

Examples:
  sudo scripts/apply-beagle-stream-latency-tuning.sh --vmid 100
  sudo scripts/apply-beagle-stream-latency-tuning.sh --process sunshine
  sudo scripts/apply-beagle-stream-latency-tuning.sh --process beagle-stream
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vmid)
      VMID="${2:-}"
      shift 2
      ;;
    --process)
      PROCESS_NAMES+=("${2:-}")
      shift 2
      ;;
    --nice)
      NICE_VALUE="${2:-}"
      shift 2
      ;;
    --no-governor)
      APPLY_GOVERNOR="0"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "$VMID" && ! "$VMID" =~ ^[0-9]+$ ]]; then
  echo "Invalid --vmid: $VMID" >&2
  exit 2
fi
if [[ ! "$NICE_VALUE" =~ ^-?[0-9]+$ || "$NICE_VALUE" -lt -20 || "$NICE_VALUE" -gt 19 ]]; then
  echo "Invalid --nice: $NICE_VALUE" >&2
  exit 2
fi

run_privileged() {
  if [[ "$(id -u)" == "0" ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

set_performance_governor() {
  local governor
  shopt -s nullglob
  for governor in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    [[ -w "$governor" || "$(id -u)" != "0" ]] || continue
    printf 'performance\n' | run_privileged tee "$governor" >/dev/null 2>&1 || true
  done
  shopt -u nullglob
}

renice_pid_and_threads() {
  local pid="$1"
  local tid
  [[ -n "$pid" && -d "/proc/$pid" ]] || return 0
  run_privileged renice -n "$NICE_VALUE" -p "$pid" >/dev/null 2>&1 || true
  while read -r tid; do
    [[ -n "$tid" ]] || continue
    run_privileged renice -n "$NICE_VALUE" -p "$tid" >/dev/null 2>&1 || true
  done < <(ps -L -p "$pid" -o tid= 2>/dev/null || true)
}

renice_named_process() {
  local name="$1"
  local pid
  while read -r pid; do
    renice_pid_and_threads "$pid"
  done < <(pgrep -x "$name" 2>/dev/null || true)
}

renice_qemu_vm() {
  local vmid="$1"
  local pid
  pid="$(ps -eo pid,args | awk -v guest="guest=beagle-${vmid}" '/[q]emu-system/ && index($0, guest) {print $1; exit}')"
  [[ -n "$pid" ]] || return 0
  renice_pid_and_threads "$pid"
}

if [[ "$APPLY_GOVERNOR" == "1" ]]; then
  set_performance_governor
fi

if [[ -n "$VMID" ]]; then
  renice_qemu_vm "$VMID"
fi

for process_name in "${PROCESS_NAMES[@]}"; do
  [[ -n "$process_name" ]] || continue
  renice_named_process "$process_name"
done

echo "beagle_stream_latency_tuning_applied=1 nice=${NICE_VALUE} vmid=${VMID:-none} processes=${PROCESS_NAMES[*]:-none} governor=${APPLY_GOVERNOR}"

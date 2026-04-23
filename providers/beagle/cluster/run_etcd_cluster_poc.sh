#!/usr/bin/env bash
set -euo pipefail

# Non-production helper that bootstraps a local three-member etcd ring
# (host-a, host-b, witness) and runs the leader-election PoC.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
POC_PY="${ROOT_DIR}/providers/beagle/cluster/store_poc.py"
TMP_DIR="${TMPDIR:-/tmp}/beagle-etcd-poc"

ETCD_BIN="${ETCD_BIN:-$(command -v etcd || true)}"
ETCDCTL_BIN="${ETCDCTL_BIN:-$(command -v etcdctl || true)}"

if [[ -z "${ETCD_BIN}" || -z "${ETCDCTL_BIN}" ]]; then
  echo "etcd/etcdctl not found. Install packages first (e.g. apt-get install etcd-server etcd-client)." >&2
  exit 1
fi

mkdir -p "${TMP_DIR}"/{a,b,w}

cleanup() {
  local pids=("${PID_A:-}" "${PID_B:-}" "${PID_W:-}")
  for pid in "${pids[@]}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT

COMMON_CLUSTER="host-a=http://127.0.0.1:23801,host-b=http://127.0.0.1:23802,witness=http://127.0.0.1:23803"

"${ETCD_BIN}" \
  --name host-a \
  --data-dir "${TMP_DIR}/a" \
  --listen-client-urls "http://127.0.0.1:23791" \
  --advertise-client-urls "http://127.0.0.1:23791" \
  --listen-peer-urls "http://127.0.0.1:23801" \
  --initial-advertise-peer-urls "http://127.0.0.1:23801" \
  --initial-cluster "${COMMON_CLUSTER}" \
  --initial-cluster-state new >"${TMP_DIR}/etcd-a.log" 2>&1 &
PID_A=$!

"${ETCD_BIN}" \
  --name host-b \
  --data-dir "${TMP_DIR}/b" \
  --listen-client-urls "http://127.0.0.1:23792" \
  --advertise-client-urls "http://127.0.0.1:23792" \
  --listen-peer-urls "http://127.0.0.1:23802" \
  --initial-advertise-peer-urls "http://127.0.0.1:23802" \
  --initial-cluster "${COMMON_CLUSTER}" \
  --initial-cluster-state new >"${TMP_DIR}/etcd-b.log" 2>&1 &
PID_B=$!

"${ETCD_BIN}" \
  --name witness \
  --data-dir "${TMP_DIR}/w" \
  --listen-client-urls "http://127.0.0.1:23793" \
  --advertise-client-urls "http://127.0.0.1:23793" \
  --listen-peer-urls "http://127.0.0.1:23803" \
  --initial-advertise-peer-urls "http://127.0.0.1:23803" \
  --initial-cluster "${COMMON_CLUSTER}" \
  --initial-cluster-state new >"${TMP_DIR}/etcd-w.log" 2>&1 &
PID_W=$!

export ETCDCTL_API=3
ENDPOINTS="http://127.0.0.1:23791,http://127.0.0.1:23792,http://127.0.0.1:23793"

for _ in {1..25}; do
  if "${ETCDCTL_BIN}" --endpoints "${ENDPOINTS}" endpoint health >/dev/null 2>&1; then
    break
  fi
  sleep 1

done

"${ETCDCTL_BIN}" --endpoints "${ENDPOINTS}" endpoint health
python3 "${POC_PY}" etcd --endpoints "${ENDPOINTS}" --timeout 25
python3 "${POC_PY}" sqlite-eval

echo "ETCD_POC_RESULT=PASS"

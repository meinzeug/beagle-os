#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-/tmp/beagle-json-stress}"
STATE_FILE="${TARGET_DIR}/testfile.json"
WORKERS="${WORKERS:-25}"
ITERATIONS="${ITERATIONS:-40}"

mkdir -p "${TARGET_DIR}"
rm -f "${STATE_FILE}"

python3 - <<'PY' "${STATE_FILE}" "${WORKERS}" "${ITERATIONS}"
import json
import sys
import threading
from pathlib import Path

from core.persistence.json_state_store import JsonStateStore

state_file = Path(sys.argv[1])
workers = int(sys.argv[2])
iterations = int(sys.argv[3])
expected = workers * iterations

store = JsonStateStore(state_file, default_factory=lambda: {"counter": 0})
store.save({"counter": 0})

def _worker() -> None:
    for _ in range(iterations):
        def mutator(doc):
            doc["counter"] = int(doc.get("counter", 0)) + 1
            return doc

        store.update(mutator)

threads = [threading.Thread(target=_worker) for _ in range(workers)]
for t in threads:
    t.start()
for t in threads:
    t.join()

payload = store.load()
counter = int(payload.get("counter", -1)) if isinstance(payload, dict) else -1

raw = state_file.read_text(encoding="utf-8")
json.loads(raw)

if counter != expected:
    print(f"FAIL counter={counter} expected={expected}")
    raise SystemExit(1)

print(f"OK counter={counter} expected={expected}")
PY

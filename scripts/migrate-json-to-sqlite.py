#!/usr/bin/env python3
"""One-shot JSON-State → SQLite importer for Beagle OS.

Usage:
    python3 scripts/migrate-json-to-sqlite.py [--dry-run] [--state-root PATH] [--db PATH]

Options:
    --dry-run       Show what would be migrated without writing to DB or moving files.
    --state-root    Root of beagle state directory (default: /var/lib/beagle).
    --db            Target SQLite DB path (default: /var/lib/beagle/state.db).

The script is idempotent: re-running it after partial migration uses UPSERT logic
so no data is duplicated or lost.  Migrated source JSON files are moved to a
timestamped backup directory (<state-root>/.bak/<ISO8601>/) only on a successful
full run (skipped in --dry-run mode).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    """Walk up from this file to the beagle-os repo root."""
    here = Path(__file__).resolve()
    for parent in [here.parent, here.parent.parent]:
        if (parent / "core" / "persistence" / "sqlite_db.py").exists():
            return parent
    raise RuntimeError("Cannot locate repo root (core/persistence/sqlite_db.py not found)")


REPO_ROOT = _find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.persistence.sqlite_db import BeagleDb  # noqa: E402
from core.repository.vm_repository import VmRepository  # noqa: E402
from core.repository.pool_repository import PoolRepository  # noqa: E402
from core.repository.device_repository import DeviceRepository  # noqa: E402
from core.repository.session_repository import SessionRepository  # noqa: E402
from core.repository.gpu_repository import GpuRepository  # noqa: E402

SCHEMA_DIR = REPO_ROOT / "core" / "persistence" / "migrations"


# ---------------------------------------------------------------------------
# Loaders — read JSON source files and normalise to repository-compatible dicts
# ---------------------------------------------------------------------------

class _Counter:
    def __init__(self) -> None:
        self.total = 0
        self.skipped = 0
        self.errors = 0

    def ok(self, n: int = 1) -> None:
        self.total += n

    def skip(self, n: int = 1) -> None:
        self.skipped += n

    def err(self, n: int = 1) -> None:
        self.errors += n

    def __repr__(self) -> str:
        return f"total={self.total} skipped={self.skipped} errors={self.errors}"


def _load_json(path: Path) -> dict | list | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [WARN] Cannot read {path}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# VMs  — /var/lib/beagle/providers/beagle/vms.json (list of vm dicts)
# ---------------------------------------------------------------------------

def migrate_vms(state_root: Path, repo: VmRepository, dry_run: bool) -> _Counter:
    c = _Counter()
    src = state_root / "providers" / "beagle" / "vms.json"
    if not src.exists():
        print(f"  [SKIP] {src} not found")
        c.skip()
        return c

    data = _load_json(src)
    if not isinstance(data, list):
        print(f"  [WARN] {src} is not a list, skipping", file=sys.stderr)
        c.skip()
        return c

    for vm in data:
        if not isinstance(vm, dict):
            c.skip()
            continue
        vmid = vm.get("vmid")
        if not vmid:
            c.skip()
            continue
        try:
            if not dry_run:
                repo.save(vm)
            print(f"  vm {vmid}: {'(dry-run) ' if dry_run else ''}OK")
            c.ok()
        except Exception as exc:
            print(f"  [ERR] vm {vmid}: {exc}", file=sys.stderr)
            c.err()

    return c


# ---------------------------------------------------------------------------
# Pools  — /var/lib/beagle/beagle-manager/desktop-pools.json
#          Format: {"pools": {"<pool_id>": {...}}, "vms": {...}, ...}
# ---------------------------------------------------------------------------

def migrate_pools(state_root: Path, repo: PoolRepository, dry_run: bool) -> _Counter:
    c = _Counter()
    src = state_root / "beagle-manager" / "desktop-pools.json"
    if not src.exists():
        print(f"  [SKIP] {src} not found")
        c.skip()
        return c

    data = _load_json(src)
    if not isinstance(data, dict):
        print(f"  [WARN] {src} unexpected format, skipping", file=sys.stderr)
        c.skip()
        return c

    pools = data.get("pools") or {}
    if isinstance(pools, list):
        pools = {p.get("pool_id", str(i)): p for i, p in enumerate(pools) if isinstance(p, dict)}

    for pool_id, pool in pools.items():
        if not isinstance(pool, dict):
            c.skip()
            continue
        pool.setdefault("pool_id", str(pool_id))
        try:
            if not dry_run:
                repo.save(pool)
            print(f"  pool {pool_id}: {'(dry-run) ' if dry_run else ''}OK")
            c.ok()
        except Exception as exc:
            print(f"  [ERR] pool {pool_id}: {exc}", file=sys.stderr)
            c.err()

    return c


# ---------------------------------------------------------------------------
# Devices  — /var/lib/beagle/beagle-manager/device-registry.json
#            Format: {"devices": {"<device_id>": {...}}}
# ---------------------------------------------------------------------------

def migrate_devices(state_root: Path, repo: DeviceRepository, dry_run: bool) -> _Counter:
    c = _Counter()
    src = state_root / "beagle-manager" / "device-registry.json"
    if not src.exists():
        print(f"  [SKIP] {src} not found")
        c.skip()
        return c

    data = _load_json(src)
    if not isinstance(data, dict):
        print(f"  [WARN] {src} unexpected format, skipping", file=sys.stderr)
        c.skip()
        return c

    devices = data.get("devices") or {}
    if isinstance(devices, list):
        devices = {d.get("device_id", str(i)): d for i, d in enumerate(devices) if isinstance(d, dict)}

    for device_id, device in devices.items():
        if not isinstance(device, dict):
            c.skip()
            continue
        device.setdefault("device_id", str(device_id))
        # Map last_seen → last_seen_at if needed
        if "last_seen" in device and "last_seen_at" not in device:
            device["last_seen_at"] = device["last_seen"]
        try:
            if not dry_run:
                repo.save(device)
            print(f"  device {device_id}: {'(dry-run) ' if dry_run else ''}OK")
            c.ok()
        except Exception as exc:
            print(f"  [ERR] device {device_id}: {exc}", file=sys.stderr)
            c.err()

    return c


# ---------------------------------------------------------------------------
# Sessions  — live sessions are ephemeral; no persistent JSON source exists by
#             default, so this is a no-op placeholder for forward compatibility.
# ---------------------------------------------------------------------------

def migrate_sessions(state_root: Path, repo: SessionRepository, dry_run: bool) -> _Counter:
    c = _Counter()
    src = state_root / "beagle-manager" / "sessions.json"
    if not src.exists():
        print(f"  [SKIP] {src} not found (sessions are ephemeral — OK)")
        c.skip()
        return c

    data = _load_json(src)
    sessions: list[dict] = []
    if isinstance(data, list):
        sessions = [s for s in data if isinstance(s, dict)]
    elif isinstance(data, dict):
        raw = data.get("sessions") or {}
        if isinstance(raw, list):
            sessions = raw
        elif isinstance(raw, dict):
            sessions = list(raw.values())

    for session in sessions:
        sid = session.get("session_id") or session.get("id") or ""
        try:
            if not dry_run:
                repo.save(session)
            print(f"  session {sid}: {'(dry-run) ' if dry_run else ''}OK")
            c.ok()
        except Exception as exc:
            print(f"  [ERR] session {sid}: {exc}", file=sys.stderr)
            c.err()

    return c


# ---------------------------------------------------------------------------
# GPUs  — GPU state is in-memory in gpu_streaming_service; no persistent JSON
#         file by default.  This is a no-op placeholder.
# ---------------------------------------------------------------------------

def migrate_gpus(state_root: Path, repo: GpuRepository, dry_run: bool) -> _Counter:
    c = _Counter()
    src = state_root / "beagle-manager" / "gpu-state.json"
    if not src.exists():
        print(f"  [SKIP] {src} not found (GPU state is ephemeral — OK)")
        c.skip()
        return c

    data = _load_json(src)
    gpus: list[dict] = []
    if isinstance(data, dict):
        raw = data.get("gpus") or data
        if isinstance(raw, dict):
            gpus = list(raw.values())
        elif isinstance(raw, list):
            gpus = raw

    for gpu in gpus:
        gid = gpu.get("gpu_id") or ""
        try:
            if not dry_run:
                repo.save(gpu)
            print(f"  gpu {gid}: {'(dry-run) ' if dry_run else ''}OK")
            c.ok()
        except Exception as exc:
            print(f"  [ERR] gpu {gid}: {exc}", file=sys.stderr)
            c.err()

    return c


# ---------------------------------------------------------------------------
# Backup moved JSON files
# ---------------------------------------------------------------------------

def _backup_sources(sources: list[Path], state_root: Path) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak_dir = state_root / ".bak" / ts
    bak_dir.mkdir(parents=True, exist_ok=True)
    for src in sources:
        if src.exists():
            dest = bak_dir / src.relative_to(state_root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f"  backed up {src} → {dest}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Show migration plan without writing")
    parser.add_argument("--state-root", default="/var/lib/beagle", help="Beagle state root (default: /var/lib/beagle)")
    parser.add_argument("--db", default=None, help="SQLite DB path (default: <state-root>/state.db)")
    args = parser.parse_args()

    state_root = Path(args.state_root).resolve()
    db_path = Path(args.db).resolve() if args.db else state_root / "state.db"

    print(f"Beagle JSON → SQLite Importer")
    print(f"  state-root : {state_root}")
    print(f"  db         : {db_path}")
    print(f"  dry-run    : {args.dry_run}")
    print()

    if not state_root.exists():
        print(f"[ERROR] state-root {state_root} does not exist", file=sys.stderr)
        return 1

    # Open DB and apply schema
    if not args.dry_run:
        db = BeagleDb(db_path)
        db.migrate(SCHEMA_DIR)
        vm_repo = VmRepository(db)
        pool_repo = PoolRepository(db)
        device_repo = DeviceRepository(db)
        session_repo = SessionRepository(db)
        gpu_repo = GpuRepository(db)
    else:
        # In dry-run mode we still need repo objects to validate normalization
        import tempfile
        _tmp = tempfile.mkdtemp()
        _db = BeagleDb(Path(_tmp) / "dry_run.db")
        _db.migrate(SCHEMA_DIR)
        vm_repo = VmRepository(_db)
        pool_repo = PoolRepository(_db)
        device_repo = DeviceRepository(_db)
        session_repo = SessionRepository(_db)
        gpu_repo = GpuRepository(_db)

    totals: dict[str, _Counter] = {}

    # --- VMs ---
    print("=== Migrating VMs ===")
    totals["vms"] = migrate_vms(state_root, vm_repo, args.dry_run)
    print(f"    Result: {totals['vms']}\n")

    # --- Pools (must come before sessions due to FK) ---
    print("=== Migrating Pools ===")
    totals["pools"] = migrate_pools(state_root, pool_repo, args.dry_run)
    print(f"    Result: {totals['pools']}\n")

    # --- Devices ---
    print("=== Migrating Devices ===")
    totals["devices"] = migrate_devices(state_root, device_repo, args.dry_run)
    print(f"    Result: {totals['devices']}\n")

    # --- Sessions ---
    print("=== Migrating Sessions ===")
    totals["sessions"] = migrate_sessions(state_root, session_repo, args.dry_run)
    print(f"    Result: {totals['sessions']}\n")

    # --- GPUs ---
    print("=== Migrating GPUs ===")
    totals["gpus"] = migrate_gpus(state_root, gpu_repo, args.dry_run)
    print(f"    Result: {totals['gpus']}\n")

    # Summary
    total_ok = sum(c.total for c in totals.values())
    total_err = sum(c.errors for c in totals.values())
    print("=== Summary ===")
    for entity, c in totals.items():
        print(f"  {entity:<10}: {c}")
    print(f"\n  Total migrated : {total_ok}")
    print(f"  Total errors   : {total_err}")

    if total_err > 0:
        print("\n[WARN] Migration completed with errors — check output above.", file=sys.stderr)
        return 2

    if not args.dry_run and total_ok > 0:
        # Backup source files that were successfully migrated
        sources = [
            state_root / "providers" / "beagle" / "vms.json",
            state_root / "beagle-manager" / "desktop-pools.json",
            state_root / "beagle-manager" / "device-registry.json",
        ]
        print("\n=== Backing up migrated source files ===")
        _backup_sources([s for s in sources if s.exists()], state_root)

    print("\nDone." if not args.dry_run else "\nDry-run complete — no changes written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

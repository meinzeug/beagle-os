from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


class BackupService:
    def __init__(
        self,
        *,
        state_file: Path,
        utcnow: Callable[[], str],
    ) -> None:
        self._state_file = Path(state_file)
        self._utcnow = utcnow

    def _default_policy(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "schedule": "daily",
            "retention_days": 7,
            "target_path": "/var/backups/beagle",
            "last_backup": "",
        }

    def _load(self) -> dict[str, Any]:
        if not self._state_file.exists():
            return {
                "pool_policies": {},
                "vm_policies": {},
                "jobs": [],
            }
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        if not isinstance(raw.get("pool_policies"), dict):
            raw["pool_policies"] = {}
        if not isinstance(raw.get("vm_policies"), dict):
            raw["vm_policies"] = {}
        if not isinstance(raw.get("jobs"), list):
            raw["jobs"] = []
        return raw

    def _save(self, state: dict[str, Any]) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")

    @staticmethod
    def _normalize_schedule(value: Any) -> str:
        schedule = str(value or "daily").strip().lower()
        if schedule not in {"hourly", "daily", "weekly"}:
            return "daily"
        return schedule

    @staticmethod
    def _normalize_retention_days(value: Any) -> int:
        try:
            days = int(value)
        except Exception:
            days = 7
        return max(1, min(days, 3650))

    @staticmethod
    def _normalize_target_path(value: Any) -> str:
        text = str(value or "").strip() or "/var/backups/beagle"
        if not text.startswith("/"):
            return "/var/backups/beagle"
        if ".." in text:
            return "/var/backups/beagle"
        return text[:512]

    def _sanitize_policy(self, payload: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
        source = payload if isinstance(payload, dict) else {}
        policy = dict(current)
        if "enabled" in source:
            policy["enabled"] = bool(source.get("enabled"))
        if "schedule" in source:
            policy["schedule"] = self._normalize_schedule(source.get("schedule"))
        if "retention_days" in source:
            policy["retention_days"] = self._normalize_retention_days(source.get("retention_days"))
        if "target_path" in source:
            policy["target_path"] = self._normalize_target_path(source.get("target_path"))
        if "last_backup" in current:
            policy["last_backup"] = str(current.get("last_backup") or "")
        return policy

    def get_pool_policy(self, pool_id: str) -> dict[str, Any]:
        state = self._load()
        key = str(pool_id or "").strip()
        if not key:
            raise ValueError("pool_id is required")
        policy = state["pool_policies"].get(key)
        if not isinstance(policy, dict):
            policy = self._default_policy()
        return {"pool_id": key, **self._sanitize_policy(policy, self._default_policy())}

    def update_pool_policy(self, pool_id: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        state = self._load()
        key = str(pool_id or "").strip()
        if not key:
            raise ValueError("pool_id is required")
        current = state["pool_policies"].get(key)
        if not isinstance(current, dict):
            current = self._default_policy()
        state["pool_policies"][key] = self._sanitize_policy(payload, current)
        self._save(state)
        return self.get_pool_policy(key)

    def get_vm_policy(self, vmid: int) -> dict[str, Any]:
        state = self._load()
        key = str(int(vmid))
        policy = state["vm_policies"].get(key)
        if not isinstance(policy, dict):
            policy = self._default_policy()
        return {"vmid": int(vmid), **self._sanitize_policy(policy, self._default_policy())}

    def update_vm_policy(self, vmid: int, payload: dict[str, Any] | None) -> dict[str, Any]:
        state = self._load()
        key = str(int(vmid))
        current = state["vm_policies"].get(key)
        if not isinstance(current, dict):
            current = self._default_policy()
        state["vm_policies"][key] = self._sanitize_policy(payload, current)
        self._save(state)
        return self.get_vm_policy(int(vmid))

    def list_jobs(self, *, scope_type: str = "", scope_id: str = "") -> list[dict[str, Any]]:
        state = self._load()
        jobs: list[dict[str, Any]] = []
        for item in state.get("jobs", []):
            if not isinstance(item, dict):
                continue
            if scope_type and str(item.get("scope_type") or "") != scope_type:
                continue
            if scope_id and str(item.get("scope_id") or "") != scope_id:
                continue
            jobs.append(dict(item))
        jobs.sort(key=lambda value: str(value.get("created_at") or ""), reverse=True)
        return jobs[:100]

    @staticmethod
    def _schedule_due(last_backup: str, schedule: str, now_iso: str) -> bool:
        if not last_backup:
            return True
        if schedule == "hourly":
            return now_iso[:13] != last_backup[:13]
        if schedule == "weekly":
            return now_iso[:10] != last_backup[:10] and now_iso[:10] > last_backup[:10]
        return now_iso[:10] != last_backup[:10]

    def _run_backup_archive(self, *, scope_type: str, scope_id: str, target_path: str) -> str:
        Path(target_path).mkdir(parents=True, exist_ok=True)
        now_iso = self._utcnow()
        safe_ts = now_iso.replace(":", "-").replace(" ", "_")
        archive = str(Path(target_path) / f"beagle-backup-{scope_type}-{scope_id}-{safe_ts}.tar.gz")
        result = subprocess.run(
            ["tar", "--ignore-failed-read", "-czf", archive, "/etc/beagle"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise RuntimeError(str(result.stderr or "tar failed").strip()[:500])
        return archive

    def run_backup_now(self, *, scope_type: str, scope_id: str) -> dict[str, Any]:
        kind = str(scope_type or "").strip().lower()
        identifier = str(scope_id or "").strip()
        if kind not in {"pool", "vm"}:
            raise ValueError("scope_type must be pool or vm")
        if not identifier:
            raise ValueError("scope_id is required")

        state = self._load()
        policy_map = state["pool_policies"] if kind == "pool" else state["vm_policies"]
        current = policy_map.get(identifier)
        if not isinstance(current, dict):
            current = self._default_policy()
            policy_map[identifier] = current

        job = {
            "job_id": str(uuid4()),
            "scope_type": kind,
            "scope_id": identifier,
            "status": "running",
            "created_at": self._utcnow(),
            "started_at": self._utcnow(),
        }
        state["jobs"].append(job)
        self._save(state)

        try:
            archive = self._run_backup_archive(scope_type=kind, scope_id=identifier, target_path=self._normalize_target_path(current.get("target_path")))
            job["status"] = "success"
            job["archive"] = archive
            policy_map[identifier]["last_backup"] = self._utcnow()
            current["last_backup"] = policy_map[identifier]["last_backup"]
        except Exception as exc:
            job["status"] = "error"
            job["error"] = str(exc)
        finally:
            job["finished_at"] = self._utcnow()
            self._save(state)

        return {
            "ok": job.get("status") == "success",
            "job": job,
            "policy": self._sanitize_policy(current, self._default_policy()),
        }

    def run_scheduled_backups(self) -> list[dict[str, Any]]:
        state = self._load()
        now_iso = self._utcnow()
        triggered: list[dict[str, Any]] = []

        for kind, policy_map in (("pool", state.get("pool_policies", {})), ("vm", state.get("vm_policies", {}))):
            if not isinstance(policy_map, dict):
                continue
            for scope_id, policy in list(policy_map.items()):
                if not isinstance(policy, dict):
                    continue
                if not bool(policy.get("enabled", False)):
                    continue
                schedule = self._normalize_schedule(policy.get("schedule"))
                last_backup = str(policy.get("last_backup") or "")
                if not self._schedule_due(last_backup, schedule, now_iso):
                    continue
                result = self.run_backup_now(scope_type=kind, scope_id=str(scope_id))
                triggered.append(result.get("job", {}))
        return triggered

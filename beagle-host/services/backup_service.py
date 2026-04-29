"""BeagleOS Backup Service — policies, scheduling, BackupTarget integration,
restore, single-file-restore, and cross-site replication.

Plan 16 coverage:
  Schritt 2 — Backup-Service with scheduling (original implementation)
  Schritt 3 — BackupTarget protocol integration (local / NFS / S3)
  Schritt 4 — Live-Restore (restore_snapshot)
  Schritt 5 — Single-File-Restore (list_snapshot_files / read_snapshot_file)
  Schritt 6 — Cross-Site-Replication (replicate_to_remote)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from core.persistence.json_state_store import JsonStateStore


class BackupService:
    def __init__(
        self,
        *,
        state_file: Path,
        utcnow: Callable[[], str],
    ) -> None:
        self._state_file = Path(state_file)
        self._utcnow = utcnow
        self._store = JsonStateStore(
            self._state_file,
            default_factory=lambda: {"pool_policies": {}, "vm_policies": {}, "jobs": [], "replication": {}},
        )

    def _default_policy(self) -> dict[str, Any]:
        return {
            "enabled": False,
            "schedule": "daily",
            "retention_days": 7,
            # target_type: "local" | "nfs" | "s3"
            "target_type": "local",
            "target_path": "/var/backups/beagle",
            # incremental: use tar --listed-incremental for level-1 backups after first full
            "incremental": False,
            # NFS
            "nfs_mount_point": "",
            # S3
            "s3_bucket": "",
            "s3_prefix": "beagle-backup/",
            "s3_endpoint_url": "",
            "s3_access_key": "",
            "s3_secret_key": "",
            "s3_encryption_key": "",
            # meta
            "last_backup": "",
        }

    def _load(self) -> dict[str, Any]:
        raw = self._store.load()
        if not isinstance(raw, dict):
            raw = {}
        if not isinstance(raw.get("pool_policies"), dict):
            raw["pool_policies"] = {}
        if not isinstance(raw.get("vm_policies"), dict):
            raw["vm_policies"] = {}
        if not isinstance(raw.get("jobs"), list):
            raw["jobs"] = []
        if not isinstance(raw.get("replication"), dict):
            raw["replication"] = {}
        return raw

    def _save(self, state: dict[str, Any]) -> None:
        self._store.save(state)

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

    @staticmethod
    def _normalize_target_type(value: Any) -> str:
        t = str(value or "local").strip().lower()
        return t if t in {"local", "nfs", "s3"} else "local"

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
        if "target_type" in source:
            policy["target_type"] = self._normalize_target_type(source.get("target_type"))
        # NFS
        if "nfs_mount_point" in source:
            mp = str(source.get("nfs_mount_point") or "").strip()
            policy["nfs_mount_point"] = mp[:512] if mp.startswith("/") else ""
        # S3 — store as-is (validated server-side when target is used)
        for s3_field in ("s3_bucket", "s3_prefix", "s3_endpoint_url", "s3_access_key", "s3_secret_key", "s3_encryption_key"):
            if s3_field in source:
                policy[s3_field] = str(source.get(s3_field) or "").strip()[:1024]
        if "incremental" in source:
            policy["incremental"] = bool(source.get("incremental"))
        # Preserve last_backup from source first (for GET reads), fall back to
        # current (for UPDATE where user payload does not include last_backup).
        policy["last_backup"] = str(
            source.get("last_backup") or current.get("last_backup") or ""
        )
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

    def _find_job(self, job_id: str) -> dict[str, Any] | None:
        state = self._load()
        for job in state.get("jobs", []):
            if isinstance(job, dict) and str(job.get("job_id") or "") == str(job_id):
                return dict(job)
        return None

    def _find_policy_for_job(self, job: dict[str, Any]) -> dict[str, Any]:
        scope_type = str(job.get("scope_type") or "").lower()
        scope_id = str(job.get("scope_id") or "")
        if scope_type == "pool":
            return self.get_pool_policy(scope_id)
        vmid = int(scope_id) if scope_id.isdigit() else 0
        return self.get_vm_policy(vmid)

    # ------------------------------------------------------------------
    # BackupTarget integration (Schritt 3)
    # ------------------------------------------------------------------

    def _get_target(self, policy: dict[str, Any]) -> Any:
        """Resolve a BackupTarget from policy fields."""
        from core.backup_target import make_target  # noqa: PLC0415

        target_type = self._normalize_target_type(policy.get("target_type"))
        if target_type == "nfs":
            return make_target({"type": "nfs", "mount_point": str(policy.get("nfs_mount_point") or "/mnt/beagle-backup")})
        if target_type == "s3":
            return make_target(
                {
                    "type": "s3",
                    "bucket": str(policy.get("s3_bucket") or ""),
                    "prefix": str(policy.get("s3_prefix") or "beagle-backup/"),
                    "endpoint_url": policy.get("s3_endpoint_url") or None,
                    "access_key": policy.get("s3_access_key") or None,
                    "secret_key": policy.get("s3_secret_key") or None,
                    "encryption_key": policy.get("s3_encryption_key") or None,
                }
            )
        return make_target({"type": "local", "path": self._normalize_target_path(policy.get("target_path"))})

    def list_snapshots(self, *, scope_type: str = "", scope_id: str = "") -> list[dict[str, Any]]:
        """List snapshots from BackupTargets of all matching policies."""
        state = self._load()
        results: list[dict[str, Any]] = []
        for kind, policy_key in (("pool", "pool_policies"), ("vm", "vm_policies")):
            if scope_type and scope_type != kind:
                continue
            for sid, policy in (state.get(policy_key) or {}).items():
                if scope_id and sid != scope_id:
                    continue
                if not isinstance(policy, dict):
                    continue
                prefix = f"beagle-backup-{kind}-{sid}-"
                try:
                    snaps = self._get_target(policy).list_snapshots(prefix=prefix)
                    for s in snaps:
                        s["scope_type"] = kind
                        s["scope_id"] = sid
                    results.extend(snaps)
                except Exception as exc:  # noqa: BLE001
                    results.append({"scope_type": kind, "scope_id": sid, "error": str(exc)})
        return results

    @staticmethod
    def _schedule_due(last_backup: str, schedule: str, now_iso: str) -> bool:
        if not last_backup:
            return True
        if schedule == "hourly":
            return now_iso[:13] != last_backup[:13]
        if schedule == "weekly":
            return now_iso[:10] != last_backup[:10] and now_iso[:10] > last_backup[:10]
        return now_iso[:10] != last_backup[:10]

    def _run_backup_archive(
        self,
        *,
        scope_type: str,
        scope_id: str,
        target_path: str,
        incremental: bool = False,
    ) -> str:
        Path(target_path).mkdir(parents=True, exist_ok=True)
        now_iso = self._utcnow()
        safe_ts = now_iso.replace(":", "-").replace(" ", "_")

        cmd: list[str] = ["tar", "--ignore-failed-read"]
        if incremental:
            snar_path = str(Path(target_path) / f"beagle-backup-{scope_type}-{scope_id}.snar")
            cmd += [f"--listed-incremental={snar_path}"]
            # Determine label: full (no prior .snar) or incremental
            label = "full" if not Path(snar_path).exists() else "incr"
            archive = str(Path(target_path) / f"beagle-backup-{scope_type}-{scope_id}-{safe_ts}-{label}.tar.gz")
        else:
            archive = str(Path(target_path) / f"beagle-backup-{scope_type}-{scope_id}-{safe_ts}.tar.gz")

        cmd += ["-czf", archive, "/etc/beagle"]
        result = subprocess.run(
            cmd,
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

        job: dict[str, Any] = {
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
            target_type = self._normalize_target_type(current.get("target_type"))
            use_incremental = bool(current.get("incremental", False)) and target_type == "local"
            if target_type == "s3":
                # Create archive in tmpdir, upload to S3, then clean up local copy
                with tempfile.TemporaryDirectory() as tmpdir:
                    local_archive = self._run_backup_archive(scope_type=kind, scope_id=identifier, target_path=tmpdir)
                    chunk_id = Path(local_archive).name
                    self._get_target(current).write_chunk(chunk_id, Path(local_archive).read_bytes())
                archive_ref = chunk_id
            elif target_type == "nfs":
                write_path = self._normalize_target_path(current.get("nfs_mount_point") or current.get("target_path"))
                archive_ref = self._run_backup_archive(scope_type=kind, scope_id=identifier, target_path=write_path)
            else:
                archive_ref = self._run_backup_archive(
                    scope_type=kind,
                    scope_id=identifier,
                    target_path=self._normalize_target_path(current.get("target_path")),
                    incremental=use_incremental,
                )

            job["status"] = "success"
            job["archive"] = archive_ref
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

    # ------------------------------------------------------------------
    # Archive resolution helper
    # ------------------------------------------------------------------

    def _resolve_archive_local(self, job: dict[str, Any], policy: dict[str, Any]) -> tuple[str, bool]:
        """Return (local_path, is_temp) for the archive referenced in job.

        For S3 targets the archive is downloaded to a temp dir (is_temp=True).
        Caller must delete the temp directory when is_temp is True.
        """
        archive = str(job.get("archive") or "")
        if not archive:
            raise ValueError("Job has no archive reference")

        target_type = self._normalize_target_type(policy.get("target_type"))
        if target_type == "s3":
            tmpdir = tempfile.mkdtemp(prefix="beagle-restore-")
            local_path = str(Path(tmpdir) / archive)
            data = self._get_target(policy).read_chunk(archive)
            Path(local_path).write_bytes(data)
            return local_path, True

        if not Path(archive).exists():
            raise FileNotFoundError(f"Archive not found: {archive!r}")
        return archive, False

    # ------------------------------------------------------------------
    # Live-Restore (Schritt 4)
    # ------------------------------------------------------------------

    def restore_snapshot(self, job_id: str, *, restore_path: str | None = None) -> dict[str, Any]:
        """Restore a backup snapshot identified by job_id.

        restore_path: directory to extract into (default: /var/restores/beagle/<job_id>/).
        Returns: {ok, restored_to, files_count, error?}
        """
        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if job.get("status") != "success":
            raise ValueError(f"Job {job_id!r} did not succeed (status={job.get('status')!r})")

        policy = self._find_policy_for_job(job)
        try:
            local_archive, is_temp = self._resolve_archive_local(job, policy)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        try:
            safe_dest = str(restore_path or f"/var/restores/beagle/{job_id}").strip()
            if ".." in safe_dest:
                raise ValueError("restore_path contains path traversal")
            dest = Path(safe_dest).resolve()
            dest.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                ["tar", "-xzf", local_archive, "-C", str(dest)],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                raise RuntimeError(str(result.stderr or "tar extract failed").strip()[:500])

            count_result = subprocess.run(
                ["tar", "-tzf", local_archive],
                capture_output=True,
                text=True,
                timeout=60,
            )
            files_count = len([ln for ln in count_result.stdout.splitlines() if ln.strip()])
            return {"ok": True, "restored_to": str(dest), "files_count": files_count}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            if is_temp:
                shutil.rmtree(str(Path(local_archive).parent), ignore_errors=True)

    # ------------------------------------------------------------------
    # Single-File-Restore (Schritt 5)
    # ------------------------------------------------------------------

    def list_snapshot_files(self, job_id: str) -> dict[str, Any]:
        """List all files inside a backup archive (tar.gz listing).

        Returns: {ok, files: [{path, size, is_dir}]}
        """
        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if job.get("status") != "success":
            raise ValueError(f"Job {job_id!r} did not succeed (status={job.get('status')!r})")

        policy = self._find_policy_for_job(job)
        try:
            local_archive, is_temp = self._resolve_archive_local(job, policy)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "files": []}
        try:
            result = subprocess.run(
                ["tar", "--list", "--verbose", "-f", local_archive],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                raise RuntimeError(str(result.stderr or "tar list failed").strip()[:500])

            files: list[dict[str, Any]] = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if not parts:
                    continue
                # tar -tv format: perms links owner group size date time path
                is_dir = parts[0].startswith("d") if parts else False
                path = parts[-1] if len(parts) >= 6 else line.strip()
                size_str = parts[4] if len(parts) >= 6 else ""
                size = int(size_str) if size_str.isdigit() else 0
                files.append({"path": path, "size": size, "is_dir": is_dir})

            return {"ok": True, "files": files}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "files": []}
        finally:
            if is_temp:
                shutil.rmtree(str(Path(local_archive).parent), ignore_errors=True)

    def read_snapshot_file(self, job_id: str, file_path: str) -> bytes:
        """Extract and return a single file's bytes from a backup archive."""
        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if job.get("status") != "success":
            raise ValueError(f"Job {job_id!r} did not succeed")

        safe_path = str(file_path or "").strip()
        if not safe_path or ".." in safe_path or safe_path.startswith("/"):
            raise ValueError(f"Invalid file_path: {file_path!r}")

        policy = self._find_policy_for_job(job)
        local_archive, is_temp = self._resolve_archive_local(job, policy)
        try:
            result = subprocess.run(
                ["tar", "-xOf", local_archive, "--", safe_path],
                capture_output=True,
                timeout=120,
            )
            if result.returncode != 0:
                raise FileNotFoundError(
                    f"File not found in archive: {safe_path!r} "
                    f"({result.stderr.decode(errors='replace').strip()[:200]})"
                )
            return result.stdout
        finally:
            if is_temp:
                shutil.rmtree(str(Path(local_archive).parent), ignore_errors=True)

    # ------------------------------------------------------------------
    # Cross-Site Replication (Schritt 6)
    # ------------------------------------------------------------------

    def get_replication_config(self) -> dict[str, Any]:
        state = self._load()
        cfg = state.get("replication") or {}
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "remote_url": str(cfg.get("remote_url") or "").strip(),
            "api_token_set": bool(cfg.get("api_token")),
            "auto_replicate": bool(cfg.get("auto_replicate", False)),
        }

    def update_replication_config(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a JSON object")
        state = self._load()
        cfg = dict(state.get("replication") or {})
        if "enabled" in payload:
            cfg["enabled"] = bool(payload["enabled"])
        if "remote_url" in payload:
            url = str(payload["remote_url"] or "").strip()
            if url and not url.startswith(("http://", "https://")):
                raise ValueError("remote_url must start with http:// or https://")
            cfg["remote_url"] = url[:2048]
        if "api_token" in payload:
            cfg["api_token"] = str(payload["api_token"] or "").strip()[:4096]
        if "auto_replicate" in payload:
            cfg["auto_replicate"] = bool(payload["auto_replicate"])
        state["replication"] = cfg
        self._save(state)
        return self.get_replication_config()

    def replicate_to_remote(self, job_id: str) -> dict[str, Any]:
        """Send a backup archive to the configured remote Beagle instance.

        The remote must expose POST /api/v1/backups/ingest.
        Returns: {ok, remote_url, job_id, error?}
        """
        state = self._load()
        cfg = state.get("replication") or {}
        remote_url = str(cfg.get("remote_url") or "").strip()
        api_token = str(cfg.get("api_token") or "").strip()

        if not remote_url:
            raise ValueError("Replication remote_url is not configured")
        if not bool(cfg.get("enabled", False)):
            raise ValueError("Replication is disabled")

        job = self._find_job(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id!r}")
        if job.get("status") != "success":
            raise ValueError(f"Job {job_id!r} did not succeed")

        policy = self._find_policy_for_job(job)
        local_archive, is_temp = self._resolve_archive_local(job, policy)
        try:
            archive_bytes = Path(local_archive).read_bytes()
            ingest_url = remote_url.rstrip("/") + "/api/v1/backups/ingest"
            meta = json.dumps(
                {
                    "job_id": job_id,
                    "scope_type": str(job.get("scope_type") or ""),
                    "scope_id": str(job.get("scope_id") or ""),
                    "archive_name": Path(local_archive).name,
                    "created_at": str(job.get("created_at") or ""),
                }
            )
            req = urllib.request.Request(
                ingest_url,
                data=archive_bytes,
                method="POST",
                headers={
                    "Content-Type": "application/octet-stream",
                    "Authorization": f"Bearer {api_token}",
                    "X-Beagle-Backup-Meta": meta,
                },
            )
            with urllib.request.urlopen(req, timeout=600) as resp:  # noqa: S310
                body = json.loads(resp.read().decode())
            return {"ok": True, "remote_url": remote_url, "job_id": job_id, "remote_response": body}
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode(errors="replace")[:500]
            return {"ok": False, "error": f"HTTP {exc.code}: {body_text}", "remote_url": remote_url, "job_id": job_id}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "remote_url": remote_url, "job_id": job_id}
        finally:
            if is_temp:
                shutil.rmtree(str(Path(local_archive).parent), ignore_errors=True)

    def ingest_replicated_backup(self, *, archive_bytes: bytes, meta: dict[str, Any]) -> dict[str, Any]:
        """Accept an incoming replicated backup archive from a remote Beagle instance."""
        archive_name = str(meta.get("archive_name") or "").strip()
        if not archive_name or "/" in archive_name or ".." in archive_name:
            raise ValueError("Invalid archive_name in replication metadata")

        dest_dir = Path("/var/backups/beagle/replicated")
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / archive_name
        dest_file.write_bytes(archive_bytes)

        state = self._load()
        job: dict[str, Any] = {
            "job_id": str(uuid4()),
            "scope_type": str(meta.get("scope_type") or ""),
            "scope_id": str(meta.get("scope_id") or ""),
            "status": "success",
            "archive": str(dest_file),
            "source": "replicated",
            "origin_job_id": str(meta.get("job_id") or ""),
            "created_at": self._utcnow(),
            "started_at": self._utcnow(),
            "finished_at": self._utcnow(),
        }
        state["jobs"].append(job)
        self._save(state)
        return {"ok": True, "job_id": job["job_id"]}

    # ------------------------------------------------------------------
    # Retention enforcement (Schritt 7 — Plan 16 Testpflicht)
    # ------------------------------------------------------------------

    def prune_old_snapshots(
        self,
        *,
        scope_type: str = "",
        scope_id: str = "",
    ) -> list[dict[str, Any]]:
        """Delete backup jobs older than the policy's retention_days.

        Archives are deleted from their target store (best-effort; errors
        are silently skipped to avoid blocking pruning of other jobs).

        Returns the list of pruned job records so the caller can emit
        audit events (e.g. backup.snapshot_pruned).
        """
        from datetime import date as _date  # noqa: PLC0415

        state = self._load()
        now_iso = self._utcnow()
        now_date_str = now_iso[:10]  # YYYY-MM-DD

        jobs_to_keep: list[dict[str, Any]] = []
        pruned: list[dict[str, Any]] = []

        for job in state.get("jobs", []):
            if not isinstance(job, dict):
                continue
            jtype = str(job.get("scope_type") or "")
            jid = str(job.get("scope_id") or "")

            # Filter to requested scope
            if scope_type and jtype != scope_type:
                jobs_to_keep.append(job)
                continue
            if scope_id and jid != scope_id:
                jobs_to_keep.append(job)
                continue

            # Only prune completed (success) jobs; keep errors/running
            if job.get("status") != "success":
                jobs_to_keep.append(job)
                continue

            # Determine retention_days from matching policy
            try:
                if jtype == "pool":
                    policy = self.get_pool_policy(jid)
                elif jid.isdigit():
                    policy = self.get_vm_policy(int(jid))
                else:
                    jobs_to_keep.append(job)
                    continue
            except Exception:  # noqa: BLE001
                jobs_to_keep.append(job)
                continue

            retention_days = int(policy.get("retention_days") or 7)
            created_at = str(job.get("created_at") or "")[:10]

            if not created_at:
                jobs_to_keep.append(job)
                continue

            try:
                age_days = (_date.fromisoformat(now_date_str) - _date.fromisoformat(created_at)).days
            except ValueError:
                jobs_to_keep.append(job)
                continue

            if age_days < retention_days:
                jobs_to_keep.append(job)
                continue

            # Job has exceeded retention — delete archive and mark pruned
            archive = str(job.get("archive") or "")
            if archive:
                try:
                    self._get_target(policy).delete_snapshot(archive)
                except Exception:  # noqa: BLE001
                    pass  # best-effort: don't block pruning

            pruned.append(dict(job))

        if pruned:
            state["jobs"] = jobs_to_keep
            self._save(state)

        return pruned

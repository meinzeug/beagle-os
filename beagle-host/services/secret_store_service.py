"""Secret Store Service — Rotation, Versioning, Audit.

GoAdvanced Plan 03.

Manages secrets with:
- Version tracking (old version stays valid for grace_period_seconds after rotation)
- Revocation (immediate invalidation)
- Audit events for every access, rotation, revocation
- JSON backend (Phase 1), Vault adapter (Phase 2)

Secret values are NEVER returned in list operations or audit events.
"""
from __future__ import annotations

import secrets as _secrets_mod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class SecretVersion:
    version: int
    value: str                   # plain-text value — only stored in encrypted file
    created_at: str
    status: str = "active"       # "active" | "superseded" | "revoked"
    expires_at: str = ""         # ISO or empty (no expiry)
    superseded_at: str = ""


@dataclass
class SecretMeta:
    """Public metadata — no secret value exposed."""
    name: str
    version: int                 # current active version number
    created_at: str
    rotated_at: str = ""
    expires_at: str = ""
    status: str = "active"
    versions_count: int = 1


class SecretNotFoundError(KeyError):
    pass


class SecretRevokedError(ValueError):
    pass


class SecretStoreService:
    """
    File-based secret store with rotation + audit.

    Storage layout:
        /var/lib/beagle/secrets/<name>.json   (mode 0o600, via JsonStateStore)

    One file per secret.  Each file contains all versions of that secret so
    grace-period checks and rollback are possible without external state.

    Audit events are written via an optional callable (injected; compatible with
    the existing AuditLogService interface).
    """

    SECRETS_DIR = Path("/var/lib/beagle/secrets")
    DEFAULT_GRACE_PERIOD_SECONDS = 24 * 3600  # old version valid 24 h after rotation

    def __init__(
        self,
        secrets_dir: Path | None = None,
        *,
        utcnow: Callable[[], str] | None = None,
        audit_fn: Callable[[str, dict[str, Any]], None] | None = None,
        grace_period_seconds: int = DEFAULT_GRACE_PERIOD_SECONDS,
    ) -> None:
        self._dir = Path(secrets_dir) if secrets_dir else self.SECRETS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._utcnow = utcnow or _utcnow_iso
        self._audit_fn = audit_fn
        self._grace_period = grace_period_seconds

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_secret(self, name: str) -> SecretVersion:
        """Return the active secret version.

        Raises SecretNotFoundError if no secret with that name exists.
        Raises SecretRevokedError if the current version is revoked.
        """
        self._validate_name(name)
        store = self._store(name)
        if not store.exists():
            raise SecretNotFoundError(f"Secret {name!r} not found")
        data = store.load()
        version = self._active_version(data)
        if version is None:
            # No active version — check if latest is revoked
            latest = self._latest_version(data)
            if latest and latest["status"] == "revoked":
                raise SecretRevokedError(f"Secret {name!r} v{latest['version']} is revoked")
            raise SecretNotFoundError(f"Secret {name!r} has no active version")
        if version["status"] == "revoked":
            raise SecretRevokedError(f"Secret {name!r} v{version['version']} is revoked")
        self._audit("secret_accessed", name=name, version=version["version"])
        return SecretVersion(**version)

    def set_secret(self, name: str, value: str, *, expires_at: str = "") -> SecretVersion:
        """Create or replace a secret (initial set, not rotation — no grace period)."""
        self._validate_name(name)
        store = self._store(name)
        data = store.load() if store.exists() else {"versions": []}
        now = self._utcnow()
        # Revoke all existing versions
        for v in data.get("versions", []):
            if v["status"] == "active":
                v["status"] = "superseded"
                v["superseded_at"] = now
        new_ver = asdict(SecretVersion(
            version=len(data.get("versions", [])) + 1,
            value=value,
            created_at=now,
            status="active",
            expires_at=expires_at,
        ))
        data.setdefault("versions", []).append(new_ver)
        store.save(data)
        self._audit("secret_set", name=name, version=new_ver["version"])
        return SecretVersion(**new_ver)

    def rotate_secret(self, name: str, *, new_value: str | None = None) -> SecretVersion:
        """Create a new version of the secret.

        The old version is marked 'superseded' but remains valid for
        grace_period_seconds to allow rolling deployments.
        If new_value is None, a 64-hex-char random value is generated.
        """
        self._validate_name(name)
        store = self._store(name)
        if not store.exists():
            raise SecretNotFoundError(f"Secret {name!r} not found. Use set_secret() first.")
        now = self._utcnow()
        value = new_value if new_value is not None else _secrets_mod.token_hex(32)
        data = store.load()
        current = self._active_version(data)
        if current is not None:
            current["status"] = "superseded"
            current["superseded_at"] = now
        new_ver = asdict(SecretVersion(
            version=(current["version"] + 1) if current else 1,
            value=value,
            created_at=now,
            status="active",
        ))
        data["versions"].append(new_ver)
        store.save(data)
        self._audit("secret_rotated", name=name, new_version=new_ver["version"])
        return SecretVersion(**new_ver)

    def revoke_secret(self, name: str, version: int) -> None:
        """Immediately invalidate a specific version."""
        self._validate_name(name)
        store = self._store(name)
        if not store.exists():
            raise SecretNotFoundError(f"Secret {name!r} not found")
        data = store.load()
        found = False
        for v in data.get("versions", []):
            if v["version"] == version:
                v["status"] = "revoked"
                found = True
        if not found:
            raise SecretNotFoundError(f"Secret {name!r} version {version} not found")
        store.save(data)
        self._audit("secret_revoked", name=name, version=version)

    def list_secrets(self) -> list[SecretMeta]:
        """Return metadata for all known secrets (NO values)."""
        result = []
        for path in sorted(self._dir.glob("*.json")):
            name = path.stem
            try:
                store = self._store(name)
                data = store.load()
                active = self._active_version(data)
                if active is None:
                    continue
                result.append(SecretMeta(
                    name=name,
                    version=active["version"],
                    created_at=active["created_at"],
                    rotated_at=active.get("superseded_at", ""),
                    expires_at=active.get("expires_at", ""),
                    status=active["status"],
                    versions_count=len(data.get("versions", [])),
                ))
            except Exception:  # noqa: BLE001
                continue
        return result

    def has_secret(self, name: str) -> bool:
        """Return True when the named secret has at least one known version."""
        self._validate_name(name)
        store = self._store(name)
        if not store.exists():
            return False
        data = store.load()
        return bool(data.get("versions"))

    def is_valid(self, name: str, value: str, *, version: int | None = None) -> bool:
        """Return True if *value* matches an active or within-grace-period superseded version.

        Used by auth middleware to validate tokens without requiring exact version.
        """
        self._validate_name(name)
        store = self._store(name)
        if not store.exists():
            return False
        data = store.load()
        now = self._utcnow()
        for v in data.get("versions", []):
            if v.get("status") == "revoked":
                continue
            if version is not None and v["version"] != version:
                continue
            if v["value"] != value:
                continue
            if v["status"] == "active":
                return True
            if v["status"] == "superseded" and v.get("superseded_at"):
                # Grace period check
                grace_end = self._add_seconds(v["superseded_at"], self._grace_period)
                if now <= grace_end:
                    return True
        return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store(self, name: str) -> JsonStateStore:
        return JsonStateStore(
            self._dir / f"{name}.json",
            default_factory=lambda: {"versions": []},
            mode=0o600,
        )

    def _active_version(self, data: dict[str, Any]) -> dict[str, Any] | None:
        for v in reversed(data.get("versions", [])):
            if v.get("status") == "active":
                return v
        return None

    def _latest_version(self, data: dict[str, Any]) -> dict[str, Any] | None:
        versions = data.get("versions", [])
        return versions[-1] if versions else None

    def _audit(self, event: str, **kwargs: Any) -> None:
        if self._audit_fn:
            try:
                self._audit_fn(event, kwargs)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _validate_name(name: str) -> None:
        import re
        if not re.fullmatch(r"[a-zA-Z0-9_\-]{1,64}", name):
            raise ValueError(f"Invalid secret name {name!r}. Use only [a-zA-Z0-9_-], max 64 chars.")

    @staticmethod
    def _add_seconds(iso_ts: str, seconds: int) -> str:
        """Add seconds to an ISO timestamp, return ISO string."""
        from datetime import datetime, timezone
        import re
        # Support both Z and +00:00 suffixes
        ts = re.sub(r"Z$", "+00:00", iso_ts)
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            dt = datetime.strptime(iso_ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        from datetime import timedelta
        return (dt + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")

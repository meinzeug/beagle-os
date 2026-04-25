"""Cluster Enrollment Token Service — Einmal-Token für Zero-Touch Node-Join.

GoEnterprise Plan 08, Schritt 4
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from core.persistence.json_state_store import JsonStateStore


@dataclass
class EnrollmentToken:
    token_id: str
    token: str                  # 32-byte hex secret
    created_at: str
    expires_at: str             # ISO UTC
    used: bool = False
    used_at: str = ""
    used_by_node: str = ""      # hostname/IP of joining node
    cluster_id: str = ""
    label: str = ""             # optional human label


class ClusterEnrollmentService:
    """
    Generates and validates single-use cluster enrollment tokens.

    Tokens are valid for 24 hours (configurable) and can only be used once.
    Used by new bare-metal nodes to join the cluster without manual admin steps.

    GoEnterprise Plan 08, Schritt 4
    """

    STATE_FILE = Path("/var/lib/beagle/cluster-enrollment/tokens.json")
    DEFAULT_TTL_HOURS = 24

    def __init__(
        self,
        state_file: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> None:
        self._store = JsonStateStore(
            state_file or self.STATE_FILE,
            default_factory=lambda: {"tokens": {}},
        )
        self._utcnow = utcnow or self._default_utcnow
        self._ttl_hours = ttl_hours
        self._state = self._store.load()

    # ------------------------------------------------------------------
    # Token generation
    # ------------------------------------------------------------------

    def generate_token(
        self,
        *,
        cluster_id: str = "",
        label: str = "",
    ) -> EnrollmentToken:
        """Generate a new single-use enrollment token valid for ttl_hours."""
        from datetime import datetime, timezone, timedelta

        token_secret = secrets.token_hex(32)
        token_id = hashlib.sha256(token_secret.encode()).hexdigest()[:16]

        now_str = self._utcnow()
        now_dt = self._parse_ts(now_str)
        expires_dt = now_dt + timedelta(hours=self._ttl_hours)
        expires_at = expires_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        token = EnrollmentToken(
            token_id=token_id,
            token=token_secret,
            created_at=now_str,
            expires_at=expires_at,
            cluster_id=cluster_id,
            label=label,
        )
        self._state["tokens"][token_id] = asdict(token)
        self._save()
        return token

    # ------------------------------------------------------------------
    # Token validation / consumption
    # ------------------------------------------------------------------

    def validate_token(self, token_secret: str) -> EnrollmentToken | None:
        """
        Validate a token secret. Returns the token if valid (unused + not expired).
        Does NOT consume the token — call consume_token() separately.
        """
        token_id = hashlib.sha256(token_secret.encode()).hexdigest()[:16]
        d = self._state["tokens"].get(token_id)
        if not d:
            return None
        t = EnrollmentToken(**d)
        if t.used:
            return None
        now_str = self._utcnow()
        if now_str >= t.expires_at:
            return None
        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(token_secret, t.token):
            return None
        return t

    def consume_token(self, token_secret: str, node_id: str = "") -> EnrollmentToken | None:
        """
        Validate and mark a token as used. Returns the token or None if invalid.
        After this call the token cannot be reused.
        """
        t = self.validate_token(token_secret)
        if t is None:
            return None
        d = self._state["tokens"][t.token_id]
        d["used"] = True
        d["used_at"] = self._utcnow()
        d["used_by_node"] = node_id
        self._save()
        return EnrollmentToken(**d)

    # ------------------------------------------------------------------
    # Token queries
    # ------------------------------------------------------------------

    def get_token(self, token_id: str) -> EnrollmentToken | None:
        d = self._state["tokens"].get(token_id)
        return EnrollmentToken(**d) if d else None

    def list_tokens(self, *, include_used: bool = True, include_expired: bool = True) -> list[EnrollmentToken]:
        now_str = self._utcnow()
        tokens = [EnrollmentToken(**d) for d in self._state["tokens"].values()]
        if not include_used:
            tokens = [t for t in tokens if not t.used]
        if not include_expired:
            tokens = [t for t in tokens if t.expires_at > now_str]
        return tokens

    def revoke_token(self, token_id: str) -> bool:
        d = self._state["tokens"].get(token_id)
        if not d:
            return False
        d["used"] = True
        d["used_at"] = self._utcnow()
        d["used_by_node"] = "__revoked__"
        self._save()
        return True

    def cleanup_expired(self) -> int:
        """Remove expired unused tokens. Returns count removed."""
        now_str = self._utcnow()
        before = len(self._state["tokens"])
        self._state["tokens"] = {
            tid: d for tid, d in self._state["tokens"].items()
            if not (d.get("expires_at", "") <= now_str and not d.get("used"))
        }
        removed = before - len(self._state["tokens"])
        if removed:
            self._save()
        return removed

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_ts(ts: str):
        from datetime import datetime, timezone
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse timestamp: {ts!r}")

    def _save(self) -> None:
        self._store.save(self._state)

    @staticmethod
    def _default_utcnow() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

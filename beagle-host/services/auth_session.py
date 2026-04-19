"""Username/password authentication and session-token management."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Callable


MIN_PASSWORD_LENGTH = 8


class AuthSessionService:
    def __init__(
        self,
        *,
        data_dir: Path,
        load_json_file: Callable[[Path, Any], Any],
        write_json_file: Callable[[Path, Any], None],
        now: Callable[[], float],
        token_urlsafe: Callable[[int], str],
        access_ttl_seconds: int = 3600,
        refresh_ttl_seconds: int = 7 * 24 * 3600,
        idle_timeout_seconds: int = 1800,
        absolute_timeout_seconds: int = 7 * 24 * 3600,
        max_sessions_per_user: int = 5,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._load_json_file = load_json_file
        self._write_json_file = write_json_file
        self._now = now
        self._token_urlsafe = token_urlsafe
        self._access_ttl_seconds = max(60, int(access_ttl_seconds))
        self._refresh_ttl_seconds = max(self._access_ttl_seconds, int(refresh_ttl_seconds))
        self._idle_timeout_seconds = max(60, int(idle_timeout_seconds))
        self._absolute_timeout_seconds = max(self._refresh_ttl_seconds, int(absolute_timeout_seconds))
        self._max_sessions_per_user = max(0, int(max_sessions_per_user))
        self._users_path = self._data_dir / "auth" / "users.json"
        self._roles_path = self._data_dir / "auth" / "roles.json"
        self._sessions_path = self._data_dir / "auth" / "sessions.json"
        self._onboarding_path = self._data_dir / "auth" / "onboarding.json"
        # ThreadingHTTPServer handles requests concurrently; serialize auth state I/O
        # so token/session updates cannot overwrite each other.
        self._state_lock = threading.RLock()

    @staticmethod
    def _default_roles() -> list[dict[str, Any]]:
        return [
            {"name": "viewer", "permissions": []},
            {"name": "ops", "permissions": ["vm:mutate", "actions:bulk", "provisioning:write"]},
            {"name": "admin", "permissions": ["vm:mutate", "actions:bulk", "provisioning:write", "policy:write", "auth:read"]},
            {"name": "superadmin", "permissions": ["*"]},
        ]

    def ensure_bootstrap_admin(self, *, username: str, password: str) -> None:
        _ = self._load_roles_doc()
        user_name = str(username or "").strip()
        passwd = str(password or "")
        if not user_name or not passwd:
            return
        users_doc = self._load_users_doc()
        users = users_doc.setdefault("users", [])
        if any(str(item.get("username") or "").strip().lower() == user_name.lower() for item in users if isinstance(item, dict)):
            return
        users.append(
            {
                "username": user_name,
                "role": "superadmin",
                "password_hash": self.hash_password(passwd),
                "created_at": int(self._now()),
                "enabled": True,
            }
        )
        self._write_json_file(self._users_path, users_doc)

    def list_users(self) -> list[dict[str, Any]]:
        users_doc = self._load_users_doc()
        result: list[dict[str, Any]] = []
        for item in users_doc.get("users", []):
            if not isinstance(item, dict):
                continue
            result.append(
                {
                    "username": str(item.get("username") or "").strip(),
                    "role": str(item.get("role") or "viewer").strip() or "viewer",
                    "enabled": bool(item.get("enabled", True)),
                    "created_at": int(item.get("created_at") or 0),
                }
            )
        return sorted(result, key=lambda entry: entry["username"].lower())

    def create_user(self, *, username: str, password: str, role: str, enabled: bool = True) -> dict[str, Any]:
        user_name = str(username or "").strip()
        if not user_name:
            raise ValueError("username is required")
        passwd = str(password or "")
        if not passwd:
            raise ValueError("password is required")
        if len(passwd) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
        role_name = str(role or "").strip().lower() or "viewer"
        if not self._role_exists(role_name):
            raise ValueError("unknown role")
        users_doc = self._load_users_doc()
        users = users_doc.setdefault("users", [])
        if any(str(item.get("username") or "").strip().lower() == user_name.lower() for item in users if isinstance(item, dict)):
            raise ValueError("user already exists")
        created = {
            "username": user_name,
            "role": role_name,
            "password_hash": self.hash_password(passwd),
            "created_at": int(self._now()),
            "enabled": bool(enabled),
        }
        users.append(created)
        self._write_json_file(self._users_path, users_doc)
        return {
            "username": user_name,
            "role": role_name,
            "enabled": bool(enabled),
            "created_at": int(created["created_at"]),
        }

    def update_user(
        self,
        *,
        username: str,
        role: str | None = None,
        enabled: bool | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        user_name = str(username or "").strip()
        if not user_name:
            raise ValueError("username is required")
        users_doc = self._load_users_doc()
        users = users_doc.setdefault("users", [])
        target: dict[str, Any] | None = None
        for item in users:
            if not isinstance(item, dict):
                continue
            if str(item.get("username") or "").strip().lower() == user_name.lower():
                target = item
                break
        if target is None:
            raise ValueError("user not found")
        if role is not None:
            role_name = str(role or "").strip().lower() or "viewer"
            if not self._role_exists(role_name):
                raise ValueError("unknown role")
            target["role"] = role_name
        if enabled is not None:
            target["enabled"] = bool(enabled)
        if password is not None:
            passwd = str(password or "")
            if not passwd:
                raise ValueError("password is required")
            if len(passwd) < MIN_PASSWORD_LENGTH:
                raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")
            target["password_hash"] = self.hash_password(passwd)
        self._write_json_file(self._users_path, users_doc)
        return {
            "username": str(target.get("username") or "").strip(),
            "role": str(target.get("role") or "viewer").strip() or "viewer",
            "enabled": bool(target.get("enabled", True)),
            "created_at": int(target.get("created_at") or 0),
        }

    def delete_user(self, username: str) -> bool:
        user_name = str(username or "").strip()
        if not user_name:
            return False
        users_doc = self._load_users_doc()
        users = users_doc.setdefault("users", [])
        before = len(users)
        users_doc["users"] = [
            item
            for item in users
            if not (isinstance(item, dict) and str(item.get("username") or "").strip().lower() == user_name.lower())
        ]
        changed = len(users_doc["users"]) != before
        if changed:
            self._write_json_file(self._users_path, users_doc)
        return changed

    def list_roles(self) -> list[dict[str, Any]]:
        roles_doc = self._load_roles_doc()
        roles = roles_doc.get("roles", [])
        output: list[dict[str, Any]] = []
        for item in roles:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip().lower()
            if not name:
                continue
            perms = [str(value).strip() for value in (item.get("permissions") or []) if str(value).strip()]
            output.append({"name": name, "permissions": sorted(set(perms))})
        return sorted(output, key=lambda role: role["name"])

    def save_role(self, *, name: str, permissions: list[str]) -> dict[str, Any]:
        role_name = str(name or "").strip().lower()
        if not role_name:
            raise ValueError("role name is required")
        perms = sorted({str(item).strip() for item in permissions if str(item).strip()})
        roles_doc = self._load_roles_doc()
        roles = roles_doc.setdefault("roles", [])
        existing: dict[str, Any] | None = None
        for item in roles:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip().lower() == role_name:
                existing = item
                break
        if existing is None:
            existing = {"name": role_name, "permissions": perms}
            roles.append(existing)
        else:
            existing["permissions"] = perms
        self._write_json_file(self._roles_path, roles_doc)
        return {"name": role_name, "permissions": perms}

    def delete_role(self, name: str) -> bool:
        role_name = str(name or "").strip().lower()
        if not role_name or role_name == "superadmin":
            return False
        roles_doc = self._load_roles_doc()
        roles = roles_doc.setdefault("roles", [])
        before = len(roles)
        roles_doc["roles"] = [
            item
            for item in roles
            if not (isinstance(item, dict) and str(item.get("name") or "").strip().lower() == role_name)
        ]
        changed = len(roles_doc["roles"]) != before
        if changed:
            users_doc = self._load_users_doc()
            for user in users_doc.get("users", []):
                if not isinstance(user, dict):
                    continue
                if str(user.get("role") or "").strip().lower() == role_name:
                    user["role"] = "viewer"
            self._write_json_file(self._roles_path, roles_doc)
            self._write_json_file(self._users_path, users_doc)
        return changed

    def role_permissions(self, role: str) -> set[str]:
        role_name = str(role or "").strip().lower()
        if not role_name:
            return set()
        for item in self.list_roles():
            if item.get("name") == role_name:
                return {str(value).strip() for value in item.get("permissions", []) if str(value).strip()}
        return set()

    def onboarding_status(
        self,
        *,
        bootstrap_username: str = "admin",
        bootstrap_disabled: bool = False,
    ) -> dict[str, Any]:
        onboarding = self._load_onboarding_doc()
        users = self.list_users()
        bootstrap = str(bootstrap_username or "admin").strip().lower() or "admin"
        enabled_users = [
            item
            for item in users
            if bool(item.get("enabled", True))
        ]
        non_bootstrap_users = [
            item
            for item in enabled_users
            if str(item.get("username") or "").strip().lower() != bootstrap
        ]

        # If bootstrap auth is disabled, remove bootstrap-only legacy users so
        # onboarding can create the real first admin account.
        if bootstrap_disabled and not non_bootstrap_users and enabled_users:
            users_doc = self._load_users_doc()
            filtered_users = []
            removed_bootstrap_user = False
            for item in users_doc.get("users", []):
                if not isinstance(item, dict):
                    continue
                username = str(item.get("username") or "").strip().lower()
                if username == bootstrap:
                    removed_bootstrap_user = True
                    continue
                filtered_users.append(item)
            if removed_bootstrap_user:
                users_doc["users"] = filtered_users
                self._write_json_file(self._users_path, users_doc)
                users = self.list_users()
                enabled_users = [
                    item
                    for item in users
                    if bool(item.get("enabled", True))
                ]
                non_bootstrap_users = [
                    item
                    for item in enabled_users
                    if str(item.get("username") or "").strip().lower() != bootstrap
                ]

        completed = bool(onboarding.get("completed")) or bool(non_bootstrap_users)
        if not bootstrap_disabled and enabled_users:
            completed = True

        # If bootstrap auth is disabled, a leftover bootstrap-only onboarding
        # completion marker must not suppress onboarding.
        if bootstrap_disabled and not non_bootstrap_users and bool(onboarding.get("completed")):
            onboarding["completed"] = False
            onboarding["completed_at"] = 0
            onboarding["completed_by"] = ""
            self._write_json_file(self._onboarding_path, onboarding)
            completed = False

        if completed and not bool(onboarding.get("completed")):
            onboarding["completed"] = True
            onboarding["completed_at"] = int(self._now())
            onboarding["completed_by"] = (
                str(non_bootstrap_users[0].get("username") or "")
                if non_bootstrap_users
                else str(enabled_users[0].get("username") or bootstrap)
            )
            self._write_json_file(self._onboarding_path, onboarding)
        return {
            "pending": not completed,
            "completed": bool(completed),
            "completed_at": int(onboarding.get("completed_at") or 0),
            "completed_by": str(onboarding.get("completed_by") or "").strip(),
            "user_count": len(users),
        }

    def complete_onboarding(
        self,
        *,
        username: str,
        password: str,
        bootstrap_username: str = "admin",
        bootstrap_disabled: bool = False,
    ) -> dict[str, Any]:
        user_name = str(username or "").strip()
        passwd = str(password or "")
        if not user_name:
            raise ValueError("username is required")
        if not passwd:
            raise ValueError("password is required")
        if len(passwd) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")

        status = self.onboarding_status(
            bootstrap_username=bootstrap_username,
            bootstrap_disabled=bootstrap_disabled,
        )
        if not bool(status.get("pending")):
            raise ValueError("onboarding already completed")

        existing = self._find_user(user_name)
        if existing is None:
            self.create_user(username=user_name, password=passwd, role="superadmin", enabled=True)
        else:
            self.update_user(username=user_name, role="superadmin", enabled=True, password=passwd)

        onboarding = self._load_onboarding_doc()
        onboarding["completed"] = True
        onboarding["completed_at"] = int(self._now())
        onboarding["completed_by"] = user_name
        self._write_json_file(self._onboarding_path, onboarding)
        return self.onboarding_status(
            bootstrap_username=bootstrap_username,
            bootstrap_disabled=bootstrap_disabled,
        )

    def login(self, *, username: str, password: str, remote_addr: str = "", user_agent: str = "") -> dict[str, Any] | None:
        with self._state_lock:
            user = self._find_user(username)
            if user is None:
                return None
            if not bool(user.get("enabled", True)):
                return None
            if not self.verify_password(str(password or ""), str(user.get("password_hash") or "")):
                return None
            return self._issue_session(
                username=str(user.get("username") or "").strip(),
                role=str(user.get("role") or "viewer").strip() or "viewer",
                remote_addr=remote_addr,
                user_agent=user_agent,
            )

    def refresh(self, refresh_token: str) -> dict[str, Any] | None:
        with self._state_lock:
            token = str(refresh_token or "").strip()
            if not token:
                return None
            sessions_doc = self._load_sessions_doc()
            sessions = sessions_doc.setdefault("sessions", [])
            now_ts = int(self._now())
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                if bool(session.get("revoked")):
                    continue
                if str(session.get("refresh_token") or "") != token:
                    continue
                if self._session_expired(session, now_ts, include_access_expiry=False):
                    session["revoked"] = True
                    self._write_json_file(self._sessions_path, sessions_doc)
                    return None
                username = str(session.get("username") or "").strip()
                user = self._find_user(username)
                if user is None or not bool(user.get("enabled", True)):
                    session["revoked"] = True
                    self._write_json_file(self._sessions_path, sessions_doc)
                    return None
                role = str(user.get("role") or session.get("role") or "viewer").strip() or "viewer"
                access_token = self._token_urlsafe(48)
                session["access_token"] = access_token
                session["last_seen_at"] = now_ts
                session["access_expires_at"] = now_ts + self._access_ttl_seconds
                self._write_json_file(self._sessions_path, sessions_doc)
                return {
                    "ok": True,
                    "access_token": access_token,
                    "refresh_token": str(session.get("refresh_token") or token),
                    "token_type": "Bearer",
                    "expires_in": self._access_ttl_seconds,
                    "user": {
                        "username": username,
                        "role": role,
                    },
                }
            return None

    def resolve_access_token(self, access_token: str) -> dict[str, Any] | None:
        with self._state_lock:
            token = str(access_token or "").strip()
            if not token:
                return None
            sessions_doc = self._load_sessions_doc()
            sessions = sessions_doc.setdefault("sessions", [])
            now_ts = int(self._now())
            dirty = False
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                if bool(session.get("revoked")):
                    continue
                if str(session.get("access_token") or "") != token:
                    continue
                if self._session_expired(session, now_ts, include_access_expiry=True):
                    session["revoked"] = True
                    dirty = True
                    continue
                session["last_seen_at"] = now_ts
                session["access_expires_at"] = now_ts + self._access_ttl_seconds
                self._write_json_file(self._sessions_path, sessions_doc)
                return {
                    "username": str(session.get("username") or "").strip(),
                    "role": str(session.get("role") or "viewer").strip() or "viewer",
                    "auth_type": "session",
                    "session_id": str(session.get("id") or "").strip(),
                }
            if dirty:
                self._write_json_file(self._sessions_path, sessions_doc)
            return None

    def revoke(self, *, access_token: str = "", refresh_token: str = "") -> bool:
        with self._state_lock:
            at = str(access_token or "").strip()
            rt = str(refresh_token or "").strip()
            if not at and not rt:
                return False
            sessions_doc = self._load_sessions_doc()
            sessions = sessions_doc.setdefault("sessions", [])
            changed = False
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                if bool(session.get("revoked")):
                    continue
                if at and str(session.get("access_token") or "") == at:
                    session["revoked"] = True
                    changed = True
                if rt and str(session.get("refresh_token") or "") == rt:
                    session["revoked"] = True
                    changed = True
            if changed:
                self._write_json_file(self._sessions_path, sessions_doc)
            return changed

    def revoke_user_sessions(self, username: str) -> int:
        with self._state_lock:
            user_name = str(username or "").strip().lower()
            if not user_name:
                return 0
            sessions_doc = self._load_sessions_doc()
            sessions = sessions_doc.setdefault("sessions", [])
            revoked_count = 0
            for session in sessions:
                if not isinstance(session, dict):
                    continue
                if bool(session.get("revoked")):
                    continue
                if str(session.get("username") or "").strip().lower() != user_name:
                    continue
                session["revoked"] = True
                revoked_count += 1
            if revoked_count > 0:
                self._write_json_file(self._sessions_path, sessions_doc)
            return revoked_count

    def hash_password(self, password: str, *, iterations: int = 390000) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, int(iterations))
        return f"pbkdf2_sha256${int(iterations)}${salt.hex()}${digest.hex()}"

    def verify_password(self, password: str, password_hash: str) -> bool:
        parts = str(password_hash or "").split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        try:
            iterations = int(parts[1])
            salt = bytes.fromhex(parts[2])
            expected = bytes.fromhex(parts[3])
        except Exception:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", str(password or "").encode("utf-8"), salt, iterations)
        return secrets.compare_digest(candidate, expected)

    def _issue_session(
        self,
        *,
        username: str,
        role: str,
        remote_addr: str,
        user_agent: str,
        sessions_doc: dict[str, Any] | None = None,
        sessions: list[Any] | None = None,
    ) -> dict[str, Any]:
        with self._state_lock:
            now_ts = int(self._now())
            access_token = self._token_urlsafe(48)
            refresh_token = self._token_urlsafe(48)
            session_id = self._token_urlsafe(16)
            payload = {
                "id": session_id,
                "username": username,
                "role": role,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "created_at": now_ts,
                "last_seen_at": now_ts,
                "access_expires_at": now_ts + self._access_ttl_seconds,
                "refresh_expires_at": now_ts + self._refresh_ttl_seconds,
                "absolute_expires_at": now_ts + self._absolute_timeout_seconds,
                "remote_addr": remote_addr,
                "user_agent": user_agent,
                "revoked": False,
            }
            if sessions_doc is None or sessions is None:
                sessions_doc = self._load_sessions_doc()
                sessions = sessions_doc.setdefault("sessions", [])
            self._enforce_session_limit(sessions=sessions, username=username, now_ts=now_ts)
            sessions.append(payload)
            self._write_json_file(self._sessions_path, sessions_doc)
            return {
                "ok": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": self._access_ttl_seconds,
                "user": {
                    "username": username,
                    "role": role,
                },
            }

    def _enforce_session_limit(self, *, sessions: list[Any], username: str, now_ts: int) -> None:
        if self._max_sessions_per_user <= 0:
            return
        user_name = str(username or "").strip().lower()
        if not user_name:
            return
        active_sessions: list[dict[str, Any]] = []
        for session in sessions:
            if not isinstance(session, dict):
                continue
            if str(session.get("username") or "").strip().lower() != user_name:
                continue
            if self._session_expired(session, now_ts, include_access_expiry=False):
                session["revoked"] = True
                continue
            active_sessions.append(session)
        if len(active_sessions) < self._max_sessions_per_user:
            return
        active_sessions.sort(
            key=lambda session: (
                int(session.get("last_seen_at") or session.get("created_at") or 0),
                int(session.get("created_at") or 0),
            )
        )
        while len(active_sessions) >= self._max_sessions_per_user:
            oldest = active_sessions.pop(0)
            oldest["revoked"] = True

    def _session_expired(self, session: dict[str, Any], now_ts: int, *, include_access_expiry: bool) -> bool:
        if bool(session.get("revoked")):
            return True
        access_expires_at = int(session.get("access_expires_at") or 0)
        refresh_expires_at = int(session.get("refresh_expires_at") or 0)
        absolute_expires_at = int(session.get("absolute_expires_at") or 0)
        last_seen_at = int(session.get("last_seen_at") or session.get("created_at") or 0)
        if include_access_expiry and access_expires_at and now_ts > access_expires_at:
            return True
        if refresh_expires_at and now_ts > refresh_expires_at:
            return True
        if absolute_expires_at and now_ts > absolute_expires_at:
            return True
        if now_ts - last_seen_at > self._idle_timeout_seconds:
            return True
        return False

    def _load_users_doc(self) -> dict[str, Any]:
        payload = self._load_json_file(self._users_path, {"users": []})
        if not isinstance(payload, dict):
            return {"users": []}
        if not isinstance(payload.get("users"), list):
            payload["users"] = []
        return payload

    def _load_roles_doc(self) -> dict[str, Any]:
        payload = self._load_json_file(self._roles_path, {"roles": self._default_roles()})
        if not isinstance(payload, dict):
            payload = {"roles": self._default_roles()}
        if not isinstance(payload.get("roles"), list):
            payload["roles"] = self._default_roles()
        normalized = []
        for item in payload.get("roles", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip().lower()
            if not name:
                continue
            perms = [str(value).strip() for value in (item.get("permissions") or []) if str(value).strip()]
            normalized.append({"name": name, "permissions": sorted(set(perms))})
        if not normalized:
            normalized = self._default_roles()
        payload["roles"] = normalized
        self._write_json_file(self._roles_path, payload)
        return payload

    def _role_exists(self, role_name: str) -> bool:
        role = str(role_name or "").strip().lower()
        if not role:
            return False
        for item in self.list_roles():
            if item.get("name") == role:
                return True
        return False

    def _load_sessions_doc(self) -> dict[str, Any]:
        payload = self._load_json_file(self._sessions_path, {"sessions": []})
        if not isinstance(payload, dict):
            return {"sessions": []}
        if not isinstance(payload.get("sessions"), list):
            payload["sessions"] = []
        return payload

    def _load_onboarding_doc(self) -> dict[str, Any]:
        payload = self._load_json_file(
            self._onboarding_path,
            {
                "completed": False,
                "completed_at": 0,
                "completed_by": "",
            },
        )
        if not isinstance(payload, dict):
            payload = {
                "completed": False,
                "completed_at": 0,
                "completed_by": "",
            }
        payload["completed"] = bool(payload.get("completed", False))
        payload["completed_at"] = int(payload.get("completed_at") or 0)
        payload["completed_by"] = str(payload.get("completed_by") or "").strip()
        return payload

    def _find_user(self, username: str) -> dict[str, Any] | None:
        name = str(username or "").strip().lower()
        if not name:
            return None
        users_doc = self._load_users_doc()
        for item in users_doc.get("users", []):
            if not isinstance(item, dict):
                continue
            if str(item.get("username") or "").strip().lower() == name:
                return item
        return None


def default_now() -> float:
    return time.time()

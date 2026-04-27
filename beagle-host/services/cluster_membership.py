from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import shutil
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ca_manager import ClusterCaService


class ClusterMembershipService:
    def __init__(
        self,
        *,
        data_dir: Path,
        ca_service: ClusterCaService,
        public_manager_url: str,
        rpc_port: int,
        utcnow,
        control_env_file: Path | None = None,
        install_check_report_token: str = "",
        rpc_request=None,
        rpc_credentials=None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._ca_service = ca_service
        self._public_manager_url = str(public_manager_url or "").strip().rstrip("/")
        self._rpc_port = int(rpc_port)
        self._utcnow = utcnow
        self._control_env_file = Path(control_env_file) if control_env_file else None
        self._install_check_report_token = str(install_check_report_token or "").strip()
        self._rpc_request = rpc_request
        self._rpc_credentials = rpc_credentials

    def cluster_dir(self) -> Path:
        path = self._data_dir / "cluster"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self) -> Path:
        return self.cluster_dir() / "cluster-state.json"

    def members_file(self) -> Path:
        return self.cluster_dir() / "members.json"

    def join_tokens_file(self) -> Path:
        return self.cluster_dir() / "join-tokens.json"

    def setup_codes_file(self) -> Path:
        return self.cluster_dir() / "setup-codes.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return default

    def _write_json(self, path: Path, payload: Any, *, mode: int = 0o600) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)
        try:
            path.chmod(mode)
        except OSError:
            pass

    @staticmethod
    def _host_from_url(url: str) -> str:
        parsed = urlparse(str(url or "").strip())
        return str(parsed.hostname or "").strip()

    @staticmethod
    def _maybe_ip_san(host: str) -> str | None:
        text = str(host or "").strip()
        if not text:
            return None
        if all(part.isdigit() and 0 <= int(part) <= 255 for part in text.split(".")) and text.count(".") == 3:
            return f"IP:{text}"
        return None

    def _node_sans(self, *, node_name: str, api_url: str, rpc_url: str) -> list[str]:
        sans = [f"DNS:{node_name}"]
        for host in (self._host_from_url(api_url), self._host_from_url(rpc_url)):
            if not host:
                continue
            ip_san = self._maybe_ip_san(host)
            sans.append(ip_san or f"DNS:{host}")
        unique: list[str] = []
        for item in sans:
            if item and item not in unique:
                unique.append(item)
        return unique

    def _build_rpc_url(self, *, host: str) -> str:
        normalized_host = str(host or "").strip()
        if not normalized_host:
            raise ValueError("cluster host is required")
        return f"https://{normalized_host}:{int(self._rpc_port)}/rpc"

    @staticmethod
    def _api_v1_url(base_url: str, path: str) -> str:
        base = str(base_url or "").strip().rstrip("/")
        route = "/" + str(path or "").strip().lstrip("/")
        if not base:
            raise ValueError("leader api url is required")
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("leader api url must be an absolute http(s) URL")
        if base.endswith("/api/v1"):
            return f"{base}{route}"
        return f"{base}/api/v1{route}"

    @staticmethod
    def _healthz_url(base_url: str) -> str:
        base = str(base_url or "").strip().rstrip("/")
        if not base:
            raise ValueError("api url is required")
        if base.endswith("/api/v1"):
            base = base[:-len("/api/v1")]
        return f"{base}/healthz"

    @staticmethod
    def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 15.0) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                response_body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"cluster leader returned HTTP {exc.code}: {error_body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"cluster leader unreachable: {exc.reason}") from exc
        parsed = json.loads(response_body or "{}")
        if not isinstance(parsed, dict):
            raise RuntimeError("cluster leader returned invalid JSON")
        if parsed.get("ok") is False:
            raise RuntimeError(str(parsed.get("error") or "cluster leader rejected join"))
        return parsed

    @staticmethod
    def _tcp_check(host: str, port: int, *, timeout: float = 3.0) -> tuple[bool, str]:
        try:
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True, "reachable"
        except OSError as exc:
            return False, str(exc)

    @staticmethod
    def _preflight_check(name: str, status: str, message: str, *, required: bool = True) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "message": message,
            "required": bool(required),
        }

    def preflight_add_server(
        self,
        *,
        node_name: str,
        api_url: str,
        advertise_host: str = "",
        rpc_url: str = "",
        ssh_port: int = 22,
        timeout: float = 3.0,
        issue_join_token: bool = False,
        token_ttl_seconds: int = 900,
        require_rpc: bool = True,
    ) -> dict[str, Any]:
        normalized_node = str(node_name or "").strip()
        normalized_api_url = str(api_url or "").strip().rstrip("/")
        normalized_host = str(advertise_host or self._host_from_url(normalized_api_url)).strip()
        normalized_rpc_url = str(rpc_url or "").strip().rstrip("/")
        if not normalized_rpc_url and normalized_host:
            normalized_rpc_url = self._build_rpc_url(host=normalized_host)

        checks: list[dict[str, Any]] = []
        if not self.is_initialized():
            checks.append(self._preflight_check("cluster_initialized", "fail", "cluster is not initialized"))
        else:
            checks.append(self._preflight_check("cluster_initialized", "pass", "cluster is initialized"))

        if not normalized_node:
            checks.append(self._preflight_check("node_name", "fail", "node_name is required"))
        elif any(str(member.get("name") or "") == normalized_node for member in self.list_members() if isinstance(member, dict)):
            checks.append(self._preflight_check("node_name", "fail", f"node '{normalized_node}' already exists"))
        else:
            checks.append(self._preflight_check("node_name", "pass", f"node '{normalized_node}' is available"))

        if not normalized_api_url:
            checks.append(self._preflight_check("api_url", "fail", "api_url is required"))
            api_parsed = None
        else:
            api_parsed = urlparse(normalized_api_url)
            if api_parsed.scheme not in {"http", "https"} or not api_parsed.hostname:
                checks.append(self._preflight_check("api_url", "fail", "api_url must be an absolute http(s) URL"))
            else:
                checks.append(self._preflight_check("api_url", "pass", "api_url format is valid"))

        if not normalized_host:
            checks.append(self._preflight_check("advertise_host", "fail", "advertise_host is required"))
        else:
            try:
                socket.getaddrinfo(normalized_host, None)
                checks.append(self._preflight_check("dns", "pass", f"{normalized_host} resolves"))
            except OSError as exc:
                checks.append(self._preflight_check("dns", "fail", f"{normalized_host} does not resolve: {exc}"))

        if api_parsed is not None and api_parsed.hostname:
            api_port = int(api_parsed.port or (443 if api_parsed.scheme == "https" else 80))
            ok, detail = self._tcp_check(api_parsed.hostname, api_port, timeout=timeout)
            checks.append(self._preflight_check("api_tcp", "pass" if ok else "fail", f"{api_parsed.hostname}:{api_port} {detail}"))
            checks.append(self._preflight_check(
                "api_health",
                "skipped",
                "authenticated remote setup token required; unauthenticated health probes are not used",
                required=False,
            ))

        rpc_parsed = urlparse(normalized_rpc_url)
        if not require_rpc:
            checks.append(self._preflight_check(
                "rpc_tcp",
                "skipped",
                "RPC proof runs after setup-code verification and cluster join",
                required=False,
            ))
        elif rpc_parsed.hostname:
            rpc_port = int(rpc_parsed.port or self._rpc_port)
            ok, detail = self._tcp_check(rpc_parsed.hostname, rpc_port, timeout=timeout)
            checks.append(self._preflight_check("rpc_tcp", "pass" if ok else "fail", f"{rpc_parsed.hostname}:{rpc_port} {detail}"))
        else:
            checks.append(self._preflight_check("rpc_url", "fail", "rpc_url could not be derived"))

        if normalized_host:
            ok, detail = self._tcp_check(normalized_host, int(ssh_port or 22), timeout=timeout)
            checks.append(self._preflight_check("ssh_tcp", "pass" if ok else "warn", f"{normalized_host}:{int(ssh_port or 22)} {detail}", required=False))
        else:
            checks.append(self._preflight_check("ssh_tcp", "skipped", "advertise_host missing", required=False))

        checks.append(self._preflight_check("kvm", "skipped", "remote KVM/libvirt proof requires authenticated remote preflight job", required=False))
        checks.append(self._preflight_check("libvirt", "skipped", "remote libvirt proof requires authenticated remote preflight job", required=False))

        required_failed = [item for item in checks if item.get("required") and item.get("status") != "pass"]
        payload: dict[str, Any] = {
            "ok": not required_failed,
            "node_name": normalized_node,
            "api_url": normalized_api_url,
            "advertise_host": normalized_host,
            "rpc_url": normalized_rpc_url,
            "checks": checks,
            "summary": {
                "passed": len([item for item in checks if item.get("status") == "pass"]),
                "failed": len([item for item in checks if item.get("status") == "fail"]),
                "warnings": len([item for item in checks if item.get("status") == "warn"]),
                "skipped": len([item for item in checks if item.get("status") == "skipped"]),
            },
        }
        if issue_join_token and payload["ok"]:
            payload["join_token"] = self.create_join_token(ttl_seconds=token_ttl_seconds)
        return payload

    @staticmethod
    def _setup_code_hash(code: str) -> str:
        text = str(code or "").strip()
        if not text:
            raise ValueError("setup_code is required")
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_setup_codes(self) -> dict[str, dict[str, Any]]:
        payload = self._read_json(self.setup_codes_file(), {})
        return payload if isinstance(payload, dict) else {}

    def _cleanup_setup_codes(self) -> dict[str, dict[str, Any]]:
        now = int(time.time())
        codes = self._load_setup_codes()
        cleaned: dict[str, dict[str, Any]] = {}
        for digest, entry in codes.items():
            if not isinstance(entry, dict):
                continue
            if bool(entry.get("used")):
                cleaned[str(digest)] = entry
                continue
            if int(entry.get("expires_at") or 0) <= now:
                continue
            cleaned[str(digest)] = entry
        if cleaned != codes:
            self._write_json(self.setup_codes_file(), cleaned)
        return cleaned

    def create_setup_code(self, *, ttl_seconds: int = 600) -> dict[str, Any]:
        if self.is_initialized():
            raise RuntimeError("server is already part of a cluster")
        ttl = max(60, min(1800, int(ttl_seconds or 600)))
        code = "BGL-" + secrets.token_urlsafe(18)
        digest = self._setup_code_hash(code)
        expires_at = int(time.time()) + ttl
        codes = self._cleanup_setup_codes()
        codes[digest] = {
            "hash": digest,
            "created_at": self._utcnow(),
            "expires_at": expires_at,
            "used": False,
        }
        self._write_json(self.setup_codes_file(), codes)
        return {
            "setup_code": code,
            "expires_at": expires_at,
            "ttl_seconds": ttl,
        }

    def consume_setup_code(self, setup_code: str) -> None:
        digest = self._setup_code_hash(setup_code)
        codes = self._cleanup_setup_codes()
        entry = codes.get(digest)
        if not isinstance(entry, dict):
            raise RuntimeError("invalid or expired setup code")
        if bool(entry.get("used")):
            raise RuntimeError("setup code already used")
        if int(entry.get("expires_at") or 0) <= int(time.time()):
            codes.pop(digest, None)
            self._write_json(self.setup_codes_file(), codes)
            raise RuntimeError("invalid or expired setup code")
        stored_hash = str(entry.get("hash") or digest)
        if not hmac.compare_digest(stored_hash, digest):
            raise RuntimeError("invalid or expired setup code")
        entry["used"] = True
        entry["used_at"] = self._utcnow()
        codes[digest] = entry
        self._write_json(self.setup_codes_file(), codes)

    def cluster_state(self) -> dict[str, Any]:
        return self._read_json(self.state_file(), {})

    def list_members(self) -> list[dict[str, Any]]:
        members = self._read_json(self.members_file(), [])
        return members if isinstance(members, list) else []

    def is_initialized(self) -> bool:
        state = self.cluster_state()
        return bool(state.get("cluster_id")) and bool(self.list_members())

    def local_member(self) -> dict[str, Any] | None:
        for item in self.list_members():
            if isinstance(item, dict) and item.get("local") is True:
                return item
        return None

    def remote_members(self) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        for item in self.list_members():
            if not isinstance(item, dict):
                continue
            if item.get("local") is True:
                continue
            members.append(item)
        return members

    def leader_member(self) -> dict[str, Any] | None:
        leader_node = str(self.cluster_state().get("leader_node") or "").strip()
        if not leader_node:
            return None
        for item in self.list_members():
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() == leader_node:
                return item
        return None

    def _probe_member_health(self, member: dict[str, Any], *, timeout: float = 3.0) -> bool:
        """Return True if the member's minimal liveness endpoint responds 200."""
        api_url = str(member.get("api_url") or "").strip().rstrip("/")
        if not api_url:
            return False
        health_url = self._healthz_url(api_url)
        try:
            req = urllib.request.Request(health_url, method="GET", headers={"Accept": "application/json"})
            ssl_context = ssl._create_unverified_context() if health_url.startswith("https://") else None
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
                return int(resp.status) == 200
        except Exception:
            return False

    def probe_and_update_member_statuses(self, *, timeout: float = 3.0) -> None:
        """Probe each remote member's health and persist updated status.

        Called before returning cluster status or inventory so offline nodes
        become visible within one poll cycle (≤ timeout seconds per member).
        """
        if not self.is_initialized():
            return
        members = self.list_members()
        changed = False
        for member in members:
            if not isinstance(member, dict):
                continue
            if member.get("local") is True:
                continue
            healthy = self._probe_member_health(member, timeout=timeout)
            new_status = "online" if healthy else "unreachable"
            if str(member.get("status") or "") != new_status:
                member["status"] = new_status
                changed = True
        if changed:
            self._write_json(self.members_file(), members)

    def initialize_cluster(self, *, node_name: str, api_url: str, advertise_host: str) -> dict[str, Any]:
        normalized_api_url = str(api_url or self._public_manager_url).strip().rstrip("/")
        normalized_host = str(advertise_host or self._host_from_url(normalized_api_url)).strip()
        if not normalized_api_url or not normalized_host:
            raise ValueError("api_url and advertise_host are required")

        cluster_id = self.cluster_state().get("cluster_id") or secrets.token_hex(16)
        rpc_url = self._build_rpc_url(host=normalized_host)
        self._ca_service.ensure_ca()
        certificate = self._ca_service.issue_node_certificate(
            node_name=node_name,
            subject_alt_names=self._node_sans(node_name=node_name, api_url=normalized_api_url, rpc_url=rpc_url),
        )

        state = {
            "cluster_id": cluster_id,
            "leader_node": str(node_name),
            "created_at": self._utcnow(),
            "updated_at": self._utcnow(),
        }
        member = {
            "name": str(node_name),
            "api_url": normalized_api_url,
            "rpc_url": rpc_url,
            "status": "online",
            "local": True,
        }
        self._write_json(self.state_file(), state)
        self._write_json(self.members_file(), [member])
        return {
            "cluster": state,
            "member": member,
            "certificate": certificate,
            "members": [member],
        }

    @staticmethod
    def _encode_join_token(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def decode_join_token(token: str) -> dict[str, Any]:
        text = str(token or "").strip()
        if not text:
            raise ValueError("join token is required")
        padding = "=" * (-len(text) % 4)
        decoded = base64.urlsafe_b64decode(text + padding)
        payload = json.loads(decoded.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid join token payload")
        return payload

    def create_join_token(self, *, ttl_seconds: int = 900) -> dict[str, Any]:
        local_member = self.local_member()
        if local_member is None:
            raise RuntimeError("cluster is not initialized")
        ttl = max(60, min(86400, int(ttl_seconds or 900)))
        secret = secrets.token_urlsafe(24)
        expires_at = int(time.time()) + ttl
        entry = {
            "secret": secret,
            "expires_at": expires_at,
            "created_at": self._utcnow(),
            "used": False,
        }
        tokens = self._read_json(self.join_tokens_file(), {})
        if not isinstance(tokens, dict):
            tokens = {}
        tokens[secret] = entry
        self._write_json(self.join_tokens_file(), tokens)
        token_payload = {
            "cluster_id": self.cluster_state().get("cluster_id"),
            "leader_api_url": local_member.get("api_url", ""),
            "secret": secret,
        }
        return {
            "join_token": self._encode_join_token(token_payload),
            "leader_api_url": local_member.get("api_url", ""),
            "cluster_id": self.cluster_state().get("cluster_id", ""),
            "expires_at": expires_at,
            "ttl_seconds": ttl,
        }

    def _validate_join_secret(self, secret: str) -> None:
        tokens = self._read_json(self.join_tokens_file(), {})
        if not isinstance(tokens, dict):
            raise RuntimeError("cluster join token store is unavailable")
        entry = tokens.get(secret)
        if not isinstance(entry, dict):
            raise RuntimeError("invalid cluster join token")
        if entry.get("used") is True:
            raise RuntimeError("cluster join token already used")
        if int(entry.get("expires_at") or 0) <= int(time.time()):
            tokens.pop(secret, None)
            self._write_json(self.join_tokens_file(), tokens)
            raise RuntimeError("cluster join token expired")
        entry["used"] = True
        entry["used_at"] = self._utcnow()
        tokens[secret] = entry
        self._write_json(self.join_tokens_file(), tokens)

    def accept_join_request(
        self,
        *,
        join_token: str,
        node_name: str,
        api_url: str,
        advertise_host: str,
        rpc_url: str = "",
    ) -> dict[str, Any]:
        token_payload = self.decode_join_token(join_token)
        self._validate_join_secret(str(token_payload.get("secret") or ""))
        if str(token_payload.get("cluster_id") or "") != str(self.cluster_state().get("cluster_id") or ""):
            raise RuntimeError("join token cluster_id does not match")

        normalized_api_url = str(api_url or "").strip().rstrip("/")
        normalized_host = str(advertise_host or self._host_from_url(normalized_api_url)).strip()
        normalized_rpc_url = str(rpc_url or "").strip().rstrip("/")
        if not normalized_rpc_url:
            normalized_rpc_url = self._build_rpc_url(host=normalized_host)
        certificate = self._ca_service.issue_node_certificate(
            node_name=node_name,
            subject_alt_names=self._node_sans(node_name=node_name, api_url=normalized_api_url, rpc_url=normalized_rpc_url),
        )

        members = [item for item in self.list_members() if isinstance(item, dict) and str(item.get("name") or "") != str(node_name)]
        member = {
            "name": str(node_name),
            "api_url": normalized_api_url,
            "rpc_url": normalized_rpc_url,
            "status": "online",
            "local": False,
        }
        members.append(member)
        self._write_json(self.members_file(), members)

        cert_path = Path(certificate["cert_path"])
        key_path = Path(certificate["key_path"])
        ca_cert_path = Path(certificate["ca_cert_path"])
        state = self.cluster_state()
        state["updated_at"] = self._utcnow()
        self._write_json(self.state_file(), state)
        return {
            "cluster": state,
            "member": member,
            "members": members,
            "certificate": {
                "cert_pem": cert_path.read_text(encoding="utf-8"),
                "key_pem": key_path.read_text(encoding="utf-8"),
                "ca_cert_pem": ca_cert_path.read_text(encoding="utf-8"),
            },
            "install_check_report_token": self._install_check_report_token,
        }

    def apply_join_response(self, *, node_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        cluster = payload.get("cluster") if isinstance(payload.get("cluster"), dict) else {}
        member = payload.get("member") if isinstance(payload.get("member"), dict) else {}
        members = payload.get("members") if isinstance(payload.get("members"), list) else []
        certificate = payload.get("certificate") if isinstance(payload.get("certificate"), dict) else {}
        if not cluster or not member or not members or not certificate:
            raise RuntimeError("cluster join response is incomplete")

        self._write_json(self.state_file(), cluster)
        normalized_members: list[dict[str, Any]] = []
        for item in members:
            if not isinstance(item, dict):
                continue
            current = dict(item)
            current["local"] = str(current.get("name") or "") == str(node_name)
            normalized_members.append(current)
        self._write_json(self.members_file(), normalized_members)

        issued = self._ca_service.nodes_dir() / str(node_name)
        issued.mkdir(parents=True, exist_ok=True)
        (issued / "node.crt").write_text(str(certificate.get("cert_pem") or ""), encoding="utf-8")
        (issued / "node.key").write_text(str(certificate.get("key_pem") or ""), encoding="utf-8")
        self._ca_service.ca_cert_path().write_text(str(certificate.get("ca_cert_pem") or ""), encoding="utf-8")
        try:
            (issued / "node.key").chmod(0o600)
            (issued / "node.crt").chmod(0o644)
            self._ca_service.ca_cert_path().chmod(0o644)
        except OSError:
            pass
        self._persist_install_check_report_token(str(payload.get("install_check_report_token") or "").strip())
        return {
            "cluster": cluster,
            "member": member,
            "members": normalized_members,
        }

    def _persist_install_check_report_token(self, token: str) -> None:
        normalized = str(token or "").strip()
        if not normalized or self._control_env_file is None:
            return
        path = self._control_env_file
        lines: list[str] = []
        if path.exists():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                lines = []
        updated = False
        next_lines: list[str] = []
        for raw in lines:
            if raw.startswith("BEAGLE_INSTALL_CHECK_REPORT_TOKEN="):
                next_lines.append(f'BEAGLE_INSTALL_CHECK_REPORT_TOKEN="{normalized}"')
                updated = True
            else:
                next_lines.append(raw)
        if not updated:
            next_lines.append(f'BEAGLE_INSTALL_CHECK_REPORT_TOKEN="{normalized}"')
        path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")

    def join_existing_cluster(
        self,
        *,
        join_token: str,
        node_name: str,
        api_url: str,
        advertise_host: str,
        rpc_url: str = "",
        leader_api_url: str = "",
    ) -> dict[str, Any]:
        token_payload = self.decode_join_token(join_token)
        leader_url = str(leader_api_url or token_payload.get("leader_api_url") or "").strip()
        if not leader_url:
            raise ValueError("leader api url is required")
        normalized_node = str(node_name or "").strip()
        normalized_api_url = str(api_url or self._public_manager_url).strip().rstrip("/")
        normalized_host = str(advertise_host or self._host_from_url(normalized_api_url)).strip()
        normalized_rpc_url = str(rpc_url or "").strip().rstrip("/")
        if not normalized_rpc_url:
            normalized_rpc_url = self._build_rpc_url(host=normalized_host)
        if not normalized_node:
            raise ValueError("node_name is required")
        if not normalized_api_url or not normalized_host:
            raise ValueError("api_url and advertise_host are required")

        join_response = self._post_json(
            self._api_v1_url(leader_url, "/cluster/join"),
            {
                "join_token": str(join_token or "").strip(),
                "node_name": normalized_node,
                "api_url": normalized_api_url,
                "advertise_host": normalized_host,
                "rpc_url": normalized_rpc_url,
            },
        )
        applied = self.apply_join_response(node_name=normalized_node, payload=join_response)
        return {
            "leader_api_url": leader_url,
            "join_response": {
                "cluster_id": str((join_response.get("cluster") or {}).get("cluster_id") or ""),
                "member": join_response.get("member") if isinstance(join_response.get("member"), dict) else {},
                "member_count": len(join_response.get("members") if isinstance(join_response.get("members"), list) else []),
            },
            **applied,
        }

    def join_with_setup_code(
        self,
        *,
        setup_code: str,
        join_token: str,
        node_name: str,
        api_url: str,
        advertise_host: str,
        rpc_url: str = "",
        leader_api_url: str = "",
    ) -> dict[str, Any]:
        if self.is_initialized():
            raise RuntimeError("server is already part of a cluster")
        self.consume_setup_code(setup_code)
        return self.join_existing_cluster(
            join_token=join_token,
            node_name=node_name,
            api_url=api_url,
            advertise_host=advertise_host,
            rpc_url=rpc_url,
            leader_api_url=leader_api_url,
        )

    def auto_join_server(
        self,
        *,
        setup_code: str,
        node_name: str,
        api_url: str,
        advertise_host: str,
        rpc_url: str = "",
        ssh_port: int = 22,
        timeout: float = 5.0,
        token_ttl_seconds: int = 900,
    ) -> dict[str, Any]:
        if not str(setup_code or "").strip():
            raise ValueError("setup_code is required")
        preflight = self.preflight_add_server(
            node_name=node_name,
            api_url=api_url,
            advertise_host=advertise_host,
            rpc_url=rpc_url,
            ssh_port=ssh_port,
            timeout=timeout,
            issue_join_token=False,
            token_ttl_seconds=token_ttl_seconds,
            require_rpc=False,
        )
        if not preflight.get("ok"):
            return {"ok": False, "preflight": preflight}
        token = self.create_join_token(ttl_seconds=token_ttl_seconds)
        local_member = self.local_member() or {}
        leader_api_url = str(local_member.get("api_url") or self._public_manager_url).strip()
        target_response = self._post_json(
            self._api_v1_url(str(api_url or "").strip(), "/cluster/join-with-setup-code"),
            {
                "setup_code": str(setup_code or "").strip(),
                "join_token": str(token.get("join_token") or ""),
                "leader_api_url": leader_api_url,
                "node_name": str(node_name or "").strip(),
                "api_url": str(api_url or "").strip(),
                "advertise_host": str(advertise_host or "").strip(),
                "rpc_url": str(rpc_url or "").strip(),
            },
            timeout=timeout,
        )
        return {
            "ok": True,
            "preflight": preflight,
            "target": {
                "cluster_id": str((target_response.get("cluster") or {}).get("cluster_id") or ""),
                "member": target_response.get("member") if isinstance(target_response.get("member"), dict) else {},
                "member_count": len(target_response.get("members") if isinstance(target_response.get("members"), list) else []),
            },
        }

    def status_payload(self) -> dict[str, Any]:
        state = self.cluster_state()
        members = self.list_members()
        return {
            "cluster": state,
            "members": members,
            "member_count": len(members),
            "local_member": self.local_member(),
            "initialized": self.is_initialized(),
        }

    def update_member(
        self,
        *,
        node_name: str,
        display_name: str = "",
        api_url: str = "",
        rpc_url: str = "",
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        if not self.is_initialized():
            raise RuntimeError("cluster is not initialized")
        target_name = str(node_name or "").strip()
        if not target_name:
            raise ValueError("node_name is required")
        members = self.list_members()
        updated: dict[str, Any] | None = None
        updated_members: list[dict[str, Any]] = []
        for item in members:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() == target_name:
                m = dict(item)
                if display_name:
                    m["display_name"] = str(display_name).strip()
                if api_url:
                    m["api_url"] = str(api_url).strip().rstrip("/")
                if rpc_url:
                    m["rpc_url"] = str(rpc_url).strip().rstrip("/")
                if enabled is not None:
                    m["enabled"] = bool(enabled)
                m["updated_at"] = self._utcnow()
                updated = m
                updated_members.append(m)
            else:
                updated_members.append(item)
        if updated is None:
            raise RuntimeError("cluster member not found")
        self._write_json(self.members_file(), updated_members)
        state = self.cluster_state()
        state["updated_at"] = self._utcnow()
        self._write_json(self.state_file(), state)
        return {"ok": True, "member": updated}

    def local_preflight_kvm_libvirt(self) -> dict[str, Any]:
        import os
        import subprocess

        checks: list[dict[str, Any]] = []

        # /dev/kvm
        kvm_exists = os.path.exists("/dev/kvm")
        checks.append(self._preflight_check(
            "kvm_device",
            "pass" if kvm_exists else "fail",
            "/dev/kvm exists — KVM is enabled" if kvm_exists else "/dev/kvm not found — enable Intel VT-x / AMD-V and load kvm module",
        ))

        # libvirt daemon
        libvirt_running = False
        for svc in ("libvirtd", "libvirt"):
            try:
                result = subprocess.run(
                    ["systemctl", "is-active", "--quiet", svc],
                    timeout=5,
                    check=False,
                )
                if result.returncode == 0:
                    libvirt_running = True
                    break
            except (OSError, subprocess.TimeoutExpired):
                pass
        checks.append(self._preflight_check(
            "libvirtd",
            "pass" if libvirt_running else "fail",
            "libvirtd is active" if libvirt_running else "libvirtd is not running — run: systemctl enable --now libvirtd",
        ))

        # virsh connection
        virsh_ok = False
        virsh_detail = "virsh not found"
        try:
            result = subprocess.run(
                ["virsh", "-c", "qemu:///system", "version", "--daemon"],
                timeout=5,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                virsh_ok = True
                virsh_detail = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "ok"
            else:
                virsh_detail = (result.stderr or result.stdout or "exit " + str(result.returncode)).strip()[:200]
        except (OSError, subprocess.TimeoutExpired) as exc:
            virsh_detail = str(exc)
        checks.append(self._preflight_check(
            "virsh_connection",
            "pass" if virsh_ok else "fail",
            virsh_detail,
        ))

        # control-plane socket/port
        cp_ok, cp_detail = self._tcp_check("127.0.0.1", 8006, timeout=2.0)
        checks.append(self._preflight_check(
            "control_plane_api",
            "pass" if cp_ok else "warn",
            "control-plane API reachable on 127.0.0.1:8006" if cp_ok else f"control-plane API not reachable on :8006 — {cp_detail}",
            required=False,
        ))

        required_failed = [c for c in checks if c.get("required") and c.get("status") != "pass"]
        return {
            "ok": not required_failed,
            "checks": checks,
            "summary": {
                "passed": len([c for c in checks if c.get("status") == "pass"]),
                "failed": len([c for c in checks if c.get("status") == "fail"]),
                "warnings": len([c for c in checks if c.get("status") == "warn"]),
                "skipped": len([c for c in checks if c.get("status") == "skipped"]),
            },
        }

    def remove_member(
        self,
        *,
        node_name: str,
        requester_node_name: str = "",
    ) -> dict[str, Any]:
        if not self.is_initialized():
            raise RuntimeError("cluster is not initialized")
        target_name = str(node_name or "").strip()
        if not target_name:
            raise ValueError("node_name is required")
        leader_node = str(self.cluster_state().get("leader_node") or "").strip()
        if leader_node and target_name == leader_node:
            raise RuntimeError("cluster leader cannot be removed from cluster membership")
        if requester_node_name and str(requester_node_name).strip() != target_name:
            raise RuntimeError("requester is not allowed to remove a different cluster member")

        members = self.list_members()
        kept: list[dict[str, Any]] = []
        removed_member: dict[str, Any] | None = None
        for item in members:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip() == target_name:
                removed_member = dict(item)
                continue
            kept.append(item)
        if removed_member is None:
            raise RuntimeError("cluster member not found")
        self._write_json(self.members_file(), kept)
        state = self.cluster_state()
        state["updated_at"] = self._utcnow()
        self._write_json(self.state_file(), state)
        return {
            "ok": True,
            "removed_node": target_name,
            "remaining_member_count": len(kept),
        }

    def reconcile_membership(self) -> dict[str, Any]:
        state = self.cluster_state()
        cluster_id = str(state.get("cluster_id") or "").strip()
        if not cluster_id:
            raise RuntimeError("cluster is not initialized")

        raw_members = self.list_members()
        normalized_members_by_name: dict[str, dict[str, Any]] = {}
        ordered_names: list[str] = []
        changes: list[dict[str, Any]] = []

        def _entry_name(entry: dict[str, Any]) -> str:
            return str(entry.get("name") or "").strip()

        for item in raw_members:
            if not isinstance(item, dict):
                changes.append({
                    "action": "drop_invalid_entry",
                    "reason": "member entry is not an object",
                })
                continue
            current = dict(item)
            name = _entry_name(current)
            if not name:
                changes.append({
                    "action": "drop_invalid_entry",
                    "reason": "member entry is missing a name",
                })
                continue
            existing = normalized_members_by_name.get(name)
            if existing is None:
                normalized_members_by_name[name] = current
                ordered_names.append(name)
                continue
            merged = dict(existing)
            if str(current.get("display_name") or "").strip() and not str(merged.get("display_name") or "").strip():
                merged["display_name"] = str(current.get("display_name") or "").strip()
            if str(current.get("api_url") or "").strip():
                merged["api_url"] = str(current.get("api_url") or "").strip().rstrip("/")
            if str(current.get("rpc_url") or "").strip():
                merged["rpc_url"] = str(current.get("rpc_url") or "").strip().rstrip("/")
            if str(current.get("status") or "").strip() and str(merged.get("status") or "").strip() in {"", "unknown", "offline", "unreachable"}:
                merged["status"] = str(current.get("status") or "").strip()
            if current.get("enabled") is not None:
                merged["enabled"] = bool(current.get("enabled"))
            if current.get("local") is True:
                merged["local"] = True
            normalized_members_by_name[name] = merged
            changes.append({
                "action": "merge_duplicate_member",
                "node_name": name,
            })

        leader_node = str(state.get("leader_node") or "").strip()
        local_member = None
        normalized_members = [normalized_members_by_name[name] for name in ordered_names]
        for item in normalized_members:
            if bool(item.get("local")) is True:
                local_member = item
                break

        if local_member is None and leader_node:
            for item in normalized_members:
                if _entry_name(item) == leader_node:
                    item["local"] = True
                    local_member = item
                    changes.append({
                        "action": "restore_local_flag",
                        "node_name": leader_node,
                    })
                    break

        if local_member is None and leader_node:
            local_api_url = self._public_manager_url
            local_rpc_url = self._build_rpc_url(host=self._host_from_url(local_api_url) or self._host_from_url(self._public_manager_url))
            local_member = {
                "name": leader_node,
                "api_url": local_api_url,
                "rpc_url": local_rpc_url,
                "status": "online",
                "local": True,
            }
            normalized_members.append(local_member)
            normalized_members_by_name[leader_node] = local_member
            changes.append({
                "action": "restore_missing_local_member",
                "node_name": leader_node,
            })

        local_name = _entry_name(local_member) if isinstance(local_member, dict) else ""
        if local_name:
            for item in normalized_members:
                entry_name = _entry_name(item)
                if entry_name == local_name:
                    if item.get("local") is not True:
                        item["local"] = True
                        changes.append({
                            "action": "normalize_local_member",
                            "node_name": local_name,
                        })
                    if not str(item.get("api_url") or "").strip():
                        item["api_url"] = self._public_manager_url
                        changes.append({
                            "action": "fill_missing_api_url",
                            "node_name": local_name,
                        })
                    if not str(item.get("rpc_url") or "").strip():
                        item["rpc_url"] = self._build_rpc_url(host=self._host_from_url(self._public_manager_url))
                        changes.append({
                            "action": "fill_missing_rpc_url",
                            "node_name": local_name,
                        })
                    if str(item.get("status") or "").strip() != "online":
                        item["status"] = "online"
                        changes.append({
                            "action": "normalize_status",
                            "node_name": local_name,
                            "status": "online",
                        })
                elif item.get("local") is True:
                    item["local"] = False
                    changes.append({
                        "action": "clear_spurious_local_flag",
                        "node_name": entry_name,
                    })

        normalized_members.sort(key=lambda item: (0 if item.get("local") is True else 1, str(item.get("name") or "").lower()))

        before_signature = json.dumps(raw_members, sort_keys=True, separators=(",", ":"))
        after_signature = json.dumps(normalized_members, sort_keys=True, separators=(",", ":"))
        repaired = before_signature != after_signature
        if repaired:
            self._write_json(self.members_file(), normalized_members)
            state["updated_at"] = self._utcnow()
            self._write_json(self.state_file(), state)

        return {
            "ok": True,
            "cluster_id": cluster_id,
            "leader_node": leader_node,
            "member_count_before": len([item for item in raw_members if isinstance(item, dict)]),
            "member_count_after": len(normalized_members),
            "drift_detected": repaired,
            "repaired": repaired,
            "changes": changes,
            "members": normalized_members,
        }

    def _cleanup_local_cluster_state(self, local_name: str) -> None:
        node_dir = self._ca_service.nodes_dir() / str(local_name or "").strip()
        if node_dir.exists():
            shutil.rmtree(node_dir, ignore_errors=True)
        cluster_dir = self.cluster_dir()
        if cluster_dir.exists():
            shutil.rmtree(cluster_dir, ignore_errors=True)

    def leave_local_cluster(self) -> dict[str, Any]:
        if not self.is_initialized():
            raise RuntimeError("server is not part of a cluster")
        local_member = self.local_member()
        if not isinstance(local_member, dict):
            raise RuntimeError("local cluster member not found")
        leader_node = str(self.cluster_state().get("leader_node") or "").strip()
        local_name = str(local_member.get("name") or "").strip()
        if leader_node and local_name and leader_node == local_name:
            raise RuntimeError("cluster leader cannot be detached locally")
        leader_member = self.leader_member()
        if not isinstance(leader_member, dict):
            raise RuntimeError("cluster leader member not found")
        leader_rpc_url = str(leader_member.get("rpc_url") or "").strip()
        if not leader_rpc_url:
            raise RuntimeError("cluster leader rpc_url is missing")
        if self._rpc_request is None or self._rpc_credentials is None:
            raise RuntimeError("cluster rpc leave workflow is not configured")
        credentials = self._rpc_credentials()
        if credentials is None:
            raise RuntimeError("local cluster rpc credentials are unavailable")
        cert_path, key_path, ca_cert_path = credentials
        payload = self._rpc_request(
            url=leader_rpc_url,
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
            method="cluster.member.leave",
            params={"node_name": local_name},
            request_id=f"cluster-leave-{local_name}",
            timeout=5,
            check_hostname=False,
        )
        result = payload.get("result") if isinstance(payload, dict) else {}
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise RuntimeError("cluster leader did not confirm member removal")
        self._cleanup_local_cluster_state(local_name)

        return {
            "ok": True,
            "detached_node": local_name,
            "former_leader_node": leader_node,
            "leader_confirmed": True,
        }

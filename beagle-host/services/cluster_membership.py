from __future__ import annotations

import base64
import json
import secrets
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
    ) -> None:
        self._data_dir = Path(data_dir)
        self._ca_service = ca_service
        self._public_manager_url = str(public_manager_url or "").strip().rstrip("/")
        self._rpc_port = int(rpc_port)
        self._utcnow = utcnow

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

    def _probe_member_health(self, member: dict[str, Any], *, timeout: float = 3.0) -> bool:
        """Return True if the member's API health endpoint responds 200."""
        api_url = str(member.get("api_url") or "").strip().rstrip("/")
        if not api_url:
            return False
        health_url = f"{api_url}/health"
        try:
            req = urllib.request.Request(health_url, method="GET", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
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
        secret = secrets.token_urlsafe(24)
        entry = {
            "secret": secret,
            "expires_at": int(ttl_seconds),
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
        return {
            "cluster": cluster,
            "member": member,
            "members": normalized_members,
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
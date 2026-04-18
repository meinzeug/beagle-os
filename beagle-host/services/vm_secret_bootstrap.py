"""Credential/bootstrap helpers for per-VM secret records.

This service owns the higher-level `ensure_vm_secret` flow around the
already-extracted `VmSecretStoreService`. It fills missing secret fields,
creates SSH keypairs for the USB tunnel, keeps the managed
`authorized_keys` block in sync, and backfills the Sunshine pinned
pubkey through an injected resolver.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


class VmSecretBootstrapService:
    def __init__(
        self,
        *,
        data_dir: Callable[[], Path],
        load_vm_secret: Callable[[str, int], dict[str, Any] | None],
        lookup_user: Callable[[str], Any] | None = None,
        keypair_factory: Callable[[str], tuple[str, str]] | None = None,
        public_server_name: str,
        public_stream_host: str,
        random_pin: Callable[[], str],
        random_secret: Callable[[int], str],
        resolve_sunshine_pinned_pubkey: Callable[[Any], str],
        safe_slug: Callable[..., str],
        save_vm_secret: Callable[[str, int, dict[str, Any]], dict[str, Any]],
        session_script_path: Path,
        usb_tunnel_attach_host: str,
        usb_tunnel_auth_dir: Path | None,
        usb_tunnel_auth_root: Path | None,
        usb_tunnel_base_port: int,
        usb_tunnel_home: Path | None,
        usb_tunnel_hostkey_file: Path,
        usb_tunnel_user: str,
    ) -> None:
        self._data_dir = data_dir
        self._load_vm_secret = load_vm_secret
        self._lookup_user = lookup_user or pwd.getpwnam
        self._keypair_factory = keypair_factory
        self._public_server_name = str(public_server_name or "")
        self._public_stream_host = str(public_stream_host or "")
        self._random_pin = random_pin
        self._random_secret = random_secret
        self._resolve_sunshine_pinned_pubkey = resolve_sunshine_pinned_pubkey
        self._safe_slug = safe_slug
        self._save_vm_secret = save_vm_secret
        self._session_script_path = Path(session_script_path)
        self._usb_tunnel_attach_host = str(usb_tunnel_attach_host or "")
        self._usb_tunnel_auth_dir = Path(usb_tunnel_auth_dir) if usb_tunnel_auth_dir is not None else None
        self._usb_tunnel_auth_root = Path(usb_tunnel_auth_root) if usb_tunnel_auth_root is not None else None
        self._usb_tunnel_base_port = int(usb_tunnel_base_port)
        self._usb_tunnel_home = Path(usb_tunnel_home) if usb_tunnel_home is not None else None
        self._usb_tunnel_hostkey_file = Path(usb_tunnel_hostkey_file)
        self._usb_tunnel_user = str(usb_tunnel_user or "")

    def default_usb_tunnel_port(self, vmid: int) -> int:
        candidate = self._usb_tunnel_base_port + int(vmid)
        if 1024 <= candidate <= 65535:
            return candidate
        return 43000 + (int(vmid) % 20000)

    def generate_ssh_keypair(self, comment: str) -> tuple[str, str]:
        if self._keypair_factory is not None:
            return self._keypair_factory(comment)
        with tempfile.TemporaryDirectory(prefix="beagle-usb-keygen-") as tmp_dir:
            key_path = Path(tmp_dir) / "id_ed25519"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", comment, "-f", str(key_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            private_key = key_path.read_text(encoding="utf-8")
            public_key = key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()
            return private_key, public_key

    def usb_tunnel_known_host_line(self) -> str:
        try:
            raw = self._usb_tunnel_hostkey_file.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
        parts = raw.split()
        if len(parts) < 2:
            return ""
        hostnames = [self._public_server_name]
        if self._public_stream_host and self._public_stream_host not in hostnames:
            hostnames.append(self._public_stream_host)
        host_field = ",".join(item for item in hostnames if item)
        return f"{host_field} {parts[0]} {parts[1]}" if host_field else ""

    def usb_tunnel_user_info(self) -> Any:
        return self._lookup_user(self._usb_tunnel_user)

    def usb_tunnel_home(self) -> Path:
        if self._usb_tunnel_home is not None:
            return self._usb_tunnel_home
        return Path(self.usb_tunnel_user_info().pw_dir)

    def usb_tunnel_auth_root(self) -> Path:
        if self._usb_tunnel_auth_root is not None:
            return self._usb_tunnel_auth_root
        if self._usb_tunnel_auth_dir is not None:
            return self._usb_tunnel_auth_dir.parent
        return self._data_dir().parent / "usb-tunnel" / self._usb_tunnel_user

    def usb_tunnel_auth_dir(self) -> Path:
        if self._usb_tunnel_auth_dir is not None:
            return self._usb_tunnel_auth_dir
        return self.usb_tunnel_auth_root() / "authorized_keys.d"

    def usb_tunnel_authorized_keys_path(self) -> Path:
        return self.usb_tunnel_auth_root() / "authorized_keys"

    def usb_tunnel_authorized_key_line(self, vm: Any, secret: dict[str, Any]) -> str:
        public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
        port = int(secret.get("usb_tunnel_port", 0) or 0)
        return (
            f'command="{self._session_script_path.as_posix()}",no-agent-forwarding,no-pty,no-user-rc,no-X11-forwarding,'
            f'permitlisten="{self._usb_tunnel_attach_host}:{port}" '
            f"{public_key}"
        )

    def sync_usb_tunnel_authorized_key(self, vm: Any, secret: dict[str, Any]) -> None:
        public_key = str(secret.get("usb_tunnel_public_key", "")).strip()
        port = int(secret.get("usb_tunnel_port", 0) or 0)
        if not public_key or port <= 0:
            return
        auth_root = self.usb_tunnel_auth_root()
        auth_root.mkdir(parents=True, exist_ok=True)
        auth_dir = self.usb_tunnel_auth_dir()
        auth_dir.mkdir(parents=True, exist_ok=True)
        key_line = self.usb_tunnel_authorized_key_line(vm, secret) + "\n"
        snippet_path = auth_dir / f"{self._safe_slug(vm.node, 'node')}-{int(vm.vmid)}.pub"
        snippet_path.write_text(key_line, encoding="utf-8")
        authorized_keys = self.usb_tunnel_authorized_keys_path()
        managed_lines: list[str] = []
        for item in sorted(auth_dir.glob("*.pub")):
            try:
                text = item.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if text:
                managed_lines.append(text)
        existing_text = ""
        if authorized_keys.exists():
            try:
                existing_text = authorized_keys.read_text(encoding="utf-8")
            except OSError:
                existing_text = ""
        begin_marker = "# BEGIN BEAGLE USB TUNNELS"
        end_marker = "# END BEAGLE USB TUNNELS"
        if begin_marker in existing_text and end_marker in existing_text:
            prefix, _, remainder = existing_text.partition(begin_marker)
            _, _, suffix = remainder.partition(end_marker)
            existing_text = prefix.rstrip("\n")
            suffix = suffix.lstrip("\n")
            if suffix:
                existing_text = (existing_text + "\n" + suffix).strip("\n")
        else:
            existing_text = existing_text.strip("\n")
        with authorized_keys.open("w", encoding="utf-8") as handle:
            if existing_text:
                handle.write(existing_text.rstrip("\n") + "\n")
            if managed_lines:
                handle.write(begin_marker + "\n")
                for line in managed_lines:
                    handle.write(line + "\n")
                handle.write(end_marker + "\n")
        os.chmod(auth_root, 0o700)
        os.chmod(authorized_keys, 0o600)
        os.chmod(snippet_path, 0o600)

    def ensure_vm_sunshine_pinned_pubkey(self, vm: Any, secret: dict[str, Any]) -> dict[str, Any]:
        if str(secret.get("sunshine_pinned_pubkey", "") or "").strip():
            return secret
        pin = str(self._resolve_sunshine_pinned_pubkey(vm) or "").strip()
        if not pin:
            return secret
        updated = dict(secret)
        updated["sunshine_pinned_pubkey"] = pin
        return self._save_vm_secret(vm.node, vm.vmid, updated)

    def ensure_vm_secret(self, vm: Any) -> dict[str, Any]:
        existing = self._load_vm_secret(vm.node, vm.vmid)
        if existing:
            changed = False
            if not str(existing.get("sunshine_username", "")).strip():
                existing["sunshine_username"] = f"sunshine-vm{vm.vmid}"
                changed = True
            if not str(existing.get("sunshine_password", "")).strip():
                existing["sunshine_password"] = self._random_secret(26)
                changed = True
            if not str(existing.get("sunshine_pin", "")).strip():
                existing["sunshine_pin"] = self._random_pin()
                changed = True
            if not str(existing.get("thinclient_password", "")).strip():
                existing["thinclient_password"] = self._random_secret(22)
                changed = True
            if not str(existing.get("usb_tunnel_public_key", "")).strip() or not str(existing.get("usb_tunnel_private_key", "")).strip():
                private_key, public_key = self.generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
                existing["usb_tunnel_private_key"] = private_key
                existing["usb_tunnel_public_key"] = public_key
                changed = True
            if int(existing.get("usb_tunnel_port", 0) or 0) <= 0:
                existing["usb_tunnel_port"] = self.default_usb_tunnel_port(vm.vmid)
                changed = True
            secret = self._save_vm_secret(vm.node, vm.vmid, existing) if changed else existing
            secret = self.ensure_vm_sunshine_pinned_pubkey(vm, secret)
            self.sync_usb_tunnel_authorized_key(vm, secret)
            return secret

        private_key, public_key = self.generate_ssh_keypair(f"beagle-vm{vm.vmid}-usb")
        secret = self._save_vm_secret(
            vm.node,
            vm.vmid,
            {
                "sunshine_username": f"sunshine-vm{vm.vmid}",
                "sunshine_password": self._random_secret(26),
                "sunshine_pin": self._random_pin(),
                "thinclient_password": self._random_secret(22),
                "sunshine_pinned_pubkey": "",
                "usb_tunnel_port": self.default_usb_tunnel_port(vm.vmid),
                "usb_tunnel_private_key": private_key,
                "usb_tunnel_public_key": public_key,
            },
        )
        secret = self.ensure_vm_sunshine_pinned_pubkey(vm, secret)
        self.sync_usb_tunnel_authorized_key(vm, secret)
        return secret

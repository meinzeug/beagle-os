"""Beagle Stream Server and Beagle Stream Client guest-integration helpers.

This service owns guest-side Beagle Stream Server certificate registration, Beagle Stream Server
server identity discovery, Beagle Stream Server access-ticket issuance/resolution, and
the authenticated Beagle Stream Server HTTP proxy flow. The control plane keeps thin
wrappers so handler signatures and response payloads remain stable while the
streaming-specific logic leaves the HTTP entrypoint.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse


class BeagleStreamServerIntegrationService:
    def __init__(
        self,
        *,
        build_profile: Callable[..., dict[str, Any]],
        ensure_vm_secret: Callable[[Any], dict[str, Any]],
        find_vm: Callable[[int], Any | None],
        get_vm_config: Callable[[str, int], dict[str, Any]],
        guest_exec_script_text: Callable[..., tuple[int, str, str]],
        load_beagle_stream_server_access_token: Callable[[str], dict[str, Any] | None],
        parse_description_meta: Callable[[str], dict[str, str]],
        public_manager_url: str,
        run_subprocess: Callable[..., Any] | None = None,
        safe_slug: Callable[..., str] | None = None,
        store_beagle_stream_server_access_token: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        beagle_stream_server_access_token_is_valid: Callable[[dict[str, Any] | None], bool] | None = None,
        beagle_stream_server_access_token_ttl_seconds: int = 600,
        ubuntu_beagle_default_guest_user: str = "beagle",
        ubuntu_beagle_install_state_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
    ) -> None:
        self._build_profile = build_profile
        self._ensure_vm_secret = ensure_vm_secret
        self._find_vm = find_vm
        self._get_vm_config = get_vm_config
        self._guest_exec_script_text = guest_exec_script_text
        self._load_beagle_stream_server_access_token = load_beagle_stream_server_access_token
        self._parse_description_meta = parse_description_meta
        self._public_manager_url = str(public_manager_url or "")
        self._run_subprocess = run_subprocess or subprocess.run
        self._safe_slug = safe_slug or (lambda value, default="item": default)
        self._store_beagle_stream_server_access_token = store_beagle_stream_server_access_token
        self._beagle_stream_server_access_token_is_valid = beagle_stream_server_access_token_is_valid or (lambda payload: False)
        self._beagle_stream_server_access_token_ttl_seconds = int(beagle_stream_server_access_token_ttl_seconds)
        self._ubuntu_beagle_default_guest_user = str(ubuntu_beagle_default_guest_user or "beagle")
        self._ubuntu_beagle_install_state_dir_path: Path = (
            ubuntu_beagle_install_state_dir
            if ubuntu_beagle_install_state_dir is not None
            else Path("/var/lib/beagle/beagle-manager/ubuntu-beagle-install")
        )
        self._utcnow = utcnow or (lambda: datetime.now(timezone.utc).isoformat())

    def _ubuntu_beagle_install_state_dir(self) -> Path:
        return self._ubuntu_beagle_install_state_dir_path

    def _latest_guest_user_from_install_state(self, vm: Any) -> str:
        state_dir = self._ubuntu_beagle_install_state_dir()
        if not state_dir.is_dir():
            return ""
        best_created_at = ""
        best_guest_user = ""
        for candidate in sorted(state_dir.glob("*.json")):
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if int(payload.get("vmid", 0) or 0) != int(vm.vmid):
                continue
            guest_user = str(payload.get("guest_user", "") or "").strip()
            created_at = str(payload.get("created_at", "") or "").strip()
            if guest_user and created_at >= best_created_at:
                best_created_at = created_at
                best_guest_user = guest_user
        return best_guest_user

    def _guest_user_candidates(self, vm: Any, config: dict[str, Any] | None = None) -> list[str]:
        vm_config = config if isinstance(config, dict) else self._get_vm_config(vm.node, vm.vmid)
        meta = self._parse_description_meta(vm_config.get("description", ""))
        candidates: list[str] = []
        for value in (
            meta.get("beagle-stream-server-guest-user", ""),
            meta.get("guest-user", ""),
            self._latest_guest_user_from_install_state(vm),
            vm_config.get("ciuser", ""),
            self._ubuntu_beagle_default_guest_user,
            "dennis",
            "beagle",
            "ubuntu",
        ):
            candidate = str(value or "").strip()
            if candidate and candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _detect_guest_user_on_vm(self, vm: Any, config: dict[str, Any] | None = None) -> str:
        candidates = self._guest_user_candidates(vm, config)
        script = f"""#!/usr/bin/env bash
set -euo pipefail

candidates=({" ".join(repr(candidate) for candidate in candidates)})

for candidate in "${{candidates[@]}}"; do
  if [[ -f "/home/$candidate/.config/beagle-stream-server/beagle_stream_server_state.json" || -f "/home/$candidate/.config/beagle-stream-server/sunshine_state.json" || -f "/home/$candidate/.config/beagle-stream-server/credentials/cacert.pem" || -f "/home/$candidate/.config/beagle-stream-server/beagle-stream-server.conf" || -f "/home/$candidate/.config/beagle-stream-server/sunshine.conf" ]]; then
    printf '%s\\n' "$candidate"
    exit 0
  fi
done

for state_path in /home/*/.config/beagle-stream-server/beagle_stream_server_state.json; do
  [[ -f "$state_path" ]] || continue
  basename "$(dirname "$(dirname "$(dirname "$state_path")")")"
  exit 0
done

for state_path in /home/*/.config/beagle-stream-server/sunshine_state.json; do
  [[ -f "$state_path" ]] || continue
  basename "$(dirname "$(dirname "$(dirname "$state_path")")")"
  exit 0
done

for conf_path in /home/*/.config/beagle-stream-server/beagle-stream-server.conf; do
  [[ -f "$conf_path" ]] || continue
  basename "$(dirname "$(dirname "$(dirname "$conf_path")")")"
  exit 0
done

for conf_path in /home/*/.config/beagle-stream-server/sunshine.conf; do
  [[ -f "$conf_path" ]] || continue
  basename "$(dirname "$(dirname "$(dirname "$conf_path")")")"
  exit 0
done

awk -F: '($3>=1000 && $3<65534 && $6 ~ /^\\/home\\//) {{print $1; exit}}' /etc/passwd
"""
        exitcode, stdout, _stderr = self.guest_exec_text(vm.vmid, script)
        if exitcode != 0:
            return candidates[0] if candidates else self._ubuntu_beagle_default_guest_user
        detected = str(stdout or "").strip().splitlines()
        if detected:
            first = str(detected[0] or "").strip()
            if first:
                return first
        return candidates[0] if candidates else self._ubuntu_beagle_default_guest_user

    def fetch_https_pinned_pubkey(self, url: str) -> str:
        parsed = urlparse(str(url or "").strip())
        host = str(parsed.hostname or "").strip()
        if not host:
            return ""
        port = parsed.port or 443
        try:
            cert_chain = self._run_subprocess(
                ["openssl", "s_client", "-connect", f"{host}:{int(port)}", "-servername", host],
                input="",
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
            ).stdout
            cert_match = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", cert_chain, re.S)
            if not cert_match:
                return ""
            pubkey = self._run_subprocess(
                ["openssl", "x509", "-pubkey", "-noout"],
                input=cert_match.group(0),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
            ).stdout
            der = self._run_subprocess(
                ["openssl", "pkey", "-pubin", "-outform", "der"],
                input=pubkey.encode("utf-8"),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=15,
            ).stdout
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return ""
        digest = hashlib.sha256(der).digest()
        return "sha256//" + base64.b64encode(digest).decode("ascii")

    def guest_exec_text(self, vmid: int, script: str) -> tuple[int, str, str]:
        return self._guest_exec_script_text(
            int(vmid),
            script,
            poll_attempts=300,
            poll_interval_seconds=2.0,
        )

    def beagle_stream_server_guest_user(self, vm: Any, config: dict[str, Any] | None = None) -> str:
        vm_config = config if isinstance(config, dict) else self._get_vm_config(vm.node, vm.vmid)
        candidates = self._guest_user_candidates(vm, vm_config)
        preferred = candidates[0] if candidates else self._ubuntu_beagle_default_guest_user
        if getattr(vm, "status", "") != "running":
            return preferred
        detected = self._detect_guest_user_on_vm(vm, vm_config)
        return str(detected or preferred).strip() or preferred

    def register_beagle_stream_client_certificate_on_vm(
        self,
        vm: Any,
        client_cert_pem: str,
        *,
        device_name: str,
    ) -> dict[str, Any]:
        config = self._get_vm_config(vm.node, vm.vmid)
        guest_user = self.beagle_stream_server_guest_user(vm, config)
        cert_b64 = base64.b64encode(client_cert_pem.encode("utf-8")).decode("ascii")
        safe_device_name = self._safe_slug(device_name or f"beagle-vm{vm.vmid}-client", f"beagle-vm{vm.vmid}-client")
        script = f"""#!/usr/bin/env bash
set -euo pipefail

guest_user={guest_user!r}
device_name={safe_device_name!r}
state_dir="/home/{guest_user}/.config/beagle-stream-server"
state_file="$state_dir/beagle_stream_server_state.json"
if [[ ! -f "$state_file" && -f "$state_dir/sunshine_state.json" ]]; then
  state_file="$state_dir/sunshine_state.json"
fi
cert_file="$(mktemp /tmp/beagle-cert-XXXXXX.pem)"
trap 'rm -f "$cert_file"' EXIT
cat > "$cert_file.b64" <<'__BEAGLE_CERT__'
{cert_b64}
__BEAGLE_CERT__
base64 -d "$cert_file.b64" > "$cert_file"
rm -f "$cert_file.b64"

python3 - "$state_file" "$device_name" "$cert_file" <<'PY'
import json
import tempfile
import sys
import uuid
from pathlib import Path

state_path = Path(sys.argv[1])
device_name = sys.argv[2]
cert_path = Path(sys.argv[3])


def _atomic_write_state(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(target.parent), encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=4) + "\\n")
        tmp_name = handle.name
    Path(tmp_name).replace(target)

if not state_path.exists():
    raise SystemExit(f"beagle-stream-server state file missing: {{state_path}}")

cert = cert_path.read_text(encoding="utf-8")
state = json.loads(state_path.read_text(encoding="utf-8"))
root = state.setdefault("root", {{}})
root["uniqueid"] = str(root.get("uniqueid") or "").strip() or str(uuid.uuid4()).upper()
named = root.setdefault("named_devices", [])

for entry in named:
    if entry.get("cert") == cert:
        entry["name"] = device_name
        _atomic_write_state(state_path, state)
        sys.stdout.write("updated-existing\\n")
        raise SystemExit(0)

named.append({{
    "name": device_name,
    "cert": cert,
    "uuid": str(uuid.uuid4()).upper(),
}})
_atomic_write_state(state_path, state)
sys.stdout.write("registered-new\\n")
PY

chown "$guest_user:$guest_user" "$state_file" >/dev/null 2>&1 || true
chmod 0600 "$state_file" >/dev/null 2>&1 || true

systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true
sleep 2
"""
        exitcode, stdout, stderr = self.guest_exec_text(vm.vmid, script)
        return {
            "ok": exitcode == 0,
            "guest_user": guest_user,
            "exitcode": exitcode,
            "stdout": stdout,
            "stderr": stderr,
        }

    def fetch_beagle_stream_server_identity(self, vm: Any, guest_user: str) -> dict[str, Any]:
        state_file = f"/home/{guest_user}/.config/beagle-stream-server/beagle_stream_server_state.json"
        cert_file = f"/home/{guest_user}/.config/beagle-stream-server/credentials/cacert.pem"
        conf_file = f"/home/{guest_user}/.config/beagle-stream-server/beagle-stream-server.conf"
        state_script = f"""#!/usr/bin/env bash
set -euo pipefail

state_file={state_file!r}
if [[ ! -f "$state_file" && -f "/home/{guest_user}/.config/beagle-stream-server/sunshine_state.json" ]]; then
  state_file="/home/{guest_user}/.config/beagle-stream-server/sunshine_state.json"
fi
if [[ -f "$state_file" ]]; then
  cat "$state_file"
fi
"""
        cert_script = f"""#!/usr/bin/env bash
set -euo pipefail

if [[ -f {cert_file!r} ]]; then
  cat {cert_file!r}
fi
"""
        conf_script = f"""#!/usr/bin/env bash
set -euo pipefail

conf_file={conf_file!r}
if [[ ! -f "$conf_file" && -f "/home/{guest_user}/.config/beagle-stream-server/sunshine.conf" ]]; then
  conf_file="/home/{guest_user}/.config/beagle-stream-server/sunshine.conf"
fi
if [[ -f "$conf_file" ]]; then
  cat "$conf_file"
fi
"""
        state_exitcode, state_stdout, state_stderr = self.guest_exec_text(vm.vmid, state_script)
        cert_exitcode, cert_stdout, cert_stderr = self.guest_exec_text(vm.vmid, cert_script)
        conf_exitcode, conf_stdout, conf_stderr = self.guest_exec_text(vm.vmid, conf_script)
        if state_exitcode != 0 or cert_exitcode != 0 or conf_exitcode != 0:
            return {
                "ok": False,
                "exitcode": state_exitcode or cert_exitcode or conf_exitcode,
                "stdout": "\n".join(item for item in (state_stdout, cert_stdout, conf_stdout) if item),
                "stderr": "\n".join(item for item in (state_stderr, cert_stderr, conf_stderr) if item),
                "uniqueid": "",
                "server_cert_pem": "",
                "beagle_stream_server_name": "",
                "stream_port": "",
            }
        payload: dict[str, Any] = {
            "uniqueid": "",
            "server_cert_pem": str(cert_stdout or ""),
            "beagle_stream_server_name": "",
            "stream_port": "",
        }
        try:
            state_payload = json.loads((state_stdout or "{}").strip() or "{}")
        except json.JSONDecodeError:
            state_payload = {}
        payload["uniqueid"] = str(((state_payload.get("root") or {}).get("uniqueid") or "")).strip()
        for raw_line in str(conf_stdout or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key in {"beagle_stream_server_name", "sunshine_name"}:
                payload["beagle_stream_server_name"] = value
            elif key == "port":
                payload["stream_port"] = value
        stream_port = str(payload.get("stream_port", "") or "").strip()
        if not str(payload.get("uniqueid", "") or "").strip() and stream_port:
            serverinfo_script = f"""#!/usr/bin/env bash
set -euo pipefail
curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:{stream_port}/serverinfo?uniqueid=0123456789ABCDEF"
"""
            serverinfo_exitcode, serverinfo_stdout, _serverinfo_stderr = self.guest_exec_text(vm.vmid, serverinfo_script)
            if serverinfo_exitcode == 0 and serverinfo_stdout:
                uniqueid_match = re.search(r"<uniqueid>([^<]+)</uniqueid>", serverinfo_stdout)
                if uniqueid_match is not None:
                    payload["uniqueid"] = str(uniqueid_match.group(1) or "").strip()
                if not str(payload.get("beagle_stream_server_name", "") or "").strip():
                    hostname_match = re.search(r"<hostname>([^<]+)</hostname>", serverinfo_stdout)
                    if hostname_match is not None:
                        payload["beagle_stream_server_name"] = str(hostname_match.group(1) or "").strip()
        return {
            "ok": True,
            "exitcode": 0,
            "stdout": "\n".join(item for item in (state_stdout, cert_stdout, conf_stdout) if item),
            "stderr": "\n".join(item for item in (state_stderr, cert_stderr, conf_stderr) if item),
            "uniqueid": str(payload.get("uniqueid", "") or "").strip(),
            "server_cert_pem": str(payload.get("server_cert_pem", "") or ""),
            "beagle_stream_server_name": str(payload.get("beagle_stream_server_name", "") or "").strip(),
            "stream_port": str(payload.get("stream_port", "") or "").strip(),
        }

        def prepare_virtual_display_on_vm(self, vm: Any, *, resolution: str) -> dict[str, Any]:
                configured = str(resolution or "").strip().lower()
                if not re.fullmatch(r"\d{3,5}x\d{3,5}", configured):
                        return {
                                "ok": False,
                                "error": "invalid resolution",
                                "resolution": configured,
                                "exitcode": 1,
                                "stdout": "",
                                "stderr": "invalid resolution format",
                        }

                guest_user = self.beagle_stream_server_guest_user(vm)
                script = f"""#!/usr/bin/env bash
set -euo pipefail

RESOLUTION={configured!r}
DISPLAY=:0
XAUTHORITY=/home/{guest_user}/.Xauthority
export DISPLAY XAUTHORITY

if ! xrandr --query >/dev/null 2>&1; then
    echo "xrandr unavailable for DISPLAY=:0" >&2
    exit 2
fi

output="$(xrandr --query | awk '/ connected/{{print $1; exit}}')"
if [[ -z "$output" ]]; then
    echo "no connected display output" >&2
    exit 3
fi

if xrandr --output "$output" --mode "$RESOLUTION" >/dev/null 2>&1; then
    echo "APPLIED:$output:$RESOLUTION"
    xrandr --query
    exit 0
fi

if [[ "$RESOLUTION" == "3840x2160" ]]; then
    xrandr --newmode "3840x2160_60.00" 712.75 3840 4160 4576 5312 2160 2163 2168 2237 -hsync +vsync >/dev/null 2>&1 || true
    xrandr --addmode "$output" "3840x2160_60.00" >/dev/null 2>&1 || true
    if xrandr --output "$output" --mode "3840x2160_60.00" >/dev/null 2>&1; then
        echo "APPLIED:$output:3840x2160_60.00"
        xrandr --query
        exit 0
    fi
fi

echo "failed to apply resolution on output $output" >&2
xrandr --query >/dev/null 2>&1 || true
exit 4
"""
                exitcode, stdout, stderr = self.guest_exec_text(vm.vmid, script)
                return {
                        "ok": exitcode == 0,
                        "exitcode": exitcode,
                        "resolution": configured,
                        "stdout": stdout,
                        "stderr": stderr,
                        "guest_user": guest_user,
                }

    def internal_beagle_stream_server_api_url(self, vm: Any, profile: dict[str, Any] | None = None) -> str:
        resolved_profile = profile if isinstance(profile, dict) else self._build_profile(vm)
        public_stream = resolved_profile.get("public_stream") if isinstance(resolved_profile.get("public_stream"), dict) else None
        guest_ip = str(resolved_profile.get("guest_ip", "") or "").strip()
        if public_stream:
            guest_ip = str(public_stream.get("guest_ip", "") or guest_ip).strip()
            ports = public_stream.get("ports", {}) if isinstance(public_stream.get("ports"), dict) else {}
            api_port = ports.get("beagle_stream_server_api_port")
            if guest_ip and api_port:
                return f"https://{guest_ip}:{int(api_port)}"
        base_url = str(resolved_profile.get("beagle_stream_server_api_url", "") or "")
        if guest_ip and base_url:
            parsed = urlparse(base_url)
            if parsed.scheme and parsed.port:
                return urlunparse(parsed._replace(netloc=f"{guest_ip}:{parsed.port}"))
        return base_url

    def resolve_vm_beagle_stream_server_pinned_pubkey(self, vm: Any) -> str:
        profile = self._build_profile(vm, allow_assignment=False)
        return self.fetch_https_pinned_pubkey(self.internal_beagle_stream_server_api_url(vm, profile))

    def issue_beagle_stream_server_access_token(self, vm: Any) -> tuple[str, dict[str, Any]]:
        if self._store_beagle_stream_server_access_token is None:
            raise RuntimeError("beagle-stream-server access token store is not configured")
        token = secrets.token_urlsafe(32)
        payload = {
            "vmid": vm.vmid,
            "node": vm.node,
            "issued_at": self._utcnow(),
            "expires_at": datetime.fromtimestamp(
                datetime.now(timezone.utc).timestamp() + self._beagle_stream_server_access_token_ttl_seconds,
                tz=timezone.utc,
            ).isoformat(),
        }
        self._store_beagle_stream_server_access_token(token, payload)
        return token, payload

    def beagle_stream_server_proxy_ticket_url(self, token: str) -> str:
        return f"{self._public_manager_url}/api/v1/public/beagle-stream-server/{token}/"

    def resolve_ticket_vm(self, path: str) -> tuple[Any | None, str]:
        prefix = "/api/v1/public/beagle-stream-server/"
        if not str(path).startswith(prefix):
            return None, ""
        remainder = str(path)[len(prefix):]
        parts = remainder.split("/", 1)
        token = parts[0].strip()
        if not token:
            return None, ""
        payload = self._load_beagle_stream_server_access_token(token)
        if not self._beagle_stream_server_access_token_is_valid(payload):
            return None, ""
        vm = self._find_vm(int(payload.get("vmid", -1))) if payload else None
        relative = "/" if len(parts) == 1 or not parts[1] else f"/{parts[1]}"
        return vm, relative

    def proxy_beagle_stream_server_request(
        self,
        vm: Any,
        *,
        request_path: str,
        query: str,
        method: str,
        body: bytes | None,
        request_headers: dict[str, str],
    ) -> tuple[int, dict[str, str], bytes]:
        profile = self._build_profile(vm)
        base_url = self.internal_beagle_stream_server_api_url(vm, profile).rstrip("/")
        if not base_url:
            raise RuntimeError("missing beagle-stream-server api url")
        secret = self._ensure_vm_secret(vm)
        pinned_pubkey = str(secret.get("beagle_stream_server_pinned_pubkey", "") or "")
        credential_candidates: list[tuple[str, str]] = []
        primary_user = str(secret.get("beagle_stream_server_username", "") or "")
        primary_password = str(secret.get("beagle_stream_server_password", "") or "")
        if primary_user and primary_password:
            credential_candidates.append((primary_user, primary_password))
        legacy_user = str(secret.get("sunshine_username", "") or "")
        legacy_password = str(secret.get("sunshine_password", "") or "")
        if legacy_user and legacy_password and (legacy_user, legacy_password) not in credential_candidates:
            credential_candidates.append((legacy_user, legacy_password))
        if not credential_candidates:
            raise RuntimeError("missing beagle-stream-server credentials")

        relative = "/" + str(request_path or "").lstrip("/")
        target_url = f"{base_url}{relative}"
        if query:
            target_url = f"{target_url}?{query}"

        header_file = tempfile.NamedTemporaryFile(prefix="beagle-stream-server-hdr-", delete=False)
        body_file = tempfile.NamedTemporaryFile(prefix="beagle-stream-server-body-", delete=False)
        header_file.close()
        body_file.close()
        input_name = ""
        try:
            last_error = "curl failed"
            for beagle_stream_server_user, beagle_stream_server_password in credential_candidates:
                Path(header_file.name).write_text("", encoding="utf-8")
                Path(body_file.name).write_bytes(b"")
                command = [
                    "curl",
                    "-sS",
                    "-D",
                    header_file.name,
                    "-o",
                    body_file.name,
                    "-X",
                    method.upper(),
                    "-u",
                    f"{beagle_stream_server_user}:{beagle_stream_server_password}",
                    "--connect-timeout",
                    "5",
                    "--max-time",
                    "30",
                ]
                if pinned_pubkey:
                    command.extend(["-k", "--pinnedpubkey", pinned_pubkey])
                for key in ("Content-Type", "Accept"):
                    value = str(request_headers.get(key, "") or "").strip()
                    if value:
                        command.extend(["-H", f"{key}: {value}"])
                if body is not None:
                    if not input_name:
                        input_file = tempfile.NamedTemporaryFile(prefix="beagle-stream-server-in-", delete=False)
                        input_file.write(body)
                        input_file.flush()
                        input_name = input_file.name
                        input_file.close()
                    command.extend(["--data-binary", f"@{input_name}"])
                command.append(target_url)
                result = self._run_subprocess(command, capture_output=True, text=True)
                if result.returncode != 0:
                    last_error = (result.stderr or result.stdout or "curl failed").strip()
                    continue

                raw_headers = Path(header_file.name).read_text(encoding="utf-8", errors="replace")
                raw_body = Path(body_file.name).read_bytes()
                blocks = [block for block in re.split(r"\r?\n\r?\n", raw_headers.strip()) if block.strip()]
                header_block = blocks[-1] if blocks else ""
                lines = [line for line in re.split(r"\r?\n", header_block) if line.strip()]
                if not lines or not lines[0].startswith("HTTP/"):
                    last_error = "invalid beagle-stream-server proxy response"
                    continue
                status_code = int(lines[0].split()[1])
                response_headers: dict[str, str] = {}
                for line in lines[1:]:
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    response_headers[key.strip()] = value.strip()
                if status_code == 401 and (beagle_stream_server_user, beagle_stream_server_password) != credential_candidates[-1]:
                    last_error = "beagle-stream-server proxy rejected credentials"
                    continue
                return status_code, response_headers, raw_body
            raise RuntimeError(last_error)
        finally:
            for path in (header_file.name, body_file.name, input_name):
                if path:
                    try:
                        Path(path).unlink(missing_ok=True)
                    except Exception:
                        pass

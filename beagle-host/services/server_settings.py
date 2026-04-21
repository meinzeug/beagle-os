"""Server settings service for the Beagle control plane.

Provides read/write access to server configuration:
- General (hostname, timezone, server name)
- Security (TLS/Let's Encrypt, password policy, session settings)
- Firewall (UFW rules)
- Network (interfaces, DNS)
- Services (systemd service status/restart)
- Updates (apt update check / apply)
- Backup (configuration)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

from webhook_service import WebhookService

_SETTINGS_FILE = "/etc/beagle/server-settings.json"

_MANAGED_SERVICES = [
    "beagle-control-plane",
    "beagle-usb-tunnel",
    "beagle-websockify",
    "nginx",
]

_SAFE_TIMEZONE_PATTERN = re.compile(r"^[A-Za-z_]+/[A-Za-z0-9_/+-]+$")
_SAFE_HOSTNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
_SAFE_DOMAIN_PATTERN = re.compile(
    r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z]{2,}$"
)
_SAFE_IP_PATTERN = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}$"
)
_ACME_WEBROOT = Path("/var/lib/beagle/beagle-manager/acme-webroot")
_CERTBOT_BASE_DIR = Path("/var/lib/beagle/beagle-manager/letsencrypt")
_CERTBOT_CONFIG_DIR = _CERTBOT_BASE_DIR / "config"
_CERTBOT_WORK_DIR = _CERTBOT_BASE_DIR / "work"
_CERTBOT_LOGS_DIR = _CERTBOT_BASE_DIR / "logs"





class ServerSettingsService:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        webhook_service: WebhookService | None = None,
    ) -> None:
        self._data_dir = data_dir or Path("/etc/beagle")
        self._utcnow = utcnow or (lambda: "")
        self._settings_path = self._data_dir / "server-settings.json"
        self._webhook_service = webhook_service or WebhookService(
            data_dir=self._data_dir,
            utcnow=self._utcnow,
        )

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_settings(self) -> dict[str, Any]:
        try:
            if self._settings_path.exists():
                return json.loads(self._settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _save_settings(self, data: dict[str, Any]) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._settings_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self._settings_path))
        try:
            os.chmod(str(self._settings_path), 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # General settings
    # ------------------------------------------------------------------

    def get_general(self) -> dict[str, Any]:
        settings = self._load_settings()
        hostname = _run_cmd(["hostname", "-f"], fallback=_run_cmd(["hostname"]))
        timezone = _run_cmd(["timedatectl", "show", "--property=Timezone", "--value"])
        return {
            "hostname": hostname,
            "timezone": timezone,
            "server_name": settings.get("server_name", hostname),
            "public_url": settings.get("public_url", ""),
        }

    def update_general(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._load_settings()
        errors: list[str] = []

        if "server_name" in payload:
            name = str(payload["server_name"]).strip()
            if len(name) > 128:
                errors.append("server_name too long (max 128)")
            else:
                settings["server_name"] = name

        if "public_url" in payload:
            url = str(payload["public_url"]).strip()
            if url and not url.startswith("https://"):
                errors.append("public_url must start with https://")
            elif len(url) > 256:
                errors.append("public_url too long")
            else:
                settings["public_url"] = url

        if "hostname" in payload:
            h = str(payload["hostname"]).strip()
            if not _SAFE_HOSTNAME_PATTERN.match(h):
                errors.append("invalid hostname format")
            else:
                result = _run_cmd(["hostnamectl", "set-hostname", h], check=True)
                if result is None:
                    errors.append("failed to set hostname")

        if "timezone" in payload:
            tz = str(payload["timezone"]).strip()
            if not _SAFE_TIMEZONE_PATTERN.match(tz):
                errors.append("invalid timezone format")
            else:
                result = _run_cmd(["timedatectl", "set-timezone", tz], check=True)
                if result is None:
                    errors.append("failed to set timezone")

        if errors:
            return {"ok": False, "errors": errors}

        self._save_settings(settings)
        return {"ok": True, "settings": self.get_general()}

    # ------------------------------------------------------------------
    # Security / TLS
    # ------------------------------------------------------------------

    def get_security(self) -> dict[str, Any]:
        settings = self._load_settings()
        tls_info = self._get_tls_info()
        return {
            "tls": tls_info,
            "password_policy": {
                "min_length": settings.get("password_min_length", 8),
            },
            "session": {
                "idle_timeout_minutes": settings.get("session_idle_timeout", 30),
                "max_sessions_per_user": settings.get("max_sessions_per_user", 5),
            },
        }

    def update_security(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._load_settings()
        errors: list[str] = []

        if "password_policy" in payload:
            pp = payload["password_policy"]
            if isinstance(pp, dict):
                ml = pp.get("min_length")
                if ml is not None:
                    ml = int(ml)
                    if ml < 8 or ml > 128:
                        errors.append("min_length must be between 8 and 128")
                    else:
                        settings["password_min_length"] = ml

        if "session" in payload:
            sess = payload["session"]
            if isinstance(sess, dict):
                idle = sess.get("idle_timeout_minutes")
                if idle is not None:
                    idle = int(idle)
                    if idle < 5 or idle > 1440:
                        errors.append("idle_timeout must be between 5 and 1440 minutes")
                    else:
                        settings["session_idle_timeout"] = idle
                max_s = sess.get("max_sessions_per_user")
                if max_s is not None:
                    max_s = int(max_s)
                    if max_s < 1 or max_s > 50:
                        errors.append("max_sessions must be between 1 and 50")
                    else:
                        settings["max_sessions_per_user"] = max_s

        if errors:
            return {"ok": False, "errors": errors}

        self._save_settings(settings)
        return {"ok": True, "settings": self.get_security()}

    def request_letsencrypt(self, domain: str, email: str) -> dict[str, Any]:
        domain = str(domain).strip().lower()
        email = str(email).strip().lower()

        if not _SAFE_DOMAIN_PATTERN.match(domain):
            return {"ok": False, "error": "invalid domain format"}
        if not email or "@" not in email or len(email) > 254:
            return {"ok": False, "error": "invalid email"}

        # Check certbot availability
        certbot = _which("certbot")
        if not certbot:
            return {"ok": False, "error": "certbot not installed on this server"}

        # Use --webroot authenticator so certbot never touches nginx itself.
        # The nginx config exposes /.well-known/acme-challenge/ from this dir
        # on port 80 before the HTTPS redirect, so the ACME HTTP-01 challenge
        # works without needing polkit/systemd-run or nginx plugin privileges.
        acme_webroot = _ACME_WEBROOT
        acme_webroot.mkdir(parents=True, exist_ok=True)
        _CERTBOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _CERTBOT_WORK_DIR.mkdir(parents=True, exist_ok=True)
        _CERTBOT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

        result = _run_certbot_command(
            [
                certbot, "certonly", "--webroot",
                "-w", str(acme_webroot),
                "--config-dir", str(_CERTBOT_CONFIG_DIR),
                "--work-dir", str(_CERTBOT_WORK_DIR),
                "--logs-dir", str(_CERTBOT_LOGS_DIR),
                "-d", domain,
                "--non-interactive",
                "--agree-tos",
                "-m", email,
            ],
            timeout=120,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[-500:]
            return {"ok": False, "error": f"certbot failed: {stderr}"}

        switched, switch_error = _switch_nginx_tls_to_letsencrypt(domain)
        if not switched:
            return {"ok": False, "error": f"certificate issued but nginx switch failed: {switch_error}"}

        # Update settings
        settings = self._load_settings()
        settings["tls_domain"] = domain
        settings["tls_email"] = email
        settings["tls_provider"] = "letsencrypt"
        self._save_settings(settings)

        return {"ok": True, "message": f"Certificate issued for {domain}"}

    def get_tls_status(self) -> dict[str, Any]:
        return {"ok": True, "tls": self._get_tls_info()}

    def _get_tls_info(self) -> dict[str, Any]:
        settings = self._load_settings()
        domain = settings.get("tls_domain", "")
        provider = settings.get("tls_provider", "self-signed")

        cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem" if domain else ""
        cert_exists = bool(cert_path and os.path.exists(cert_path))
        nginx_letsencrypt_active = False

        # Check nginx TLS config
        nginx_tls = False
        for nginx_path in (
            Path("/etc/nginx/sites-enabled/beagle-web-ui"),
            Path("/etc/nginx/sites-enabled/beagle-proxy.conf"),
            Path("/etc/nginx/sites-enabled/beagle-proxy"),
        ):
            try:
                nginx_conf = nginx_path.read_text()
            except OSError:
                continue
            if "ssl_certificate" in nginx_conf:
                nginx_tls = True
            if cert_path and cert_path in nginx_conf:
                nginx_letsencrypt_active = True
                break

        return {
            "domain": domain,
            "provider": provider,
            "certificate_exists": cert_exists,
            "nginx_tls_enabled": nginx_tls,
            "nginx_tls_uses_letsencrypt": nginx_letsencrypt_active,
            "email": settings.get("tls_email", ""),
        }

    # ------------------------------------------------------------------
    # Firewall
    # ------------------------------------------------------------------

    def get_firewall(self) -> dict[str, Any]:
        status = _run_cmd(["ufw", "status"])
        rules: list[dict[str, str]] = []

        if status and "Status: active" in status:
            active = True
            numbered = _run_cmd(["ufw", "status", "numbered"])
            if numbered:
                for line in numbered.splitlines():
                    m = re.match(r"\[\s*(\d+)\]\s+(.+)", line)
                    if m:
                        rules.append({"number": m.group(1), "rule": m.group(2).strip()})
        else:
            active = False

        return {
            "active": active,
            "rules": rules,
            "raw_status": (status or "")[:2000],
        }

    def update_firewall(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "")).strip()
        errors: list[str] = []

        if action == "enable":
            r = subprocess.run(
                ["ufw", "--force", "enable"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                errors.append(f"ufw enable failed: {r.stderr.strip()[:200]}")

        elif action == "disable":
            r = subprocess.run(
                ["ufw", "disable"],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode != 0:
                errors.append(f"ufw disable failed: {r.stderr.strip()[:200]}")

        elif action == "add_rule":
            rule_str = str(payload.get("rule", "")).strip()
            if not rule_str or len(rule_str) > 200:
                errors.append("invalid rule")
            else:
                # Parse simple allow/deny port rules
                parts = shlex.split(rule_str)
                if not parts:
                    errors.append("empty rule")
                else:
                    cmd = ["ufw"] + parts
                    r = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=30
                    )
                    if r.returncode != 0:
                        errors.append(f"ufw rule failed: {r.stderr.strip()[:200]}")

        elif action == "delete_rule":
            rule_num = str(payload.get("rule_number", "")).strip()
            if not rule_num.isdigit():
                errors.append("invalid rule number")
            else:
                r = subprocess.run(
                    ["ufw", "--force", "delete", rule_num],
                    capture_output=True, text=True, timeout=30
                )
                if r.returncode != 0:
                    errors.append(f"ufw delete failed: {r.stderr.strip()[:200]}")

        else:
            errors.append(f"unknown action: {action}")

        if errors:
            return {"ok": False, "errors": errors}
        return {"ok": True, "firewall": self.get_firewall()}

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def get_network(self) -> dict[str, Any]:
        interfaces: list[dict[str, Any]] = []
        raw = _run_cmd(["ip", "-j", "addr", "show"])
        if raw:
            try:
                ifaces = json.loads(raw)
                for iface in ifaces:
                    name = iface.get("ifname", "")
                    if name == "lo":
                        continue
                    addrs = []
                    for addr_info in iface.get("addr_info", []):
                        addrs.append({
                            "address": addr_info.get("local", ""),
                            "prefix": addr_info.get("prefixlen", ""),
                            "family": addr_info.get("family", ""),
                        })
                    interfaces.append({
                        "name": name,
                        "state": iface.get("operstate", "UNKNOWN"),
                        "mac": iface.get("address", ""),
                        "addresses": addrs,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        dns_servers: list[str] = []
        try:
            resolv = Path("/etc/resolv.conf").read_text()
            for line in resolv.splitlines():
                if line.strip().startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_servers.append(parts[1])
        except OSError:
            pass

        gateway = _run_cmd(["ip", "route", "show", "default"])
        default_gw = ""
        if gateway:
            m = re.search(r"default via (\S+)", gateway)
            if m:
                default_gw = m.group(1)

        return {
            "interfaces": interfaces,
            "dns_servers": dns_servers,
            "default_gateway": default_gw,
        }

    def update_network_dns(self, payload: dict[str, Any]) -> dict[str, Any]:
        servers = payload.get("dns_servers", [])
        if not isinstance(servers, list) or len(servers) > 5:
            return {"ok": False, "error": "invalid dns_servers (max 5)"}

        validated: list[str] = []
        for s in servers:
            s = str(s).strip()
            if not _SAFE_IP_PATTERN.match(s):
                return {"ok": False, "error": f"invalid DNS IP: {s}"}
            validated.append(s)

        # Write to resolved.conf.d or resolvconf
        conf_dir = Path("/etc/systemd/resolved.conf.d")
        if conf_dir.exists() or Path("/etc/systemd/resolved.conf").exists():
            conf_dir.mkdir(parents=True, exist_ok=True)
            dns_line = " ".join(validated)
            content = f"[Resolve]\nDNS={dns_line}\n"
            (conf_dir / "beagle-dns.conf").write_text(content)
            _run_cmd(["systemctl", "restart", "systemd-resolved"], check=True)
        else:
            # Fallback: write /etc/resolv.conf
            lines = [f"nameserver {s}" for s in validated]
            Path("/etc/resolv.conf").write_text("\n".join(lines) + "\n")

        return {"ok": True, "dns_servers": validated}

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def get_services(self) -> dict[str, Any]:
        services: list[dict[str, Any]] = []
        for svc in _MANAGED_SERVICES:
            status = _run_cmd(["systemctl", "is-active", svc]) or "unknown"
            enabled = _run_cmd(["systemctl", "is-enabled", svc]) or "unknown"
            services.append({
                "name": svc,
                "status": status.strip(),
                "enabled": enabled.strip(),
            })
        return {"services": services}

    def restart_service(self, name: str) -> dict[str, Any]:
        name = str(name).strip()
        if name not in _MANAGED_SERVICES:
            return {"ok": False, "error": f"service '{name}' is not managed by Beagle"}
        if not _SAFE_SERVICE_NAME.match(name):
            return {"ok": False, "error": "invalid service name"}

        r = subprocess.run(
            ["systemctl", "restart", name],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            return {"ok": False, "error": f"restart failed: {r.stderr.strip()[:200]}"}

        new_status = _run_cmd(["systemctl", "is-active", name]) or "unknown"
        return {"ok": True, "name": name, "status": new_status.strip()}

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------

    def get_updates(self) -> dict[str, Any]:
        # Check for available updates
        _run_cmd(["apt-get", "update", "-qq"], check=True)
        upgradable_raw = _run_cmd(["apt", "list", "--upgradable"])
        upgradable: list[dict[str, str]] = []
        if upgradable_raw:
            for line in upgradable_raw.splitlines():
                if "/" in line and "Listing" not in line:
                    parts = line.split("/")
                    pkg_name = parts[0] if parts else line
                    upgradable.append({"package": pkg_name, "line": line.strip()})

        return {
            "upgradable_count": len(upgradable),
            "upgradable": upgradable[:100],
        }

    def apply_updates(self) -> dict[str, Any]:
        r = subprocess.run(
            ["apt-get", "upgrade", "-y", "-qq"],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            return {"ok": False, "error": f"upgrade failed: {r.stderr.strip()[:500]}"}

        return {"ok": True, "message": "Updates applied successfully", "output": (r.stdout or "").strip()[-1000:]}

    # ------------------------------------------------------------------
    # Backup
    # ------------------------------------------------------------------

    def get_backup(self) -> dict[str, Any]:
        settings = self._load_settings()
        return {
            "enabled": settings.get("backup_enabled", False),
            "schedule": settings.get("backup_schedule", "daily"),
            "retention_days": settings.get("backup_retention_days", 7),
            "target_path": settings.get("backup_target_path", "/var/backups/beagle"),
            "last_backup": settings.get("backup_last_run", ""),
        }

    def update_backup(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._load_settings()
        errors: list[str] = []

        if "enabled" in payload:
            settings["backup_enabled"] = bool(payload["enabled"])

        if "schedule" in payload:
            sched = str(payload["schedule"]).strip()
            if sched not in {"hourly", "daily", "weekly"}:
                errors.append("schedule must be hourly, daily, or weekly")
            else:
                settings["backup_schedule"] = sched

        if "retention_days" in payload:
            ret = int(payload["retention_days"])
            if ret < 1 or ret > 365:
                errors.append("retention_days must be 1-365")
            else:
                settings["backup_retention_days"] = ret

        if "target_path" in payload:
            tp = str(payload["target_path"]).strip()
            if not tp.startswith("/"):
                errors.append("target_path must be absolute")
            elif ".." in tp:
                errors.append("target_path must not contain ..")
            elif len(tp) > 256:
                errors.append("target_path too long")
            else:
                settings["backup_target_path"] = tp

        if errors:
            return {"ok": False, "errors": errors}

        self._save_settings(settings)
        return {"ok": True, "backup": self.get_backup()}

    def run_backup_now(self) -> dict[str, Any]:
        settings = self._load_settings()
        target = settings.get("backup_target_path", "/var/backups/beagle")
        if ".." in target:
            return {"ok": False, "error": "invalid backup path"}

        Path(target).mkdir(parents=True, exist_ok=True)
        ts = self._utcnow().replace(":", "-").replace(" ", "_") if self._utcnow else "manual"

        # Backup beagle config
        archive = f"{target}/beagle-backup-{ts}.tar.gz"
        r = subprocess.run(
            ["tar", "czf", archive, "/etc/beagle"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            return {"ok": False, "error": f"backup failed: {r.stderr.strip()[:200]}"}

        settings["backup_last_run"] = self._utcnow() if self._utcnow else ts
        self._save_settings(settings)

        return {"ok": True, "archive": archive}

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    def get_webhooks(self) -> dict[str, Any]:
        return {"webhooks": self._webhook_service.list_webhooks()}

    def update_webhooks(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._webhook_service.replace_webhooks(payload.get("webhooks"))

    def send_webhook_test(self, payload: dict[str, Any]) -> dict[str, Any]:
        webhook_id = str(payload.get("id") or "").strip()
        return self._webhook_service.send_test_event(webhook_id)

    # ------------------------------------------------------------------
    # HTTP surface routing
    # ------------------------------------------------------------------

    def route_get(self, path: str) -> dict[str, Any] | None:
        if path == "/api/v1/settings/general":
            return _ok(self.get_general())
        if path == "/api/v1/settings/security":
            return _ok(self.get_security())
        if path == "/api/v1/settings/security/tls":
            return _ok(self.get_tls_status())
        if path == "/api/v1/settings/firewall":
            return _ok(self.get_firewall())
        if path == "/api/v1/settings/network":
            return _ok(self.get_network())
        if path == "/api/v1/settings/services":
            return _ok(self.get_services())
        if path == "/api/v1/settings/updates":
            return _ok(self.get_updates())
        if path == "/api/v1/settings/backup":
            return _ok(self.get_backup())
        if path == "/api/v1/settings/webhooks":
            return _ok(self.get_webhooks())
        return None

    def route_put(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if path == "/api/v1/settings/general":
            result = self.update_general(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/security":
            result = self.update_security(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/firewall":
            result = self.update_firewall(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/network/dns":
            result = self.update_network_dns(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/backup":
            result = self.update_backup(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/webhooks":
            result = self.update_webhooks(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        return None

    def route_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if path == "/api/v1/settings/security/tls/letsencrypt":
            domain = str(payload.get("domain", "")).strip()
            email = str(payload.get("email", "")).strip()
            result = self.request_letsencrypt(domain, email)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/updates/apply":
            result = self.apply_updates()
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/backup/run":
            result = self.run_backup_now()
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/webhooks/test":
            result = self.send_webhook_test(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path.startswith("/api/v1/settings/services/") and path.endswith("/restart"):
            # /api/v1/settings/services/{name}/restart
            segment = path[len("/api/v1/settings/services/"):-len("/restart")]
            if segment and _SAFE_SERVICE_NAME.match(segment):
                result = self.restart_service(segment)
                status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
                return {"kind": "json", "status": status, "payload": result}
        return None


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


def _ok(data: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "json", "status": HTTPStatus.OK, "payload": {"ok": True, **data}}


def _run_cmd(
    cmd: list[str],
    *,
    check: bool = False,
    fallback: str | None = None,
    timeout: int = 30,
) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            return None if fallback is None else fallback
        return r.stdout.strip() if r.stdout else (fallback or "")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return fallback


def _which(name: str) -> str | None:
    try:
        r = subprocess.run(["which", name], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _certbot_has_plugin(certbot: str, plugin_name: str) -> bool:
    try:
        result = subprocess.run(
            [certbot, "plugins"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    if result.returncode != 0:
        return False
    output = "\n".join([result.stdout or "", result.stderr or ""]).lower()
    return plugin_name.strip().lower() in output


def _run_certbot_command(cmd: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    # Run certbot directly. Wrapping in systemd-run --service-type=exec requires
    # interactive D-Bus/PolicyKit authentication which is unavailable from a
    # background service, causing "Interactive authentication required" errors.
    # certbot is designed to run standalone as root and needs no transient unit wrapper.
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _switch_nginx_tls_to_letsencrypt(domain: str) -> tuple[bool, str]:
    live_candidates = [
        Path(f"/etc/letsencrypt/live/{domain}"),
        _CERTBOT_CONFIG_DIR / "live" / domain,
    ]
    live_dir: Path | None = None
    for candidate in live_candidates:
        if (candidate / "fullchain.pem").exists() and (candidate / "privkey.pem").exists():
            live_dir = candidate
            break

    if live_dir is None:
        return False, "missing issued certificate files"

    cert_path = str(live_dir / "fullchain.pem")
    key_path = str(live_dir / "privkey.pem")

    candidate_files = [
        Path("/etc/nginx/sites-available/beagle-proxy.conf"),
        Path("/etc/nginx/sites-enabled/beagle-proxy.conf"),
        Path("/etc/nginx/sites-enabled/beagle-proxy"),
        Path("/etc/nginx/sites-enabled/beagle-web-ui"),
    ]

    backups: dict[Path, str] = {}
    changed = False
    seen: set[Path] = set()
    for path in candidate_files:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        try:
            original = resolved.read_text(encoding="utf-8")
        except OSError:
            continue

        updated = re.sub(
            r"(?m)^(\s*ssl_certificate\s+)\S+;",
            rf"\1{cert_path};",
            original,
        )
        updated = re.sub(
            r"(?m)^(\s*ssl_certificate_key\s+)\S+;",
            rf"\1{key_path};",
            updated,
        )

        if updated != original:
            backups[resolved] = original
            try:
                resolved.write_text(updated, encoding="utf-8")
            except OSError as exc:
                return False, f"failed writing nginx config {resolved}: {exc}"
            changed = True

    if not changed:
        return False, "no nginx ssl_certificate directives found to update"

    # Use sudo so the beagle-manager service user (NoNewPrivileges=yes) can
    # test and reload nginx. The sudoers rule is installed by install-beagle-proxy.sh.
    test = subprocess.run(["sudo", "nginx", "-t"], capture_output=True, text=True, timeout=20, check=False)
    if test.returncode != 0:
        for path, content in backups.items():
            try:
                path.write_text(content, encoding="utf-8")
            except OSError:
                pass
        stderr = (test.stderr or "").strip()[-300:]
        return False, f"nginx config test failed: {stderr}"

    reload_result = subprocess.run(["sudo", "systemctl", "reload", "nginx"], capture_output=True, text=True, timeout=20, check=False)
    if reload_result.returncode != 0:
        stderr = (reload_result.stderr or "").strip()[-300:]
        return False, f"nginx reload failed: {stderr}"

    return True, "ok"

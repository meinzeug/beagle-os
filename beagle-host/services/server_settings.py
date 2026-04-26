"""Server settings service for the Beagle control plane.

Provides read/write access to server configuration:
- General (hostname, timezone, server name)
- Security (TLS/Let's Encrypt, password policy, session settings)
- Firewall (UFW rules)
- Network (interfaces, DNS)
- Services (systemd service status/restart)
- Updates (apt update check / apply + repo auto-update)
- Backup (configuration)
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import socket
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
    "beagle-artifacts-refresh",
    "beagle-artifacts-refresh.timer",
    "beagle-artifacts-watchdog",
    "beagle-artifacts-watchdog.timer",
    "beagle-repo-auto-update",
    "beagle-repo-auto-update.timer",
    "nginx",
]

_REQUIRED_ARTIFACTS = [
    "beagle-downloads-status.json",
    "pve-thin-client-live-usb-latest.sh",
    "pve-thin-client-live-usb-latest.ps1",
    "pve-thin-client-usb-installer-latest.sh",
    "pve-thin-client-usb-installer-latest.ps1",
    "pve-thin-client-usb-payload-latest.tar.gz",
    "pve-thin-client-usb-bootstrap-latest.tar.gz",
    "beagle-os-installer-amd64.iso",
    "beagle-os-server-installer-amd64.iso",
    "Debian-1201-bookworm-amd64-beagle-server.tar.gz",
]

_PUBLIC_THIN_CLIENT_LATEST_ARTIFACTS = [
    "pve-thin-client-usb-installer-latest.sh",
    "pve-thin-client-usb-installer-latest.ps1",
    "pve-thin-client-live-usb-latest.sh",
    "pve-thin-client-live-usb-latest.ps1",
    "pve-thin-client-usb-payload-latest.tar.gz",
    "pve-thin-client-usb-bootstrap-latest.tar.gz",
]

_SAFE_TIMEZONE_PATTERN = re.compile(r"^[A-Za-z_]+/[A-Za-z0-9_/+-]+$")
_SAFE_HOSTNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$")
_SAFE_DOMAIN_PATTERN = re.compile(
    r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z]{2,}$"
)
_SAFE_IP_PATTERN = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}$"
)
_SAFE_SERVICE_NAME = re.compile(r"^[A-Za-z0-9_.@-]+$")
_ACME_WEBROOT = Path("/var/lib/beagle/acme-webroot")
_CERTBOT_BASE_DIR = Path("/var/lib/beagle/beagle-manager/letsencrypt")
_CERTBOT_CONFIG_DIR = _CERTBOT_BASE_DIR / "config"
_CERTBOT_WORK_DIR = _CERTBOT_BASE_DIR / "work"
_CERTBOT_LOGS_DIR = _CERTBOT_BASE_DIR / "logs"
_ARTIFACT_WATCHDOG_STATUS_FILE = Path("/var/lib/beagle/artifact-watchdog-status.json")
_ARTIFACT_WATCHDOG_RULE_FILE = Path("/etc/polkit-1/rules.d/49-beagle-artifacts-watchdog.rules")
_REPO_AUTO_UPDATE_STATUS_FILE = Path("/var/lib/beagle/repo-auto-update-status.json")
_REPO_AUTO_UPDATE_RULE_FILE = Path("/etc/polkit-1/rules.d/49-beagle-repo-auto-update.rules")
_DEFAULT_REPO_AUTO_UPDATE_URL = "https://github.com/meinzeug/beagle-os.git"
_DEFAULT_REPO_AUTO_UPDATE_BRANCH = "main"





class ServerSettingsService:
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        install_dir: Path | None = None,
        utcnow: Callable[[], str] | None = None,
        webhook_service: WebhookService | None = None,
    ) -> None:
        self._data_dir = data_dir or Path("/etc/beagle")
        self._install_dir = install_dir or Path(os.environ.get("BEAGLE_INSTALL_DIR", "/opt/beagle"))
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

        if _domain_has_ipv6_records(domain) and not _host_has_global_ipv6():
            return {
                "ok": False,
                "error": (
                    "domain has an AAAA/IPv6 DNS record, but this server has no global IPv6 address. "
                    "Remove the AAAA record or configure public IPv6 before requesting a Let's Encrypt certificate."
                ),
            }

        # Use --webroot authenticator so certbot never touches nginx itself.
        # The nginx config exposes /.well-known/acme-challenge/ from this dir
        # on port 80 before the HTTPS redirect, so the ACME HTTP-01 challenge
        # works without needing polkit/systemd-run or nginx plugin privileges.
        acme_webroot = _ACME_WEBROOT
        acme_webroot.mkdir(parents=True, exist_ok=True)
        challenge_dir = acme_webroot / ".well-known" / "acme-challenge"
        challenge_dir.mkdir(parents=True, exist_ok=True)
        for path in (acme_webroot, acme_webroot / ".well-known", challenge_dir):
            path.chmod(0o755)
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
            "source": "apt",
            "repo_auto_update": self.get_repo_auto_update(),
        }

    def get_repo_auto_update(self) -> dict[str, Any]:
        settings = self._load_settings()
        config = {
            "enabled": bool(settings.get("repo_auto_update_enabled", False)),
            "repo_url": str(settings.get("repo_auto_update_repo_url") or _DEFAULT_REPO_AUTO_UPDATE_URL).strip() or _DEFAULT_REPO_AUTO_UPDATE_URL,
            "branch": str(settings.get("repo_auto_update_branch") or _DEFAULT_REPO_AUTO_UPDATE_BRANCH).strip() or _DEFAULT_REPO_AUTO_UPDATE_BRANCH,
            "interval_minutes": int(settings.get("repo_auto_update_interval_minutes", 15) or 15),
        }
        status: dict[str, Any] = {}
        try:
            if _REPO_AUTO_UPDATE_STATUS_FILE.is_file():
                loaded = json.loads(_REPO_AUTO_UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    status.update(loaded)
        except (OSError, json.JSONDecodeError):
            status = {"error": "unreadable"}

        status.setdefault("state", "disabled" if not config["enabled"] else "unknown")
        status.setdefault("checked_at", "")
        status.setdefault("last_update_at", "")
        status.setdefault("current_commit", "")
        status.setdefault("remote_commit", "")
        status.setdefault("update_available", False)
        status.setdefault("message", "Repo-Auto-Update ist deaktiviert." if not config["enabled"] else "Noch nicht geprueft.")

        return {
            "config": config,
            "status": status,
            "services": {
                "beagle-repo-auto-update.service": _run_cmd(["systemctl", "is-active", "beagle-repo-auto-update.service"], fallback="unknown") or "unknown",
                "beagle-repo-auto-update.timer": _run_cmd(["systemctl", "is-active", "beagle-repo-auto-update.timer"], fallback="unknown") or "unknown",
            },
            "start_capable": _can_start_systemd_unit("beagle-repo-auto-update.service", rule_file=_REPO_AUTO_UPDATE_RULE_FILE),
        }

    def update_repo_auto_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._load_settings()
        errors: list[str] = []

        enabled = payload.get("enabled")
        if enabled is not None:
            settings["repo_auto_update_enabled"] = bool(enabled)

        repo_url = payload.get("repo_url")
        if repo_url is not None:
            repo_url = str(repo_url).strip()
            if not repo_url.startswith("https://github.com/") or not repo_url.endswith(".git"):
                errors.append("repo_url must point to a GitHub HTTPS repository and end with .git")
            else:
                settings["repo_auto_update_repo_url"] = repo_url

        branch = payload.get("branch")
        if branch is not None:
            branch = str(branch).strip()
            if not re.fullmatch(r"[A-Za-z0-9._/-]{1,120}", branch or ""):
                errors.append("branch contains invalid characters")
            else:
                settings["repo_auto_update_branch"] = branch

        interval_minutes = payload.get("interval_minutes")
        if interval_minutes is not None:
            try:
                interval = int(interval_minutes)
            except (TypeError, ValueError):
                interval = 0
            if interval < 5 or interval > 1440:
                errors.append("interval_minutes must be between 5 and 1440")
            else:
                settings["repo_auto_update_interval_minutes"] = interval

        if errors:
            return {"ok": False, "errors": errors}

        self._save_settings(settings)
        return {"ok": True, "repo_auto_update": self.get_repo_auto_update()}

    def run_repo_auto_update(self) -> dict[str, Any]:
        r = _run_systemctl_privileged(["--no-block", "start", "beagle-repo-auto-update.service"], timeout=30)
        if r.returncode != 0:
            return {"ok": False, "error": f"repo auto update start failed: {r.stderr.strip()[:300]}"}
        return {"ok": True, "repo_auto_update": self.get_repo_auto_update()}

    def get_artifacts(self) -> dict[str, Any]:
        dist_dir = self._install_dir / "dist"
        status_file = dist_dir / "beagle-downloads-status.json"
        refresh_status_file = Path("/var/lib/beagle/refresh.status.json")
        version = ""
        try:
            version = (self._install_dir / "VERSION").read_text(encoding="utf-8").strip()
        except OSError:
            version = ""
        artifacts: list[dict[str, Any]] = []
        for rel_path in _REQUIRED_ARTIFACTS:
            path = dist_dir / rel_path
            exists = path.is_file()
            size = 0
            mtime = None
            try:
                if exists:
                    stat = path.stat()
                    size = int(stat.st_size)
                    mtime = int(stat.st_mtime)
            except OSError:
                exists = False
            artifacts.append({
                "path": rel_path,
                "exists": exists,
                "size_bytes": size,
                "mtime_epoch": mtime,
            })

        status_json: dict[str, Any] = {}
        refresh_status: dict[str, Any] = {}
        for path, target in ((status_file, status_json), (refresh_status_file, refresh_status)):
            try:
                if path.is_file():
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        target.update(loaded)
            except (OSError, json.JSONDecodeError):
                target["error"] = "unreadable"

        missing = [item["path"] for item in artifacts if not item["exists"]]
        refresh_service = _run_cmd(["systemctl", "is-active", "beagle-artifacts-refresh.service"]) or "unknown"
        refresh_timer = _run_cmd(["systemctl", "is-active", "beagle-artifacts-refresh.timer"]) or "unknown"
        refresh_state = str(refresh_status.get("status") or "").strip().lower()
        running_refresh = refresh_state in {"queued", "running"} or refresh_service.strip() == "active"
        preflight = self._artifact_preflight(dist_dir=dist_dir, running_refresh=running_refresh)
        publish_gate = self._artifact_publish_gate(dist_dir=dist_dir, version=version)
        watchdog = self.get_artifact_watchdog(status_json=status_json, refresh_status=refresh_status)
        status_url = str(status_json.get("status_url") or "").strip()
        downloads_path = str(status_json.get("downloads_path") or "/beagle-downloads").strip() or "/beagle-downloads"
        if not downloads_path.startswith("/"):
            downloads_path = "/" + downloads_path
        return {
            "dist_dir": str(dist_dir),
            "status_file": str(status_file),
            "refresh_status_file": str(refresh_status_file),
            "version": version or str(status_json.get("version") or "").strip(),
            "status": status_json,
            "refresh_status": refresh_status,
            "artifacts": artifacts,
            "missing": missing,
            "ready": not missing and bool(status_json),
            "running_refresh": running_refresh,
            "preflight": preflight,
            "publish_gate": publish_gate,
            "watchdog": watchdog,
            "links": {
                "status_json": status_url or f"{downloads_path.rstrip('/')}/beagle-downloads-status.json",
                "downloads_index": f"{downloads_path.rstrip('/')}/beagle-downloads-index.html",
            },
            "services": {
                "beagle-artifacts-refresh.service": refresh_service.strip(),
                "beagle-artifacts-refresh.timer": refresh_timer.strip(),
                "beagle-artifacts-watchdog.service": _run_cmd(["systemctl", "is-active", "beagle-artifacts-watchdog.service"], fallback="unknown") or "unknown",
                "beagle-artifacts-watchdog.timer": _run_cmd(["systemctl", "is-active", "beagle-artifacts-watchdog.timer"], fallback="unknown") or "unknown",
            },
        }

    def start_artifact_refresh(self) -> dict[str, Any]:
        self._write_refresh_status({
            "status": "queued",
            "step": "systemd",
            "progress": 1,
            "message": "Refresh-Service wird gestartet ...",
            "last_result": "queued",
        })
        r = _run_systemctl_privileged(["--no-block", "start", "beagle-artifacts-refresh.service"], timeout=30)
        if r.returncode != 0:
            self._write_refresh_status({
                "status": "failed",
                "step": "systemd",
                "progress": 0,
                "message": "Refresh-Service konnte nicht gestartet werden.",
                "last_result": "failed",
                "error_excerpt": (r.stderr or r.stdout or "").strip()[:400],
            })
            return {"ok": False, "error": f"artifact refresh start failed: {r.stderr.strip()[:300]}"}
        return {"ok": True, "artifacts": self.get_artifacts()}

    def get_artifact_watchdog(self, *, status_json: dict[str, Any] | None = None, refresh_status: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self._load_settings()
        config = {
            "enabled": bool(settings.get("artifact_watchdog_enabled", False)),
            "max_age_hours": int(settings.get("artifact_watchdog_max_age_hours", 24) or 24),
            "auto_repair": bool(settings.get("artifact_watchdog_auto_repair", True)),
        }
        status: dict[str, Any] = {}
        try:
            if _ARTIFACT_WATCHDOG_STATUS_FILE.is_file():
                loaded = json.loads(_ARTIFACT_WATCHDOG_STATUS_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    status.update(loaded)
        except (OSError, json.JSONDecodeError):
            status = {"error": "unreadable"}
        status.setdefault("state", "disabled" if not config["enabled"] else "unknown")
        status.setdefault("checked_at", "")
        status.setdefault("artifact_age_seconds", None)
        status.setdefault("reaction", "none")
        status.setdefault("findings", [])
        status.setdefault("message", "Watchdog noch nicht gelaufen." if config["enabled"] else "Watchdog ist deaktiviert.")
        return {
            "config": config,
            "status": status,
            "start_capable": _can_start_systemd_unit("beagle-artifacts-watchdog.service", rule_file=_ARTIFACT_WATCHDOG_RULE_FILE),
        }

    def update_artifact_watchdog(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._load_settings()
        errors: list[str] = []

        enabled = payload.get("enabled")
        if enabled is not None:
            settings["artifact_watchdog_enabled"] = bool(enabled)

        max_age_hours = payload.get("max_age_hours")
        if max_age_hours is not None:
            try:
                value = int(max_age_hours)
            except (TypeError, ValueError):
                value = 0
            if value < 1 or value > 168:
                errors.append("max_age_hours must be between 1 and 168")
            else:
                settings["artifact_watchdog_max_age_hours"] = value

        auto_repair = payload.get("auto_repair")
        if auto_repair is not None:
            settings["artifact_watchdog_auto_repair"] = bool(auto_repair)

        if errors:
            return {"ok": False, "errors": errors}

        self._save_settings(settings)
        return {"ok": True, "watchdog": self.get_artifact_watchdog()}

    def run_artifact_watchdog(self) -> dict[str, Any]:
        r = _run_systemctl_privileged(["--no-block", "start", "beagle-artifacts-watchdog.service"], timeout=30)
        if r.returncode != 0:
            return {"ok": False, "error": f"artifact watchdog start failed: {r.stderr.strip()[:300]}"}
        return {"ok": True, "watchdog": self.get_artifact_watchdog()}

    def _artifact_preflight(self, *, dist_dir: Path, running_refresh: bool) -> dict[str, Any]:
        free_bytes = 0
        total_bytes = 0
        try:
            usage = shutil.disk_usage(dist_dir if dist_dir.exists() else self._install_dir)
            free_bytes = int(usage.free)
            total_bytes = int(usage.total)
        except OSError:
            pass

        required_tools = [
            "zip",
            "tar",
            "sha256sum",
            "python3",
            "node",
            "npm",
            "systemctl",
        ]
        optional_build_tools = [
            "lb",
            "xorriso",
            "mksquashfs",
            "grub-mkstandalone",
        ]
        missing_required = [tool for tool in required_tools if _which(tool) is None]
        missing_optional = [tool for tool in optional_build_tools if _which(tool) is None]
        service_present = bool(_run_cmd(["systemctl", "show", "-p", "FragmentPath", "beagle-artifacts-refresh.service"]))
        return {
            "free_bytes": free_bytes,
            "total_bytes": total_bytes,
            "running_refresh": running_refresh,
            "service_unit_present": service_present,
            "systemd_start_capable": _can_start_artifact_refresh_service(),
            "missing_required_tools": missing_required,
            "missing_optional_build_tools": missing_optional,
            "ok": not running_refresh and service_present and not missing_required and _can_start_artifact_refresh_service(),
        }

    def _artifact_publish_gate(self, *, dist_dir: Path, version: str) -> dict[str, Any]:
        version = str(version or "").strip()
        versioned = []
        if version:
            versioned = [
                f"pve-thin-client-usb-installer-v{version}.sh",
                f"pve-thin-client-usb-installer-v{version}.ps1",
                f"pve-thin-client-live-usb-v{version}.sh",
                f"pve-thin-client-live-usb-v{version}.ps1",
                f"pve-thin-client-usb-payload-v{version}.tar.gz",
                f"pve-thin-client-usb-bootstrap-v{version}.tar.gz",
            ]
        missing_latest = [name for name in _PUBLIC_THIN_CLIENT_LATEST_ARTIFACTS if not (dist_dir / name).is_file()]
        missing_versioned = [name for name in versioned if not (dist_dir / name).is_file()]
        return {
            "public_ready": not missing_latest and not missing_versioned,
            "missing_latest": missing_latest,
            "missing_versioned": missing_versioned,
            "latest_expected": list(_PUBLIC_THIN_CLIENT_LATEST_ARTIFACTS),
            "versioned_expected": versioned,
        }

    def _write_refresh_status(self, payload: dict[str, Any]) -> None:
        path = Path("/var/lib/beagle/refresh.status.json")
        existing: dict[str, Any] = {}
        try:
            if path.is_file():
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing.update(loaded)
        except (OSError, json.JSONDecodeError):
            existing = {}

        merged = dict(existing)
        merged.update(payload)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        except OSError:
            return

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
        if path == "/api/v1/settings/artifacts":
            return _ok(self.get_artifacts())
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
        if path == "/api/v1/settings/artifacts/watchdog":
            result = self.update_artifact_watchdog(payload)
            status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/updates/repo-auto":
            result = self.update_repo_auto_update(payload)
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
        if path == "/api/v1/settings/updates/repo-auto/check":
            result = self.run_repo_auto_update()
            status = HTTPStatus.ACCEPTED if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/artifacts/refresh":
            result = self.start_artifact_refresh()
            status = HTTPStatus.ACCEPTED if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
            return {"kind": "json", "status": status, "payload": result}
        if path == "/api/v1/settings/artifacts/watchdog/check":
            result = self.run_artifact_watchdog()
            status = HTTPStatus.ACCEPTED if result.get("ok") else HTTPStatus.INTERNAL_SERVER_ERROR
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


def _run_systemctl_privileged(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    command = ["systemctl", *args]
    direct = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if direct.returncode == 0 or os.geteuid() == 0:
        return direct
    if _which("sudo"):
        return subprocess.run(["sudo", "-n", *command], capture_output=True, text=True, timeout=timeout)
    return direct


def _can_start_artifact_refresh_service() -> bool:
    return _can_start_systemd_unit("beagle-artifacts-refresh.service", rule_file=Path("/etc/polkit-1/rules.d/49-beagle-artifacts-refresh.rules"))


def _can_start_systemd_unit(unit_name: str, *, rule_file: Path | None = None) -> bool:
    if os.geteuid() == 0:
        return True
    try:
        if rule_file and rule_file.is_file():
            return True
    except OSError:
        pass
    if not _which("sudo"):
        return False
    try:
        result = subprocess.run(
            ["sudo", "-n", "systemctl", "show", "-p", "Id", unit_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _domain_has_ipv6_records(domain: str) -> bool:
    try:
        return bool(socket.getaddrinfo(domain, None, socket.AF_INET6, socket.SOCK_STREAM))
    except socket.gaierror:
        return False


def _host_has_global_ipv6() -> bool:
    try:
        result = subprocess.run(
            ["ip", "-6", "-o", "addr", "show", "scope", "global"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    return bool((result.stdout or "").strip())


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
        preexec_fn=lambda: os.umask(0o002),
    )


def _switch_nginx_tls_to_letsencrypt(domain: str) -> tuple[bool, str]:
    live_candidates = [
        Path(f"/etc/letsencrypt/live/{domain}"),
        _CERTBOT_CONFIG_DIR / "live" / domain,
    ]
    live_dir: Path | None = None
    for candidate in live_candidates:
        try:
            if (candidate / "fullchain.pem").exists() and (candidate / "privkey.pem").exists():
                live_dir = candidate
                break
        except OSError:
            continue

    if live_dir is None:
        return False, "missing issued certificate files"

    source_cert = live_dir / "fullchain.pem"
    source_key = live_dir / "privkey.pem"
    target_dir = Path("/etc/beagle/tls")
    target_cert = target_dir / "beagle-proxy.crt"
    target_key = target_dir / "beagle-proxy.key"

    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_cert.write_bytes(source_cert.read_bytes())
        target_key.write_bytes(source_key.read_bytes())
        os.chmod(target_cert, 0o644)
        os.chmod(target_key, 0o600)
    except OSError as exc:
        return False, f"failed updating Beagle TLS files: {exc}"

    pid_candidates = [Path("/run/nginx.pid"), Path("/var/run/nginx.pid")]
    nginx_pid: int | None = None
    for pid_path in pid_candidates:
        try:
            if pid_path.exists():
                nginx_pid = int((pid_path.read_text(encoding="utf-8") or "").strip())
                break
        except (OSError, ValueError):
            continue
    if nginx_pid is None:
        return False, "nginx pid file not found"

    try:
        os.kill(nginx_pid, signal.SIGHUP)
    except OSError as exc:
        return False, f"nginx reload failed: {exc}"

    return True, "ok"

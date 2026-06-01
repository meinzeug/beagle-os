import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

SERVER_SETTINGS_PATH = SERVICES_DIR / "server_settings.py"
SPEC = importlib.util.spec_from_file_location("beagle_server_settings", SERVER_SETTINGS_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
ServerSettingsService = MODULE.ServerSettingsService


class ServerSettingsLetsEncryptTests(unittest.TestCase):
    def make_service(self) -> ServerSettingsService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return ServerSettingsService(data_dir=Path(temp_dir.name))

    def test_request_letsencrypt_requires_certbot(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_which", return_value=None):
            result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "certbot not installed on this server")

    def test_request_letsencrypt_uses_webroot_authenticator(self):
        service = self.make_service()

        captured = []

        def fake_run_certbot(cmd, *, timeout):
            captured.append(cmd)
            proc = mock.Mock()
            proc.returncode = 0
            proc.stdout = "Successfully received certificate."
            proc.stderr = ""
            return proc

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_webroot = Path(tmpdir) / "acme-webroot"
            fake_certbot_config = Path(tmpdir) / "certbot" / "config"
            fake_certbot_work = Path(tmpdir) / "certbot" / "work"
            fake_certbot_logs = Path(tmpdir) / "certbot" / "logs"
            with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
                  mock.patch.object(MODULE, "_domain_has_ipv6_records", return_value=False), \
                  mock.patch.object(MODULE, "_host_has_global_ipv6", return_value=False), \
                 mock.patch.object(MODULE, "_ACME_WEBROOT", fake_webroot), \
                 mock.patch.object(MODULE, "_CERTBOT_CONFIG_DIR", fake_certbot_config), \
                 mock.patch.object(MODULE, "_CERTBOT_WORK_DIR", fake_certbot_work), \
                 mock.patch.object(MODULE, "_CERTBOT_LOGS_DIR", fake_certbot_logs), \
                 mock.patch.object(MODULE, "_run_certbot_command", side_effect=fake_run_certbot), \
                 mock.patch.object(MODULE, "_switch_nginx_tls_to_letsencrypt", return_value=(True, "ok")):
                result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertTrue(result["ok"], result)
        self.assertIn("--webroot", captured[0])
        self.assertNotIn("--nginx", captured[0])
        self.assertIn("--config-dir", captured[0])
        self.assertIn("--work-dir", captured[0])
        self.assertIn("--logs-dir", captured[0])

    def test_request_letsencrypt_rejects_aaaa_without_global_ipv6(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_which", return_value="/usr/bin/certbot"), \
             mock.patch.object(MODULE, "_domain_has_ipv6_records", return_value=True), \
             mock.patch.object(MODULE, "_host_has_global_ipv6", return_value=False):
            result = service.request_letsencrypt("srv1.beagle-os.com", "ops@beagle-os.com")

        self.assertFalse(result["ok"])
        self.assertIn("AAAA/IPv6 DNS record", result["error"])

    def test_switch_nginx_tls_to_letsencrypt_replaces_beagle_tls_files_atomically(self):
        domain = "srv1.beagle-os.com"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            live_dir = tmp_root / "certbot" / "config" / "live" / domain
            live_dir.mkdir(parents=True)
            (live_dir / "fullchain.pem").write_text("new-cert", encoding="utf-8")
            (live_dir / "privkey.pem").write_text("new-key", encoding="utf-8")

            target_dir = tmp_root / "beagle-tls"
            target_dir.mkdir()
            (target_dir / "beagle-proxy.crt").write_text("old-cert", encoding="utf-8")
            (target_dir / "beagle-proxy.key").write_text("old-key", encoding="utf-8")

            pid_file = tmp_root / "nginx.pid"
            pid_file.write_text("4242\n", encoding="utf-8")

            with mock.patch.object(MODULE, "_CERTBOT_CONFIG_DIR", tmp_root / "certbot" / "config"), \
                 mock.patch.object(MODULE, "_BEAGLE_TLS_DIR", target_dir), \
                 mock.patch.object(MODULE, "_BEAGLE_TLS_CERT_PATH", target_dir / "beagle-proxy.crt"), \
                 mock.patch.object(MODULE, "_BEAGLE_TLS_KEY_PATH", target_dir / "beagle-proxy.key"), \
                 mock.patch.object(MODULE, "_NGINX_PID_CANDIDATES", [pid_file]), \
                 mock.patch.object(MODULE.os, "kill") as kill:
                ok, message = MODULE._switch_nginx_tls_to_letsencrypt(domain)

                self.assertTrue(ok, message)
                self.assertEqual(message, "ok")
                self.assertEqual((target_dir / "beagle-proxy.crt").read_text(encoding="utf-8"), "new-cert")
                self.assertEqual((target_dir / "beagle-proxy.key").read_text(encoding="utf-8"), "new-key")
                self.assertFalse(any(path.name.startswith(".beagle-proxy.") for path in target_dir.iterdir()))
                kill.assert_called_once_with(4242, MODULE.signal.SIGHUP)

    def test_get_tls_info_counts_installed_beagle_tls_copy(self):
        domain = "srv1.beagle-os.com"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            data_dir = tmp_root / "data"
            target_dir = tmp_root / "beagle-tls"
            target_dir.mkdir()
            cert_path = target_dir / "beagle-proxy.crt"
            key_path = target_dir / "beagle-proxy.key"
            cert_path.write_text("cert", encoding="utf-8")
            key_path.write_text("key", encoding="utf-8")
            nginx_conf = tmp_root / "beagle-proxy.conf"
            nginx_conf.write_text(f"ssl_certificate {cert_path};\nssl_certificate_key {key_path};\n", encoding="utf-8")

            service = ServerSettingsService(data_dir=data_dir)
            settings = service._load_settings()
            settings["tls_domain"] = domain
            settings["tls_email"] = "ops@beagle-os.com"
            settings["tls_provider"] = "letsencrypt"
            service._save_settings(settings)

            with mock.patch.object(MODULE, "_BEAGLE_TLS_CERT_PATH", cert_path), \
                 mock.patch.object(MODULE, "_BEAGLE_TLS_KEY_PATH", key_path), \
                 mock.patch.object(MODULE, "_NGINX_TLS_CONFIG_CANDIDATES", [nginx_conf]):
                tls = service.get_tls_status()["tls"]

        self.assertTrue(tls["certificate_exists"])
        self.assertTrue(tls["beagle_tls_certificate_exists"])
        self.assertTrue(tls["beagle_tls_key_exists"])
        self.assertTrue(tls["nginx_tls_enabled"])
        self.assertTrue(tls["nginx_tls_uses_letsencrypt"])
        self.assertEqual(tls["certificate_path"], str(cert_path))

    def test_route_post_tls_letsencrypt_returns_bad_request_for_invalid_domain(self):
        service = self.make_service()

        response = service.route_post(
            "/api/v1/settings/security/tls/letsencrypt",
            {"domain": "invalid_domain", "email": "ops@beagle-os.com"},
        )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 400)
        self.assertFalse(response["payload"]["ok"])
        self.assertEqual(response["payload"]["error"], "invalid domain format")

    def test_route_post_tls_letsencrypt_returns_ok_for_successful_request(self):
        service = self.make_service()

        with mock.patch.object(
            service,
            "request_letsencrypt",
            return_value={"ok": True, "message": "Certificate issued for srv1.beagle-os.com"},
        ):
            response = service.route_post(
                "/api/v1/settings/security/tls/letsencrypt",
                {"domain": "srv1.beagle-os.com", "email": "ops@beagle-os.com"},
            )

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 200)
        self.assertTrue(response["payload"]["ok"])


    def test_get_artifacts_reports_missing_and_present_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            dist = install_dir / "dist"
            dist.mkdir(parents=True)
            (install_dir / "VERSION").write_text("6.7.0-test\n", encoding="utf-8")
            (dist / "beagle-downloads-status.json").write_text('{"version":"test"}\n', encoding="utf-8")
            (dist / "pve-thin-client-live-usb-latest.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            service = ServerSettingsService(data_dir=Path(tmpdir) / "data", install_dir=install_dir)

            with mock.patch.object(MODULE, "_run_cmd", return_value="active"), \
                 mock.patch.object(MODULE, "_which", side_effect=lambda tool: f"/usr/bin/{tool}"):
                result = service.get_artifacts()

        self.assertFalse(result["ready"])
        self.assertIn("pve-thin-client-usb-installer-latest.sh", result["missing"])
        self.assertEqual(result["status"]["version"], "test")
        self.assertEqual(result["services"]["beagle-artifacts-refresh.service"], "active")
        self.assertIn("preflight", result)
        self.assertIn("publish_gate", result)
        self.assertIn("context", result)
        self.assertIn("live_events", result)
        self.assertEqual(result["context"]["repo"]["branch"], "main")
        self.assertEqual(result["context"]["github"]["repository"], "meinzeug/beagle-os")
        self.assertIn("actions", result["context"]["github"]["actions_url"])
        self.assertEqual(result["publish_gate"]["missing_latest"].count("pve-thin-client-usb-installer-latest.sh"), 1)
        self.assertEqual(result["links"]["downloads_index"], "/beagle-downloads/beagle-downloads-index.html")

    def test_get_artifacts_reports_live_journal_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            dist = install_dir / "dist"
            dist.mkdir(parents=True)
            (install_dir / "VERSION").write_text("6.7.0-test\n", encoding="utf-8")
            service = ServerSettingsService(data_dir=Path(tmpdir) / "data", install_dir=install_dir)

            def fake_run_cmd(cmd, *args, **kwargs):
                if cmd and cmd[0] == "journalctl":
                    return "2026-05-11T20:26:00+00:00 srv1 beagle[1]: Pakete werden installiert\n"
                if cmd[:2] == ["systemctl", "is-active"] and cmd[2] == "beagle-artifacts-refresh.service":
                    return "active"
                if cmd[:2] == ["systemctl", "is-active"]:
                    return "inactive"
                return ""

            with mock.patch.object(MODULE, "_run_cmd", side_effect=fake_run_cmd), \
                 mock.patch.object(MODULE, "_which", side_effect=lambda tool: f"/usr/bin/{tool}"):
                result = service.get_artifacts()

        messages = [event["message"] for event in result["live_events"]]
        self.assertTrue(any("Pakete werden installiert" in message for message in messages))

    def test_get_artifacts_treats_activating_refresh_as_running(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            (install_dir / "dist").mkdir(parents=True)
            service = ServerSettingsService(data_dir=Path(tmpdir) / "data", install_dir=install_dir)

            def fake_run_cmd(cmd, *args, **kwargs):
                if cmd[:2] == ["systemctl", "is-active"] and cmd[2] == "beagle-artifacts-refresh.service":
                    return "activating"
                if cmd[:2] == ["systemctl", "is-active"]:
                    return "inactive"
                return ""

            with mock.patch.object(MODULE, "_run_cmd", side_effect=fake_run_cmd), \
                 mock.patch.object(MODULE, "_which", side_effect=lambda tool: f"/usr/bin/{tool}"):
                result = service.get_artifacts()

        self.assertTrue(result["running_refresh"])
        self.assertEqual(result["primary_status"]["state"], "building")
        self.assertEqual(result["primary_status"]["severity"], "info")

    def test_route_get_updates_stream_returns_sse_descriptor(self):
        service = self.make_service()

        response = service.route_get("/api/v1/settings/updates/stream")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response["kind"], "sse")
        self.assertIn("generator", response)

    def test_start_artifact_refresh_starts_systemd_service(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        with mock.patch.object(MODULE, "_which", return_value="/usr/bin/sudo"), \
             mock.patch.object(MODULE.subprocess, "run", return_value=proc) as run, \
             mock.patch.object(service, "get_artifacts", return_value={"ready": True}):
            result = service.start_artifact_refresh()

        self.assertTrue(result["ok"])
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][1:], ["--no-block", "start", "beagle-artifacts-refresh.service"])
        self.assertTrue(run.call_args.args[0][0].endswith("systemctl"))

    def test_start_artifact_refresh_returns_error_and_failed_status_when_systemd_start_fails(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 1
        proc.stderr = "Interactive authentication required"
        captured_status = []

        with mock.patch.object(MODULE, "_run_systemctl_privileged", return_value=proc), \
             mock.patch.object(service, "_write_refresh_status", side_effect=lambda payload: captured_status.append(payload)):
            result = service.start_artifact_refresh()

        self.assertFalse(result["ok"])
        self.assertIn("artifact refresh start failed", result["error"])
        self.assertGreaterEqual(len(captured_status), 2)
        payload = captured_status[-1]
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["step"], "systemd")
        self.assertIn("Interactive authentication required", payload["error_excerpt"])

    def test_stop_artifact_refresh_stops_and_resets_systemd_service(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        calls = []

        def fake_systemctl(args, *args_pos, **kwargs):
            calls.append(args)
            return proc

        with mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=fake_systemctl), \
             mock.patch.object(service, "get_artifacts", return_value={"running_refresh": False}):
            result = service.stop_artifact_refresh()

        self.assertTrue(result["ok"])
        self.assertEqual(calls, [["stop", "beagle-artifacts-refresh.service"], ["reset-failed", "beagle-artifacts-refresh.service"]])

    def test_restart_artifact_refresh_stops_then_starts_service(self):
        service = self.make_service()

        with mock.patch.object(service, "stop_artifact_refresh", return_value={"ok": True}) as stop, \
             mock.patch.object(service, "start_artifact_refresh", return_value={"ok": True, "artifacts": {"running_refresh": True}}) as start:
            result = service.restart_artifact_refresh()

        self.assertTrue(result["ok"])
        stop.assert_called_once()
        start.assert_called_once()

    def test_route_get_artifacts_returns_ok_wrapper(self):
        service = self.make_service()

        with mock.patch.object(service, "get_artifacts", return_value={"ready": True, "missing": []}):
            response = service.route_get("/api/v1/settings/artifacts")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 200)
        self.assertTrue(response["payload"]["ok"])
        self.assertTrue(response["payload"]["ready"])

    def test_route_post_artifact_refresh_returns_accepted(self):
        service = self.make_service()

        with mock.patch.object(service, "start_artifact_refresh", return_value={"ok": True, "artifacts": {"running_refresh": True}}):
            response = service.route_post("/api/v1/settings/artifacts/refresh", {})

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 202)
        self.assertTrue(response["payload"]["ok"])

    def test_route_post_artifact_refresh_returns_internal_error_on_failure(self):
        service = self.make_service()

        with mock.patch.object(service, "start_artifact_refresh", return_value={"ok": False, "error": "boom"}):
            response = service.route_post("/api/v1/settings/artifacts/refresh", {})

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 500)
        self.assertFalse(response["payload"]["ok"])

    def test_route_post_artifact_stop_and_restart_return_accepted(self):
        service = self.make_service()

        with mock.patch.object(service, "stop_artifact_refresh", return_value={"ok": True, "artifacts": {"running_refresh": False}}):
            stop_response = service.route_post("/api/v1/settings/artifacts/stop", {})
        with mock.patch.object(service, "restart_artifact_refresh", return_value={"ok": True, "artifacts": {"running_refresh": True}}):
            restart_response = service.route_post("/api/v1/settings/artifacts/restart", {})

        self.assertIsNotNone(stop_response)
        self.assertIsNotNone(restart_response)
        assert stop_response is not None
        assert restart_response is not None
        self.assertEqual(int(stop_response["status"]), 202)
        self.assertEqual(int(restart_response["status"]), 202)
        self.assertTrue(stop_response["payload"]["ok"])
        self.assertTrue(restart_response["payload"]["ok"])

    def test_enable_auto_maintenance_enables_repo_and_watchdog_and_triggers_checks(self):
        service = self.make_service()

        with mock.patch.object(service, "run_repo_auto_update", return_value={"ok": True}), \
             mock.patch.object(service, "apply_updates", return_value={"ok": True}), \
             mock.patch.object(service, "get_system_updates_status", return_value={"auto_enabled": True}), \
             mock.patch.object(service, "run_artifact_watchdog", return_value={"ok": True}), \
             mock.patch.object(service, "get_repo_auto_update", return_value={"config": {"enabled": True}}), \
             mock.patch.object(service, "get_artifact_watchdog", return_value={"config": {"enabled": True}}), \
             mock.patch.object(service, "_set_repo_auto_update_timer", return_value=mock.Mock(returncode=0, stderr="")), \
             mock.patch.object(service, "_set_system_updates_timer", return_value=mock.Mock(returncode=0, stderr="")), \
             mock.patch.object(service, "_set_artifact_watchdog_timer", return_value=mock.Mock(returncode=0, stderr="")):
            result = service.enable_auto_maintenance()

        self.assertTrue(result["ok"])
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings.get("repo_auto_update_enabled"))
        self.assertTrue(settings.get("artifact_watchdog_enabled"))
        self.assertTrue(settings.get("artifact_watchdog_auto_repair"))
        self.assertEqual(settings.get("artifact_watchdog_max_age_hours"), 6)

    def test_route_post_maintenance_auto_enable_returns_accepted(self):
        service = self.make_service()

        with mock.patch.object(service, "enable_auto_maintenance", return_value={"ok": True, "maintenance": {"auto_enabled": True}}):
            response = service.route_post("/api/v1/settings/maintenance/auto-enable", {})

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 202)
        self.assertTrue(response["payload"]["ok"])

    def test_route_post_maintenance_run_returns_accepted(self):
        service = self.make_service()

        with mock.patch.object(service, "run_maintenance_now", return_value={"ok": True, "maintenance": {}}):
            response = service.route_post("/api/v1/settings/maintenance/run", {})

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(int(response["status"]), 202)
        self.assertTrue(response["payload"]["ok"])


class ServerSettingsGeneralTests(unittest.TestCase):
    def make_service(self) -> ServerSettingsService:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return ServerSettingsService(data_dir=Path(temp_dir.name))

    def test_update_general_accepts_fqdn_hostname_and_public_url(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_run_cmd", return_value="srv1.beagle-os.com"):
            result = service.update_general(
                {
                    "hostname": "srv1.beagle-os.com",
                    "public_url": "https://srv1.beagle-os.com",
                }
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["settings"]["public_url"], "https://srv1.beagle-os.com")
        self.assertEqual(result["settings"]["hostname"], "srv1.beagle-os.com")

    def test_update_general_skips_hostnamectl_when_hostname_unchanged(self):
        service = self.make_service()
        calls: list[list[str]] = []

        def fake_run_cmd(cmd, *args, **kwargs):
            calls.append(cmd)
            if cmd == ["hostname", "-f"]:
                return "srv1.beagle-os.com"
            if cmd == ["hostname"]:
                return "srv1.beagle-os.com"
            if cmd[:2] == ["hostnamectl", "set-hostname"]:
                return None
            return ""

        with mock.patch.object(MODULE, "_run_cmd", side_effect=fake_run_cmd):
            result = service.update_general(
                {
                    "hostname": "srv1.beagle-os.com",
                    "public_url": "https://srv1.beagle-os.com",
                }
            )

        self.assertTrue(result["ok"], result)
        self.assertNotIn(["hostnamectl", "set-hostname", "srv1.beagle-os.com"], calls)

    def test_update_general_rejects_invalid_hostname(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_run_cmd", return_value="srv1.beagle-os.com"):
            result = service.update_general(
                {
                    "hostname": "srv1..beagle-os.com",
                    "public_url": "https://srv1.beagle-os.com",
                }
            )

        self.assertFalse(result["ok"])
        self.assertIn("invalid hostname format", result["errors"])

    def test_enable_auto_maintenance_recovers_from_invalid_legacy_repo_values(self):
        service = self.make_service()
        service._settings_path.write_text(
            MODULE.json.dumps(
                {
                    "repo_auto_update_enabled": False,
                    "repo_auto_update_repo_url": "ssh://invalid-repo",
                    "repo_auto_update_branch": "bad branch name",
                    "repo_auto_update_interval_minutes": 0,
                }
            ),
            encoding="utf-8",
        )

        with mock.patch.object(service, "run_repo_auto_update", return_value={"ok": True}), \
             mock.patch.object(service, "apply_updates", return_value={"ok": True}), \
             mock.patch.object(service, "get_system_updates_status", return_value={"auto_enabled": True}), \
             mock.patch.object(service, "run_artifact_watchdog", return_value={"ok": True}), \
             mock.patch.object(service, "get_repo_auto_update", wraps=service.get_repo_auto_update), \
             mock.patch.object(service, "get_artifact_watchdog", wraps=service.get_artifact_watchdog), \
             mock.patch.object(service, "_set_repo_auto_update_timer", return_value=mock.Mock(returncode=0, stderr="")), \
             mock.patch.object(service, "_set_system_updates_timer", return_value=mock.Mock(returncode=0, stderr="")), \
             mock.patch.object(service, "_set_artifact_watchdog_timer", return_value=mock.Mock(returncode=0, stderr="")):
            result = service.enable_auto_maintenance()

        self.assertTrue(result["ok"])
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings["repo_auto_update_enabled"])
        self.assertEqual(settings["repo_auto_update_repo_url"], "https://github.com/meinzeug/beagle-os.git")
        self.assertEqual(settings["repo_auto_update_branch"], "main")
        self.assertEqual(settings["repo_auto_update_interval_minutes"], 1)

    def test_get_artifacts_includes_watchdog_config_and_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            dist = install_dir / "dist"
            data_dir = Path(tmpdir) / "data"
            watchdog_status_file = Path(tmpdir) / "artifact-watchdog-status.json"
            dist.mkdir(parents=True)
            data_dir.mkdir(parents=True)
            (install_dir / "VERSION").write_text("6.7.0-test\n", encoding="utf-8")
            (data_dir / "server-settings.json").write_text(
                MODULE.json.dumps(
                    {
                        "artifact_watchdog_enabled": True,
                        "artifact_watchdog_max_age_hours": 12,
                        "artifact_watchdog_auto_repair": False,
                    }
                ),
                encoding="utf-8",
            )
            watchdog_status_file.write_text(
                MODULE.json.dumps(
                    {
                        "state": "drift",
                        "checked_at": "2026-04-26T15:00:00+00:00",
                        "reaction": "notify_only",
                        "message": "Artefakt-Drift erkannt.",
                    }
                ),
                encoding="utf-8",
            )
            service = ServerSettingsService(data_dir=data_dir, install_dir=install_dir)

            with mock.patch.object(MODULE, "_run_cmd", return_value="inactive"), \
                 mock.patch.object(MODULE, "_which", side_effect=lambda tool: f"/usr/bin/{tool}"), \
                 mock.patch.object(MODULE, "_can_start_systemd_unit", return_value=True), \
                 mock.patch.object(MODULE, "_ARTIFACT_WATCHDOG_STATUS_FILE", watchdog_status_file):
                result = service.get_artifacts()

        self.assertIn("watchdog", result)
        self.assertTrue(result["watchdog"]["config"]["enabled"])
        self.assertEqual(result["watchdog"]["config"]["max_age_hours"], 12)
        self.assertEqual(result["watchdog"]["status"]["state"], "drift")
        self.assertEqual(result["watchdog"]["status"]["reaction"], "notify_only")

    def test_update_artifact_watchdog_validates_max_age(self):
        service = self.make_service()

        result = service.update_artifact_watchdog({"enabled": True, "max_age_hours": 0, "auto_repair": True})

        self.assertFalse(result["ok"])
        self.assertIn("max_age_hours", result["errors"][0])

    def test_artifact_watchdog_defaults_to_auto_repair_with_six_hour_age(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_can_start_systemd_unit", return_value=True):
            result = service.get_artifact_watchdog()

        self.assertTrue(result["config"]["enabled"])
        self.assertTrue(result["config"]["auto_repair"])
        self.assertEqual(result["config"]["max_age_hours"], 6)

    def test_update_artifact_watchdog_persists_values(self):
        service = self.make_service()

        with mock.patch.object(service, "get_artifact_watchdog", return_value={"config": {"enabled": True}}), \
             mock.patch.object(service, "_set_artifact_watchdog_timer", return_value=mock.Mock(returncode=0, stderr="")):
            result = service.update_artifact_watchdog({"enabled": True, "max_age_hours": 18, "auto_repair": False})

        self.assertTrue(result["ok"])
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings["artifact_watchdog_enabled"])
        self.assertEqual(settings["artifact_watchdog_max_age_hours"], 18)
        self.assertFalse(settings["artifact_watchdog_auto_repair"])

    def test_update_artifact_watchdog_disable_stops_and_disables_timer(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        calls = []

        def fake_systemctl(args, *, timeout=30):
            calls.append(args)
            return proc

        with mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=fake_systemctl), \
             mock.patch.object(service, "get_artifact_watchdog", return_value={"config": {"enabled": False}}):
            result = service.update_artifact_watchdog({"enabled": False})

        self.assertTrue(result["ok"], result)
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertFalse(settings["artifact_watchdog_enabled"])
        self.assertIn(["stop", "beagle-artifacts-watchdog.service"], calls)
        self.assertIn(["disable", "--now", "beagle-artifacts-watchdog.timer"], calls)

    def test_run_artifact_watchdog_returns_accepted_payload(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""

        with mock.patch.object(MODULE, "_run_systemctl_privileged", return_value=proc), \
             mock.patch.object(service, "get_artifact_watchdog", return_value={"status": {"state": "healthy"}}):
            result = service.run_artifact_watchdog()

        self.assertTrue(result["ok"])
        self.assertEqual(result["watchdog"]["status"]["state"], "healthy")

    def test_get_artifacts_publish_gate_turns_ready_when_latest_and_versioned_installers_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            install_dir = Path(tmpdir) / "beagle"
            dist = install_dir / "dist"
            dist.mkdir(parents=True)
            version = "6.7.0-test"
            (install_dir / "VERSION").write_text(version + "\n", encoding="utf-8")
            (dist / "beagle-downloads-status.json").write_text(
                '{"version":"%s","downloads_path":"/beagle-downloads","status_url":"https://srv1/beagle-downloads/beagle-downloads-status.json"}\n' % version,
                encoding="utf-8",
            )
            for name in MODULE._REQUIRED_ARTIFACTS:
                if name == "beagle-downloads-status.json":
                    continue
                (dist / name).write_text("x\n", encoding="utf-8")
            for name in [
                f"pve-thin-client-usb-installer-v{version}.sh",
                f"pve-thin-client-usb-installer-v{version}.ps1",
                f"pve-thin-client-live-usb-v{version}.sh",
                f"pve-thin-client-live-usb-v{version}.ps1",
            ]:
                (dist / name).write_text("x\n", encoding="utf-8")

            service = ServerSettingsService(data_dir=Path(tmpdir) / "data", install_dir=install_dir)
            with mock.patch.object(MODULE, "_run_cmd", return_value="inactive"), \
                 mock.patch.object(MODULE, "_which", side_effect=lambda tool: f"/usr/bin/{tool}"):
                result = service.get_artifacts()

        self.assertTrue(result["publish_gate"]["public_ready"])
        self.assertEqual(result["publish_gate"]["missing_latest"], [])
        self.assertEqual(result["publish_gate"]["missing_versioned"], [])
        self.assertEqual(result["links"]["status_json"], "https://srv1/beagle-downloads/beagle-downloads-status.json")

    def test_get_firewall_reports_beagle_nftables_guard(self):
        service = self.make_service()

        def fake_run(cmd):
            if cmd == ["systemctl", "is-active", "nftables"]:
                return "active"
            if cmd == ["nft", "list", "table", "inet", "beagle_guard"]:
                return "table inet beagle_guard {\n chain input { policy drop; }\n}"
            return ""

        status_proc = mock.Mock()
        status_proc.returncode = 0
        status_proc.stdout = "active\n"
        status_proc.stderr = ""
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.object(MODULE, "_BEAGLE_FIREWALL_EXTRA_RULES", Path(tmpdir) / "extra.rules"), \
             mock.patch.object(service, "_run_firewall_script", return_value=status_proc), \
             mock.patch.object(MODULE, "_run_cmd", side_effect=fake_run):
            (Path(tmpdir) / "extra.rules").write_text("tcp dport 8443 drop\n", encoding="utf-8")
            result = service.get_firewall()

        self.assertTrue(result["active"])
        self.assertEqual(result["engine"], "nftables")
        self.assertTrue(result["service_active"])
        self.assertGreaterEqual(len(result["rules"]), 5)
        self.assertTrue(result["rules"][0]["managed"])
        self.assertEqual(result["rules"][-1], {"number": "1", "rule": "tcp dport 8443 drop", "managed": False})

    def test_update_firewall_add_rule_persists_safe_nft_rule_and_reapplies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            install_dir = Path(tmpdir) / "install"
            script = install_dir / "scripts" / "apply-beagle-firewall.sh"
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            service = ServerSettingsService(data_dir=data_dir, install_dir=install_dir)
            calls = []

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                proc = mock.Mock()
                proc.returncode = 0
                proc.stdout = ""
                proc.stderr = ""
                return proc

            with mock.patch.object(MODULE, "_BEAGLE_FIREWALL_EXTRA_RULES", Path(tmpdir) / "extra.rules"), \
                 mock.patch.object(MODULE.subprocess, "run", side_effect=fake_run), \
                 mock.patch.object(MODULE.os, "geteuid", return_value=0), \
                 mock.patch.object(service, "get_firewall", return_value={"active": True, "rules": []}):
                result = service.update_firewall({"action": "add_rule", "rule": "allow 9443/tcp"})

            self.assertTrue(result["ok"], result)
            self.assertEqual(calls[0], [str(script), "--add-extra-rule", "tcp dport 9443 accept"])

    def test_update_firewall_enable_uses_systemd_unit_when_sandboxed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            install_dir = Path(tmpdir) / "install"
            script = install_dir / "scripts" / "apply-beagle-firewall.sh"
            action_file = Path(tmpdir) / "run" / "firewall-action.env"
            script.parent.mkdir(parents=True)
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            service = ServerSettingsService(data_dir=data_dir, install_dir=install_dir)
            unit_calls = []

            def fake_systemctl(args, **_kwargs):
                unit_calls.append(args)
                proc = mock.Mock()
                proc.returncode = 0
                proc.stdout = ""
                proc.stderr = ""
                return proc

            with mock.patch.object(MODULE, "_BEAGLE_FIREWALL_ACTION_FILE", action_file), \
                 mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=fake_systemctl), \
                 mock.patch.object(MODULE.os, "geteuid", return_value=1000), \
                 mock.patch.object(service, "get_firewall", return_value={"active": True, "rules": []}):
                result = service.update_firewall({"action": "enable"})

            self.assertTrue(result["ok"], result)
            self.assertEqual(unit_calls, [["start", "beagle-firewall-apply.service"]])
            self.assertEqual(action_file.read_text(encoding="utf-8"), "BEAGLE_FIREWALL_ACTION=enable\nBEAGLE_FIREWALL_ARG_B64=\n")

    def test_route_post_firewall_matches_webui_action_method(self):
        service = self.make_service()
        with mock.patch.object(service, "update_firewall", return_value={"ok": True, "firewall": {"active": True}}) as update:
            response = service.route_post("/api/v1/settings/firewall", {"action": "enable"})

        self.assertIsNotNone(response)
        self.assertEqual(response["status"], MODULE.HTTPStatus.OK)
        self.assertTrue(response["payload"]["ok"])
        update.assert_called_once_with({"action": "enable"})

    def test_get_updates_includes_repo_auto_update_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir(parents=True)
            status_file = Path(tmpdir) / "repo-auto-update-status.json"
            status_file.write_text(MODULE.json.dumps({"state": "healthy", "current_commit": "abc123", "remote_commit": "abc123"}), encoding="utf-8")
            (data_dir / "server-settings.json").write_text(
                MODULE.json.dumps(
                    {
                        "repo_auto_update_enabled": True,
                        "repo_auto_update_repo_url": "https://github.com/meinzeug/beagle-os.git",
                        "repo_auto_update_branch": "main",
                        "repo_auto_update_interval_minutes": 30,
                    }
                ),
                encoding="utf-8",
            )
            service = ServerSettingsService(data_dir=data_dir)
            run_values = {
                ("apt-get", "update", "-qq"): "",
                ("apt", "list", "--upgradable"): "Listing...\n",
                ("systemctl", "is-active", "beagle-repo-auto-update.service"): "inactive",
                ("systemctl", "is-active", "beagle-repo-auto-update.timer"): "active",
            }

            def fake_run(cmd, **_kwargs):
                return run_values.get(tuple(cmd), "")

            with mock.patch.object(MODULE, "_run_cmd", side_effect=fake_run), \
                 mock.patch.object(MODULE, "_can_start_systemd_unit", return_value=True), \
                 mock.patch.object(MODULE, "_REPO_AUTO_UPDATE_STATUS_FILE", status_file):
                result = service.get_updates()

        self.assertEqual(result["source"], "apt")
        self.assertIn("repo_auto_update", result)
        self.assertTrue(result["repo_auto_update"]["config"]["enabled"])
        self.assertEqual(result["repo_auto_update"]["status"]["state"], "healthy")

    def test_update_repo_auto_update_validates_repo_and_interval(self):
        service = self.make_service()

        result = service.update_repo_auto_update({"repo_url": "git@github.com:bad", "channel": "nightly", "interval_minutes": 0})

        self.assertFalse(result["ok"])
        self.assertGreaterEqual(len(result["errors"]), 1)
        self.assertIn("channel must be stable or rolling", result["errors"])

    def test_repo_auto_update_defaults_to_security_automation(self):
        service = self.make_service()

        with mock.patch.object(MODULE, "_run_cmd", return_value="inactive"), \
             mock.patch.object(MODULE, "_can_start_systemd_unit", return_value=True):
            result = service.get_repo_auto_update()

        self.assertTrue(result["config"]["enabled"])
        self.assertEqual(result["config"]["repo_url"], "https://github.com/meinzeug/beagle-os.git")
        self.assertEqual(result["config"]["branch"], "main")
        self.assertEqual(result["config"]["channel"], "stable")
        self.assertEqual(result["config"]["interval_minutes"], 1)
        self.assertEqual(result["status"]["installed_version"], "")
        self.assertEqual(result["status"]["remote_version"], "")

    def test_update_repo_auto_update_persists_values(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""

        with mock.patch.object(service, "get_repo_auto_update", return_value={"config": {"enabled": True}}), \
             mock.patch.object(MODULE, "_run_systemctl_privileged", return_value=proc):
            result = service.update_repo_auto_update({
                "enabled": True,
                "repo_url": "https://github.com/meinzeug/beagle-os.git",
                "branch": "main",
                "channel": "rolling",
                "interval_minutes": 1,
            })

        self.assertTrue(result["ok"])
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings["repo_auto_update_enabled"])
        self.assertEqual(settings["repo_auto_update_branch"], "main")
        self.assertEqual(settings["repo_auto_update_channel"], "rolling")
        self.assertEqual(settings["repo_auto_update_interval_minutes"], 1)

    def test_update_repo_auto_update_channel_save_does_not_reapply_unchanged_timer(self):
        service = self.make_service()
        service._save_settings({"repo_auto_update_enabled": True})

        with mock.patch.object(service, "get_repo_auto_update", return_value={"config": {"enabled": True}}), \
             mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=AssertionError("timer should not be touched")):
            result = service.update_repo_auto_update({
                "enabled": True,
                "channel": "rolling",
            })

        self.assertTrue(result["ok"], result)
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings["repo_auto_update_enabled"])
        self.assertEqual(settings["repo_auto_update_channel"], "rolling")

    def test_update_repo_auto_update_enable_also_enables_system_updates_timer(self):
        service = self.make_service()
        service._save_settings({"repo_auto_update_enabled": False})
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        calls = []

        def fake_systemctl(args, *, timeout=30):
            calls.append(args)
            return proc

        with mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=fake_systemctl), \
             mock.patch.object(service, "get_repo_auto_update", return_value={"config": {"enabled": True}}):
            result = service.update_repo_auto_update({"enabled": True})

        self.assertTrue(result["ok"], result)
        self.assertIn(["enable", "--now", "beagle-repo-auto-update.timer"], calls)
        self.assertIn(["enable", "--now", "beagle-system-updates.timer"], calls)

    def test_update_repo_auto_update_disable_stops_and_disables_timer(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""
        calls = []

        def fake_systemctl(args, *, timeout=30):
            calls.append(args)
            return proc

        with mock.patch.object(MODULE, "_run_systemctl_privileged", side_effect=fake_systemctl), \
             mock.patch.object(service, "get_repo_auto_update", return_value={"config": {"enabled": False}}):
            result = service.update_repo_auto_update({"enabled": False})

        self.assertTrue(result["ok"], result)
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertFalse(settings["repo_auto_update_enabled"])
        self.assertIn(["stop", "beagle-repo-auto-update.service"], calls)
        self.assertIn(["disable", "--now", "beagle-repo-auto-update.timer"], calls)
        self.assertIn(["stop", "beagle-system-updates.service"], calls)
        self.assertIn(["disable", "--now", "beagle-system-updates.timer"], calls)

    def test_apply_updates_starts_privileged_systemd_unit(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""

        with mock.patch.object(MODULE, "_run_systemctl_privileged", return_value=proc) as run, \
             mock.patch.object(service, "get_system_updates_status", return_value={"status": {"status": "running"}}):
            result = service.apply_updates()

        self.assertTrue(result["ok"], result)
        run.assert_called_once_with(["--no-block", "start", "beagle-system-updates.service"], timeout=30)
        self.assertEqual(result["system_updates"]["status"]["status"], "running")

    def test_run_repo_auto_update_returns_accepted_payload(self):
        service = self.make_service()
        proc = mock.Mock()
        proc.returncode = 0
        proc.stderr = ""

        with mock.patch.object(MODULE, "_run_systemctl_privileged", return_value=proc), \
             mock.patch.object(service, "get_repo_auto_update", return_value={"status": {"state": "updating"}}):
            result = service.run_repo_auto_update()

        self.assertTrue(result["ok"])
        self.assertEqual(result["repo_auto_update"]["status"]["state"], "updating")

    def test_update_artifact_watchdog_skips_timer_when_enabled_unchanged(self):
        service = self.make_service()
        service._save_settings({
            "artifact_watchdog_enabled": True,
            "artifact_watchdog_max_age_hours": 6,
            "artifact_watchdog_auto_repair": True,
        })

        with mock.patch.object(MODULE, "_run_systemctl_privileged") as run_systemctl:
            result = service.update_artifact_watchdog({
                "enabled": True,
                "max_age_hours": 8,
                "auto_repair": True,
            })

        self.assertTrue(result["ok"], result)
        run_systemctl.assert_not_called()
        settings = MODULE.json.loads(service._settings_path.read_text(encoding="utf-8"))
        self.assertTrue(settings["artifact_watchdog_enabled"])
        self.assertEqual(settings["artifact_watchdog_max_age_hours"], 8)


if __name__ == "__main__":
    unittest.main()

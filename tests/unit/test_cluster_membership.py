from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from ca_manager import ClusterCaService
from cluster_membership import ClusterMembershipService


class ClusterMembershipServiceTests(unittest.TestCase):
    def make_service(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        ca_service = ClusterCaService(data_dir=Path(temp_dir.name))
        service = ClusterMembershipService(
            data_dir=Path(temp_dir.name),
            ca_service=ca_service,
            public_manager_url="https://leader.example.test/beagle-api",
            rpc_port=9089,
            utcnow=lambda: "2026-04-23T12:00:00Z",
        )
        return service

    def make_service_with_rpc(self, *, rpc_request, rpc_credentials):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        ca_service = ClusterCaService(data_dir=Path(temp_dir.name))
        service = ClusterMembershipService(
            data_dir=Path(temp_dir.name),
            ca_service=ca_service,
            public_manager_url="https://leader.example.test/beagle-api",
            rpc_port=9089,
            utcnow=lambda: "2026-04-23T12:00:00Z",
            rpc_request=rpc_request,
            rpc_credentials=rpc_credentials,
        )
        return service

    def test_apply_join_response_persists_install_check_report_token(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        env_file = root / "beagle-manager.env"
        env_file.write_text('BEAGLE_MANAGER_API_TOKEN="local"\n', encoding="utf-8")
        ca_service = ClusterCaService(data_dir=root)
        service = ClusterMembershipService(
            data_dir=root,
            ca_service=ca_service,
            public_manager_url="https://leader.example.test/beagle-api",
            rpc_port=9089,
            utcnow=lambda: "2026-04-23T12:00:00Z",
            control_env_file=env_file,
        )

        applied = service.apply_join_response(
            node_name="node-b",
            payload={
                "cluster": {
                    "cluster_id": "cluster-123",
                    "leader_node": "leader-node",
                    "created_at": "2026-04-23T12:00:00Z",
                    "updated_at": "2026-04-23T12:00:00Z",
                },
                "member": {
                    "name": "node-b",
                    "api_url": "https://node-b.example.test/beagle-api",
                    "rpc_url": "https://node-b.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
                "members": [
                    {
                        "name": "leader-node",
                        "api_url": "https://leader.example.test/beagle-api",
                        "rpc_url": "https://leader.example.test:9089/rpc",
                        "status": "online",
                        "local": False,
                    },
                    {
                        "name": "node-b",
                        "api_url": "https://node-b.example.test/beagle-api",
                        "rpc_url": "https://node-b.example.test:9089/rpc",
                        "status": "online",
                        "local": False,
                    },
                ],
                "certificate": {
                    "cert_pem": "node-cert",
                    "key_pem": "node-key",
                    "ca_cert_pem": "ca-cert",
                },
                "install_check_report_token": "shared-token",
            },
        )

        self.assertEqual(applied["member"]["name"], "node-b")
        self.assertIn('BEAGLE_INSTALL_CHECK_REPORT_TOKEN="shared-token"', env_file.read_text(encoding="utf-8"))

    def test_initialize_cluster_creates_local_member_and_ca(self):
        service = self.make_service()

        payload = service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        self.assertTrue(payload["cluster"]["cluster_id"])
        self.assertEqual(payload["member"]["name"], "leader-node")
        self.assertTrue(service.is_initialized())
        self.assertEqual(len(service.list_members()), 1)

    def test_create_accept_and_apply_join_roundtrip(self):
        leader = self.make_service()
        leader.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        leader._install_check_report_token = "shared-report-token"
        token_payload = leader.create_join_token()

        accepted = leader.accept_join_request(
            join_token=token_payload["join_token"],
            node_name="node-b",
            api_url="https://node-b.example.test/beagle-api",
            advertise_host="node-b.example.test",
            rpc_url="https://node-b.example.test:9192/rpc",
        )
        self.assertEqual(accepted["member"]["rpc_url"], "https://node-b.example.test:9192/rpc")

        follower = self.make_service()
        applied = follower.apply_join_response(node_name="node-b", payload=accepted)

        self.assertEqual(applied["member"]["name"], "node-b")
        self.assertEqual(len(applied["members"]), 2)
        local = follower.local_member()
        self.assertIsNotNone(local)
        self.assertEqual(local["name"], "node-b")
        self.assertEqual(accepted["install_check_report_token"], "shared-report-token")

    def test_join_existing_cluster_posts_to_leader_and_applies_response(self):
        follower = self.make_service()
        join_payload = {
            "cluster_id": "cluster-123",
            "leader_api_url": "https://leader.example.test/beagle-api",
            "secret": "secret-123",
        }
        join_token = ClusterMembershipService._encode_join_token(join_payload)
        leader_response = {
            "ok": True,
            "cluster": {
                "cluster_id": "cluster-123",
                "leader_node": "leader-node",
                "created_at": "2026-04-23T12:00:00Z",
                "updated_at": "2026-04-23T12:00:00Z",
            },
            "member": {
                "name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "rpc_url": "https://node-b.example.test:9089/rpc",
                "status": "online",
                "local": False,
            },
            "members": [
                {
                    "name": "leader-node",
                    "api_url": "https://leader.example.test/beagle-api",
                    "rpc_url": "https://leader.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
                {
                    "name": "node-b",
                    "api_url": "https://node-b.example.test/beagle-api",
                    "rpc_url": "https://node-b.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
            ],
            "certificate": {
                "cert_pem": "node-cert",
                "key_pem": "node-key",
                "ca_cert_pem": "ca-cert",
            },
        }

        with patch.object(ClusterMembershipService, "_post_json", return_value=leader_response) as post_json:
            result = follower.join_existing_cluster(
                join_token=join_token,
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
                leader_api_url="",
            )

        post_json.assert_called_once()
        self.assertEqual(post_json.call_args.args[0], "https://leader.example.test/beagle-api/api/v1/cluster/join")
        self.assertEqual(post_json.call_args.args[1]["node_name"], "node-b")
        self.assertEqual(result["cluster"]["cluster_id"], "cluster-123")
        local = follower.local_member()
        self.assertIsNotNone(local)
        self.assertEqual(local["name"], "node-b")

    def test_setup_code_is_hashed_one_time_and_rejects_initialized_nodes(self):
        service = self.make_service()

        result = service.create_setup_code(ttl_seconds=120)
        code = result["setup_code"]
        raw_store = service.setup_codes_file().read_text(encoding="utf-8")

        self.assertTrue(code.startswith("BGL-"))
        self.assertNotIn(code, raw_store)
        service.consume_setup_code(code)
        with self.assertRaisesRegex(RuntimeError, "already used"):
            service.consume_setup_code(code)

        initialized = self.make_service()
        initialized.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        with self.assertRaisesRegex(RuntimeError, "already part of a cluster"):
            initialized.create_setup_code()

    def test_join_with_setup_code_consumes_code_and_applies_join_response(self):
        follower = self.make_service()
        setup = follower.create_setup_code(ttl_seconds=120)
        join_payload = {
            "cluster_id": "cluster-123",
            "leader_api_url": "https://leader.example.test/beagle-api",
            "secret": "secret-123",
        }
        join_token = ClusterMembershipService._encode_join_token(join_payload)
        leader_response = {
            "ok": True,
            "cluster": {
                "cluster_id": "cluster-123",
                "leader_node": "leader-node",
                "created_at": "2026-04-23T12:00:00Z",
                "updated_at": "2026-04-23T12:00:00Z",
            },
            "member": {
                "name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "rpc_url": "https://node-b.example.test:9089/rpc",
                "status": "online",
                "local": False,
            },
            "members": [
                {
                    "name": "leader-node",
                    "api_url": "https://leader.example.test/beagle-api",
                    "rpc_url": "https://leader.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
                {
                    "name": "node-b",
                    "api_url": "https://node-b.example.test/beagle-api",
                    "rpc_url": "https://node-b.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
            ],
            "certificate": {
                "cert_pem": "node-cert",
                "key_pem": "node-key",
                "ca_cert_pem": "ca-cert",
            },
        }

        with patch.object(ClusterMembershipService, "_post_json", return_value=leader_response):
            result = follower.join_with_setup_code(
                setup_code=setup["setup_code"],
                join_token=join_token,
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
            )

        self.assertEqual(result["cluster"]["cluster_id"], "cluster-123")
        self.assertEqual(follower.local_member()["name"], "node-b")
        with self.assertRaisesRegex(RuntimeError, "already part of a cluster"):
            follower.join_with_setup_code(
                setup_code=setup["setup_code"],
                join_token=join_token,
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
            )

    def test_auto_join_server_uses_setup_code_and_skips_public_rpc_preflight(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        target_response = {
            "ok": True,
            "cluster": {"cluster_id": service.cluster_state()["cluster_id"]},
            "member": {"name": "node-b"},
            "members": [{"name": "leader-node"}, {"name": "node-b"}],
        }

        with patch("cluster_membership.socket.getaddrinfo", return_value=[object()]), \
             patch.object(ClusterMembershipService, "_tcp_check", return_value=(True, "reachable")), \
             patch.object(ClusterMembershipService, "_post_json", return_value=target_response) as post_json:
            result = service.auto_join_server(
                setup_code="BGL-setup-code",
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
            )

        self.assertTrue(result["ok"])
        post_json.assert_called_once()
        self.assertEqual(post_json.call_args.args[0], "https://node-b.example.test/beagle-api/api/v1/cluster/join-with-setup-code")
        self.assertEqual(post_json.call_args.args[1]["setup_code"], "BGL-setup-code")
        self.assertTrue(post_json.call_args.args[1]["join_token"])
        checks = {item["name"]: item for item in result["preflight"]["checks"]}
        self.assertEqual(checks["rpc_tcp"]["status"], "skipped")
        self.assertFalse(checks["rpc_tcp"]["required"])

    def test_expired_join_token_is_rejected(self):
        leader = self.make_service()
        leader.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        token_payload = leader.create_join_token(ttl_seconds=60)
        decoded = ClusterMembershipService.decode_join_token(token_payload["join_token"])
        tokens = leader._read_json(leader.join_tokens_file(), {})
        tokens[decoded["secret"]]["expires_at"] = 1
        leader._write_json(leader.join_tokens_file(), tokens)

        with self.assertRaisesRegex(RuntimeError, "expired"):
            leader.accept_join_request(
                join_token=token_payload["join_token"],
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
            )

    def test_leave_local_cluster_clears_local_cluster_state(self):
        rpc_request = MagicMock(return_value={"ok": True, "result": {"ok": True, "removed_node": "node-b"}})
        follower = self.make_service_with_rpc(
            rpc_request=rpc_request,
            rpc_credentials=lambda: None,
        )
        accepted = {
            "cluster": {
                "cluster_id": "cluster-123",
                "leader_node": "leader-node",
                "created_at": "2026-04-23T12:00:00Z",
                "updated_at": "2026-04-23T12:00:00Z",
            },
            "member": {
                "name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "rpc_url": "https://node-b.example.test:9089/rpc",
                "status": "online",
                "local": False,
            },
            "members": [
                {
                    "name": "leader-node",
                    "api_url": "https://leader.example.test/beagle-api",
                    "rpc_url": "https://leader.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
                {
                    "name": "node-b",
                    "api_url": "https://node-b.example.test/beagle-api",
                    "rpc_url": "https://node-b.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
            ],
            "certificate": {
                "cert_pem": "node-cert",
                "key_pem": "node-key",
                "ca_cert_pem": "ca-cert",
            },
        }
        follower.apply_join_response(node_name="node-b", payload=accepted)
        creds = (
            follower._ca_service.nodes_dir() / "node-b" / "node.crt",
            follower._ca_service.nodes_dir() / "node-b" / "node.key",
            follower._ca_service.ca_cert_path(),
        )
        follower._rpc_credentials = lambda: creds

        result = follower.leave_local_cluster()

        self.assertTrue(result["ok"])
        self.assertEqual(result["detached_node"], "node-b")
        self.assertTrue(result["leader_confirmed"])
        rpc_request.assert_called_once()
        self.assertEqual(rpc_request.call_args.kwargs["method"], "cluster.member.leave")
        self.assertEqual(rpc_request.call_args.kwargs["params"]["node_name"], "node-b")
        self.assertFalse(follower.is_initialized())
        self.assertFalse(follower.state_file().exists())
        self.assertFalse(follower.members_file().exists())

    def test_leave_local_cluster_rejects_leader(self):
        leader = self.make_service()
        leader.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        with self.assertRaisesRegex(RuntimeError, "leader"):
            leader.leave_local_cluster()

    def test_remove_member_rejects_mismatched_requester(self):
        leader = self.make_service()
        leader.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        leader.accept_join_request(
            join_token=leader.create_join_token()["join_token"],
            node_name="node-b",
            api_url="https://node-b.example.test/beagle-api",
            advertise_host="node-b.example.test",
        )

        with self.assertRaisesRegex(RuntimeError, "not allowed"):
            leader.remove_member(node_name="node-b", requester_node_name="node-c")

    def test_preflight_add_server_can_issue_join_token(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        with patch("cluster_membership.socket.getaddrinfo", return_value=[object()]), \
             patch.object(ClusterMembershipService, "_tcp_check", return_value=(True, "reachable")):
            result = service.preflight_add_server(
                node_name="node-b",
                api_url="https://node-b.example.test/beagle-api",
                advertise_host="node-b.example.test",
                issue_join_token=True,
            )

        self.assertTrue(result["ok"])
        self.assertIn("join_token", result)
        checks = {item["name"]: item for item in result["checks"]}
        self.assertEqual(checks["api_health"]["status"], "skipped")
        self.assertFalse(checks["api_health"]["required"])
        self.assertEqual(checks["kvm"]["status"], "skipped")

    def test_preflight_add_server_rejects_duplicate_node(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        result = service.preflight_add_server(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
            issue_join_token=True,
        )

        self.assertFalse(result["ok"])
        self.assertNotIn("join_token", result)
        checks = {item["name"]: item for item in result["checks"]}
        self.assertEqual(checks["node_name"]["status"], "fail")

    def test_probe_unreachable_marks_member_offline(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        # Manually inject an unreachable remote member.
        members = service.list_members()
        members.append({
            "name": "dead-node",
            "api_url": "http://127.0.0.1:19999/api/v1",
            "rpc_url": "https://127.0.0.1:20000/rpc",
            "status": "online",
            "local": False,
        })
        service._write_json(service.members_file(), members)

        service.probe_and_update_member_statuses(timeout=0.5)

        after = {m["name"]: m for m in service.list_members()}
        self.assertEqual(after["dead-node"]["status"], "unreachable")

    def test_update_member_changes_fields(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        token_payload = service.create_join_token(ttl_seconds=120)
        follower_payload = {
            "cluster": service.cluster_state(),
            "member": {
                "name": "node-b",
                "api_url": "https://node-b.example.test/beagle-api",
                "rpc_url": "https://node-b.example.test:9089/rpc",
                "status": "online",
                "local": False,
            },
            "members": [
                {
                    "name": "leader-node",
                    "api_url": "https://leader.example.test/beagle-api",
                    "rpc_url": "https://leader.example.test:9089/rpc",
                    "status": "online",
                    "local": True,
                },
                {
                    "name": "node-b",
                    "api_url": "https://node-b.example.test/beagle-api",
                    "rpc_url": "https://node-b.example.test:9089/rpc",
                    "status": "online",
                    "local": False,
                },
            ],
            "certificate": {"cert_pem": "c", "key_pem": "k", "ca_cert_pem": "ca"},
        }
        service._write_json(service.members_file(), follower_payload["members"])

        result = service.update_member(
            node_name="node-b",
            display_name="Node B Renamed",
            api_url="https://node-b-new.example.test/beagle-api",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["member"]["display_name"], "Node B Renamed")
        self.assertEqual(result["member"]["api_url"], "https://node-b-new.example.test/beagle-api")
        # rpc_url should remain unchanged
        self.assertEqual(result["member"]["rpc_url"], "https://node-b.example.test:9089/rpc")
        saved = {m["name"]: m for m in service.list_members()}
        self.assertEqual(saved["node-b"]["display_name"], "Node B Renamed")

    def test_update_member_not_found_raises(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )

        with self.assertRaisesRegex(RuntimeError, "not found"):
            service.update_member(node_name="does-not-exist")

    def test_update_member_enabled_flag(self):
        service = self.make_service()
        service.initialize_cluster(
            node_name="leader-node",
            api_url="https://leader.example.test/beagle-api",
            advertise_host="leader.example.test",
        )
        members = service.list_members()
        members.append({
            "name": "node-c",
            "api_url": "https://node-c.example.test/beagle-api",
            "rpc_url": "https://node-c.example.test:9089/rpc",
            "status": "online",
            "local": False,
        })
        service._write_json(service.members_file(), members)

        result = service.update_member(node_name="node-c", enabled=False)
        self.assertTrue(result["ok"])
        self.assertFalse(result["member"]["enabled"])
        result2 = service.update_member(node_name="node-c", enabled=True)
        self.assertTrue(result2["member"]["enabled"])

    def test_local_preflight_kvm_libvirt_returns_checks(self):
        from unittest.mock import patch as mock_patch, MagicMock
        import subprocess
        service = self.make_service()

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 0
            m.stdout = "libvirt 10.0.0"
            m.stderr = ""
            return m

        with mock_patch("os.path.exists", return_value=True), \
             mock_patch("subprocess.run", side_effect=fake_run), \
             mock_patch.object(service.__class__, "_tcp_check", return_value=(True, "reachable")):
            result = service.local_preflight_kvm_libvirt()

        self.assertIsInstance(result, dict)
        self.assertIn("checks", result)
        check_names = {c["name"] for c in result["checks"]}
        self.assertIn("kvm_device", check_names)
        self.assertIn("libvirtd", check_names)
        self.assertIn("virsh_connection", check_names)

    def test_local_preflight_kvm_libvirt_fails_without_kvm(self):
        from unittest.mock import patch as mock_patch, MagicMock
        service = self.make_service()

        def fake_run(cmd, **kwargs):
            m = MagicMock()
            m.returncode = 1
            m.stdout = ""
            m.stderr = "not found"
            return m

        with mock_patch("os.path.exists", return_value=False), \
             mock_patch("subprocess.run", side_effect=fake_run), \
             mock_patch.object(service.__class__, "_tcp_check", return_value=(False, "refused")):
            result = service.local_preflight_kvm_libvirt()

        self.assertFalse(result["ok"])
        checks = {c["name"]: c for c in result["checks"]}
        self.assertEqual(checks["kvm_device"]["status"], "fail")

    def test_probe_member_health_uses_unverified_context_for_https(self):
        service = self.make_service()

        class _Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("cluster_membership.urllib.request.urlopen", return_value=_Resp()) as urlopen:
            healthy = service._probe_member_health({"api_url": "https://srv2.beagle-os.com/beagle-api/api/v1"})

        self.assertTrue(healthy)
        self.assertIn("context", urlopen.call_args.kwargs)
        self.assertIsNotNone(urlopen.call_args.kwargs["context"])

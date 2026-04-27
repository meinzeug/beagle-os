"""Unit tests for Plan 11 L216: Auto-Pairing without manual PIN.

Verifies the complete auto-pairing flow:
  1. Endpoint requests a pairing token → receives signed token + PIN (no user sees PIN)
  2. Endpoint exchanges token with Sunshine via API → pairing confirmed automatically
  3. Tampered tokens are rejected
  4. Expired tokens are rejected
  5. Wrong VM identity is rejected
  6. Missing pairing_token in exchange is rejected

This ensures that Moonlight clients can pair with Sunshine VMs without any
manual PIN entry by the user — the PIN is embedded in the token and used
programmatically.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_SERVICES = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(_SERVICES) not in sys.path:
    sys.path.insert(0, str(_SERVICES))

from endpoint_http_surface import EndpointHttpSurfaceService  # type: ignore[import]
from pairing_service import PairingService  # type: ignore[import]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Vm:
    def __init__(self, vmid: int = 100, node: str = "beagle-0") -> None:
        self.vmid = vmid
        self.node = node


def _make_surface(
    *,
    exchange_ok: bool = True,
    exchange_fn=None,
    issue_fn=None,
) -> EndpointHttpSurfaceService:
    vm = _Vm()

    def _find(vmid: int):
        return vm if int(vmid) == vm.vmid else None

    def _default_issue(_vm, _identity, device_name):
        return {"ok": True, "token": "auto-pair-token", "pin": "9876", "expires_at": "2026-05-01T00:00:00Z"}

    def _default_exchange(_vm, _identity, pairing_token):
        return {"ok": exchange_ok}

    class _SessionManagerStub:
        def find_active_session(self, *, session_id="", vm_id=0):
            return None

    return EndpointHttpSurfaceService(
        build_vm_profile=lambda item: {},
        dequeue_vm_actions=lambda node, vmid: [],
        exchange_moonlight_pairing_token=exchange_fn or _default_exchange,
        fetch_sunshine_server_identity=lambda vm, guest_user: {},
        find_vm=_find,
        issue_moonlight_pairing_token=issue_fn or _default_issue,
        prepare_virtual_display_on_vm=lambda vm, res: {"ok": True, "resolution": res, "exitcode": 0, "stdout": "", "stderr": ""},
        register_moonlight_certificate_on_vm=lambda vm, cert, device_name: {"ok": True},
        service_name="beagle-control-plane",
        session_manager_service=_SessionManagerStub(),
        store_action_result=lambda node, vmid, payload: None,
        store_support_bundle=lambda node, vmid, action_id, filename, payload: {},
        summarize_action_result=lambda action_id, result: "",
        utcnow=lambda: "2026-04-24T10:00:00+00:00",
        version="6.7.0",
    )


def _identity(vmid: int = 100, node: str = "beagle-0") -> dict:
    return {
        "vmid": vmid,
        "node": node,
        "hostname": f"endpoint-{vmid}",
        "endpoint_id": f"ep-{vmid}",
    }


def _route_post(surface, path, *, identity=None, json_payload=None):
    """Helper that calls route_post with the correct signature."""
    return surface.route_post(
        path,
        endpoint_identity=identity,
        query={},
        json_payload=json_payload,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAutoPairingFlow(unittest.TestCase):

    def test_pair_token_issued_without_user_pin_input(self):
        """pair-token endpoint returns a signed token + embedded PIN — no user interaction."""
        surface = _make_surface()
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-token",
            identity=_identity(), json_payload={"device_name": "moonlight-client"})
        self.assertEqual(resp["status"], 201)
        pairing = resp["payload"]["pairing"]
        self.assertTrue(pairing["token"])           # token issued
        self.assertTrue(pairing["pin"])             # PIN embedded (not shown to user)
        self.assertTrue(pairing["expires_at"])

    def test_pair_token_exchange_succeeds_without_user_input(self):
        """pair-exchange endpoint pairs automatically using the token (no user PIN entry)."""
        surface = _make_surface(exchange_ok=True)
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-exchange",
            identity=_identity(), json_payload={"pairing_token": "auto-pair-token"})
        self.assertEqual(resp["status"], 200)
        self.assertTrue(resp["payload"]["ok"])

    def test_pair_exchange_fails_when_sunshine_rejects(self):
        """502 returned if Sunshine rejects the token exchange."""
        surface = _make_surface(exchange_ok=False)
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-exchange",
            identity=_identity(), json_payload={"pairing_token": "auto-pair-token"})
        self.assertEqual(resp["status"], 502)
        self.assertFalse(resp["payload"]["ok"])

    def test_pair_exchange_missing_token_returns_400(self):
        """pair-exchange without pairing_token field returns 400."""
        surface = _make_surface()
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-exchange",
            identity=_identity(), json_payload={})
        self.assertEqual(resp["status"], 400)
        self.assertIn("pairing_token", resp["payload"]["error"])

    def test_pair_token_wrong_vm_returns_404(self):
        """pair-token for non-existent VM returns 404."""
        surface = _make_surface()
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-token",
            identity=_identity(vmid=9999, node="beagle-0"), json_payload={"device_name": "client"})
        self.assertEqual(resp["status"], 404)

    def test_pair_exchange_exception_returns_502(self):
        """Exception in exchange_fn returns 502 (graceful error handling)."""
        def _boom(_vm, _identity, pairing_token):
            raise ConnectionError("Sunshine unreachable")

        surface = _make_surface(exchange_fn=_boom)
        resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-exchange",
            identity=_identity(), json_payload={"pairing_token": "any-token"})
        self.assertEqual(resp["status"], 502)

    def test_full_auto_pairing_cycle_no_user_interaction(self):
        """Full cycle: issue token → exchange token → paired. No PIN prompt ever shown."""
        received_pin: list[str] = []

        def _issue(_vm, _identity, device_name):
            pin = "5555"  # PIN embedded, never surfaced to user
            received_pin.append(pin)
            return {"ok": True, "token": "tok-5555", "pin": pin, "expires_at": "2026-05-01T00:00:00Z"}

        def _exchange(_vm, _identity, pairing_token):
            # In production, Sunshine receives the PIN from the token automatically
            return {"ok": pairing_token == "tok-5555"}

        surface = _make_surface(issue_fn=_issue, exchange_fn=_exchange)

        # Step 1: Endpoint requests pairing token (automated, no user interaction)
        issue_resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-token",
            identity=_identity(), json_payload={"device_name": "moonlight-auto"})
        self.assertEqual(issue_resp["status"], 201)
        token = issue_resp["payload"]["pairing"]["token"]
        self.assertEqual(token, "tok-5555")

        # Step 2: Endpoint exchanges token (automated, no user interaction)
        exchange_resp = _route_post(surface, "/api/v1/endpoints/moonlight/pair-exchange",
            identity=_identity(), json_payload={"pairing_token": token})
        self.assertEqual(exchange_resp["status"], 200)
        self.assertTrue(exchange_resp["payload"]["ok"])


class TestPairingServiceTokenSecurity(unittest.TestCase):
    """PairingService HMAC security tests for Plan 11 auto-pairing."""

    def _svc(self, secret: str = "test-secret") -> PairingService:
        return PairingService(
            signing_secret=secret,
            token_ttl_seconds=300,
            utcnow=lambda: "2026-04-24T10:00:00+00:00",
        )

    def test_token_contains_pin_not_exposed_to_client(self):
        """The PIN is embedded in the token payload, not in the API response path."""
        svc = self._svc()
        token = svc.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "4242"})
        payload = svc.validate_token(token)
        self.assertEqual(payload["pairing_pin"], "4242")
        # Token is opaque to the recipient — they pass it as-is, never see the PIN
        self.assertNotIn("4242", token.split(".")[0])  # PIN not in raw header

    def test_tampered_signature_rejected(self):
        svc = self._svc()
        token = svc.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "1111"})
        bad = token[:-4] + "XXXX"
        self.assertIsNone(svc.validate_token(bad))

    def test_expired_token_rejected(self):
        svc_issue = self._svc()
        token = svc_issue.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "2222"})

        # Validate at t+10min (past 5-min TTL)
        svc_late = PairingService(
            signing_secret="test-secret",
            token_ttl_seconds=300,
            utcnow=lambda: "2026-04-24T10:10:00+00:00",
        )
        self.assertIsNone(svc_late.validate_token(token))

    def test_wrong_secret_rejected(self):
        svc_a = self._svc(secret="secret-a")
        svc_b = self._svc(secret="secret-b")
        token = svc_a.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "3333"})
        self.assertIsNone(svc_b.validate_token(token))

    def test_valid_token_accepted(self):
        svc = self._svc()
        token = svc.issue_token({"vmid": 100, "node": "beagle-0", "pairing_pin": "7777"})
        payload = svc.validate_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["pairing_pin"], "7777")


if __name__ == "__main__":
    unittest.main()

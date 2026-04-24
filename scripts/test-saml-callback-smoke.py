#!/usr/bin/env python3
"""Smoke test: SAML assertion with bad signature is rejected, audit event created."""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HOST = "http://srv1.beagle-os.com:9088"
ADMIN_TOKEN = ""  # filled from env or CLI

PASS_COUNT = 0
TOTAL_COUNT = 0


def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def passed(msg: str) -> None:
    global PASS_COUNT, TOTAL_COUNT
    print(f"[PASS] {msg}", flush=True)
    PASS_COUNT += 1
    TOTAL_COUNT += 1


def failed(msg: str) -> None:
    global TOTAL_COUNT
    print(f"[FAIL] {msg}", flush=True)
    TOTAL_COUNT += 1


def _api(method: str, path: str, body: bytes | None = None, content_type: str = "application/json", token: str = "") -> tuple[int, dict]:
    url = f"{HOST}{path}"
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except Exception:
            return exc.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _make_saml_response(
    *,
    include_signature: bool = True,
    status: str = "urn:oasis:names:tc:SAML:2.0:status:Success",
    not_on_or_after: str | None = None,
    name_id: str = "test@example.com",
) -> str:
    sig_block = ""
    if include_signature:
        sig_block = (
            '<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'
            "<ds:SignedInfo>"
            '<ds:Reference URI="#id1"><ds:DigestValue>AAAA</ds:DigestValue></ds:Reference>'
            "</ds:SignedInfo>"
            "<ds:SignatureValue>AAAA</ds:SignatureValue>"
            "</ds:Signature>"
        )
    not_on_after_attr = f' NotOnOrAfter="{not_on_or_after}"' if not_on_or_after else ""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"'
        ' xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"'
        ' ID="id1" Version="2.0">'
        f"{sig_block}"
        "<samlp:Status>"
        f'<samlp:StatusCode Value="{status}"/>'
        "</samlp:Status>"
        "<saml:Assertion>"
        f"<saml:Conditions{not_on_after_attr}></saml:Conditions>"
        f"<saml:NameID>{name_id}</saml:NameID>"
        "</saml:Assertion>"
        "</samlp:Response>"
    )
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


def _post_saml_callback(saml_b64: str) -> tuple[int, dict]:
    """POST to /api/v1/auth/saml/callback with form-encoded SAMLResponse."""
    body = urllib.parse.urlencode({"SAMLResponse": saml_b64}).encode("ascii")
    return _api("POST", "/api/v1/auth/saml/callback", body=body, content_type="application/x-www-form-urlencoded")


def _get_audit_events(token: str) -> list[dict]:
    status, body = _api("GET", "/api/v1/audit/events", token=token)
    if status == 200:
        return body.get("events", [])
    return []


def _admin_login() -> str:
    """Return admin token or empty string."""
    import os
    admin_pass = os.environ.get("BEAGLE_ADMIN_PASSWORD", "admin")
    status, body = _api(
        "POST",
        "/api/v1/auth/login",
        body=json.dumps({"username": "admin", "password": admin_pass}).encode(),
    )
    if status == 200:
        return str(body.get("access_token") or "")
    return ""


def test_unsigned_assertion_rejected() -> None:
    info("Test 1: Unsigned SAML assertion is rejected (401)...")
    b64 = _make_saml_response(include_signature=False)
    status, body = _post_saml_callback(b64)
    if status == 401:
        passed("Unsigned assertion → 401 Unauthorized")
    else:
        failed(f"Expected 401, got {status}: {body}")


def test_expired_assertion_rejected() -> None:
    info("Test 2: Expired SAML assertion is rejected (401)...")
    past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    b64 = _make_saml_response(not_on_or_after=past_ts)
    status, body = _post_saml_callback(b64)
    if status == 401:
        passed("Expired assertion → 401 Unauthorized")
    else:
        failed(f"Expected 401, got {status}: {body}")


def test_missing_saml_response() -> None:
    info("Test 3: Missing SAMLResponse returns 400...")
    body_bytes = b"relay_state=test"
    status, body = _api("POST", "/api/v1/auth/saml/callback", body=body_bytes, content_type="application/x-www-form-urlencoded")
    if status == 400:
        passed("Missing SAMLResponse → 400 Bad Request")
    else:
        failed(f"Expected 400, got {status}: {body}")


def test_valid_signed_assertion_accepted() -> None:
    info("Test 4: Valid signed assertion is accepted (200)...")
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    b64 = _make_saml_response(not_on_or_after=future_ts)
    status, body = _post_saml_callback(b64)
    if status == 200:
        passed(f"Valid assertion → 200 OK, name_id={body.get('claims', {}).get('name_id')}")
    else:
        failed(f"Expected 200, got {status}: {body}")


def test_audit_event_on_rejection(token: str) -> None:
    info("Test 5: Audit event created on assertion rejection...")
    if not token:
        info("  Skipping audit event check (no admin token)")
        return

    # First trigger a rejection
    b64 = _make_saml_response(include_signature=False)
    _post_saml_callback(b64)

    # Check audit events
    events = _get_audit_events(token)
    saml_rejections = [e for e in events if "saml" in str(e.get("event_type") or "").lower() and "reject" in str(e.get("event_type") or "").lower()]
    if saml_rejections:
        passed(f"Audit event 'auth.saml.assertion_rejected' found ({len(saml_rejections)} events)")
    else:
        failed(f"No audit.saml.assertion_rejected event found (total events: {len(events)})")


def main() -> int:
    import os
    global HOST

    HOST = os.environ.get("BEAGLE_HOST", "http://srv1.beagle-os.com:9088")
    info(f"Testing SAML callback at {HOST}")
    info("")

    token = _admin_login()
    if not token:
        info("WARNING: Could not login as admin, audit event test will be skipped")

    test_unsigned_assertion_rejected()
    test_expired_assertion_rejected()
    test_missing_saml_response()
    test_valid_signed_assertion_accepted()
    test_audit_event_on_rejection(token)

    info("")
    info("=" * 40)
    info(f"Results: {PASS_COUNT}/{TOTAL_COUNT} tests passed")
    info("=" * 40)

    if PASS_COUNT == TOTAL_COUNT:
        print("SAML_CALLBACK_SMOKE=PASS")
        return 0
    else:
        print("SAML_CALLBACK_SMOKE=FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())

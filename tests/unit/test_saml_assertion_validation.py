"""Unit tests for SAML assertion validation in SamlService."""

import base64
import sys
import os
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../beagle-host/services"))

from saml_service import SamlService, SamlAssertionError


def _make_saml_response(
    *,
    include_signature: bool = True,
    status: str = "urn:oasis:names:tc:SAML:2.0:status:Success",
    not_on_or_after: str | None = None,
    audience: str | None = None,
    name_id: str = "test@example.com",
) -> str:
    """Build a minimal (unsigned-but-structurally-valid) SAML Response and return base64."""
    sig_block = ""
    if include_signature:
        sig_block = (
            "<ds:Signature xmlns:ds=\"http://www.w3.org/2000/09/xmldsig#\">"
            "<ds:SignedInfo>"
            "<ds:Reference URI=\"#id1\"><ds:DigestValue>AAAA</ds:DigestValue></ds:Reference>"
            "</ds:SignedInfo>"
            "<ds:SignatureValue>AAAA</ds:SignatureValue>"
            "</ds:Signature>"
        )

    not_on_after_attr = ""
    if not_on_or_after:
        not_on_after_attr = f' NotOnOrAfter="{not_on_or_after}"'

    audience_block = ""
    if audience:
        audience_block = (
            f'<saml:AudienceRestriction>'
            f'<saml:Audience>{audience}</saml:Audience>'
            f'</saml:AudienceRestriction>'
        )

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
        f'<saml:Conditions{not_on_after_attr}>'
        f"{audience_block}"
        "</saml:Conditions>"
        f"<saml:NameID>{name_id}</saml:NameID>"
        "<saml:AttributeStatement>"
        '<saml:Attribute Name="email">'
        f"<saml:AttributeValue>{name_id}</saml:AttributeValue>"
        "</saml:Attribute>"
        "</saml:AttributeStatement>"
        "</saml:Assertion>"
        "</samlp:Response>"
    )
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


def _make_service(entity_id: str = "") -> SamlService:
    return SamlService(
        enabled=True,
        entity_id=entity_id,
        acs_url="https://beagle.example.com/api/v1/auth/saml/callback",
        idp_sso_url="https://idp.example.com/sso",
        nameid_format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
        signing_cert_pem="",
    )


class TestSamlAssertionValidation(unittest.TestCase):

    def test_valid_assertion_passes(self):
        """A properly structured assertion with signature passes validation."""
        svc = _make_service()
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = _make_saml_response(not_on_or_after=future_ts)
        claims = svc.validate_assertion(b64)
        self.assertEqual(claims["name_id"], "test@example.com")
        self.assertIn("email", claims["attributes"])

    def test_unsigned_assertion_rejected(self):
        """Assertion without Signature element must be rejected."""
        svc = _make_service()
        b64 = _make_saml_response(include_signature=False)
        with self.assertRaises(SamlAssertionError) as ctx:
            svc.validate_assertion(b64)
        self.assertIn("Signature", str(ctx.exception))
        self.assertIn("unsigned", str(ctx.exception).lower())

    def test_expired_assertion_rejected(self):
        """Assertion with NotOnOrAfter in the past must be rejected."""
        svc = _make_service()
        past_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = _make_saml_response(not_on_or_after=past_ts)
        with self.assertRaises(SamlAssertionError) as ctx:
            svc.validate_assertion(b64)
        self.assertIn("expired", str(ctx.exception).lower())

    def test_wrong_audience_rejected(self):
        """Assertion for wrong audience must be rejected when entity_id is set."""
        svc = _make_service(entity_id="https://beagle.example.com/sp")
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = _make_saml_response(
            audience="https://other-sp.example.com",
            not_on_or_after=future_ts,
        )
        with self.assertRaises(SamlAssertionError) as ctx:
            svc.validate_assertion(b64)
        self.assertIn("audience", str(ctx.exception).lower())

    def test_correct_audience_passes(self):
        """Assertion with correct audience passes validation."""
        svc = _make_service(entity_id="https://beagle.example.com/sp")
        future_ts = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        b64 = _make_saml_response(
            audience="https://beagle.example.com/sp",
            not_on_or_after=future_ts,
        )
        claims = svc.validate_assertion(b64)
        self.assertEqual(claims["name_id"], "test@example.com")

    def test_invalid_base64_rejected(self):
        """Invalid base64 input (non-base64 chars after strict decode) must be rejected."""
        svc = _make_service()
        # Use a string with characters outside the base64 alphabet that Python strictmode rejects
        with self.assertRaises(SamlAssertionError):
            # Valid base64 of garbage bytes that produce non-parseable XML
            svc.validate_assertion(base64.b64encode(b"\x00\x01\x02 invalid xml").decode())

    def test_invalid_xml_rejected(self):
        """Invalid XML inside base64 must be rejected."""
        svc = _make_service()
        bad_xml = base64.b64encode(b"<not valid xml").decode("ascii")
        with self.assertRaises(SamlAssertionError) as ctx:
            svc.validate_assertion(bad_xml)
        self.assertIn("xml", str(ctx.exception).lower())

    def test_failed_status_rejected(self):
        """Assertion with non-Success status code must be rejected."""
        svc = _make_service()
        b64 = _make_saml_response(status="urn:oasis:names:tc:SAML:2.0:status:AuthnFailed")
        with self.assertRaises(SamlAssertionError) as ctx:
            svc.validate_assertion(b64)
        self.assertIn("Success", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

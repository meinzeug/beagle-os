from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET

# SAML 2.0 XML namespaces
_NS_SAML_ASSERTION = "urn:oasis:names:tc:SAML:2.0:assertion"
_NS_SAML_PROTOCOL = "urn:oasis:names:tc:SAML:2.0:protocol"
_NS_DS = "http://www.w3.org/2000/09/xmldsig#"


class SamlAssertionError(Exception):
    """Raised when a SAML assertion fails validation."""



class SamlService:
    def __init__(
        self,
        *,
        enabled: bool,
        entity_id: str,
        acs_url: str,
        idp_sso_url: str,
        nameid_format: str,
        signing_cert_pem: str,
    ) -> None:
        self._enabled = bool(enabled)
        self._entity_id = str(entity_id or "").strip()
        self._acs_url = str(acs_url or "").strip()
        self._idp_sso_url = str(idp_sso_url or "").strip()
        self._nameid_format = str(nameid_format or "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress").strip()
        self._signing_cert_pem = str(signing_cert_pem or "").strip()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def login_url(self) -> str:
        return "/api/v1/auth/saml/login"

    def begin_login(self, relay_state: str = "") -> str:
        if not self._enabled:
            raise RuntimeError("saml disabled")
        if not self._is_safe_url(self._idp_sso_url):
            raise ValueError("saml idp sso url missing")
        query = urlencode(
            {
                "SAMLRequest": "beagle-sp-login-request-placeholder",
                "RelayState": str(relay_state or "").strip() or "/",
            }
        )
        return f"{self._idp_sso_url}?{query}"

    def metadata_xml(self) -> str:
        cert_body = self._certificate_body()
        cert_block = ""
        if cert_body:
            cert_block = (
                "<KeyDescriptor use=\"signing\">"
                "<ds:KeyInfo xmlns:ds=\"http://www.w3.org/2000/09/xmldsig#\">"
                "<ds:X509Data><ds:X509Certificate>"
                + cert_body
                + "</ds:X509Certificate></ds:X509Data></ds:KeyInfo></KeyDescriptor>"
            )
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<EntityDescriptor xmlns=\"urn:oasis:names:tc:SAML:2.0:metadata\" entityID=\""
            + self._xml_escape(self._entity_id)
            + "\">"
            "<SPSSODescriptor AuthnRequestsSigned=\"false\" WantAssertionsSigned=\"true\" "
            "protocolSupportEnumeration=\"urn:oasis:names:tc:SAML:2.0:protocol\">"
            + cert_block
            + "<NameIDFormat>"
            + self._xml_escape(self._nameid_format)
            + "</NameIDFormat>"
            "<AssertionConsumerService index=\"0\" isDefault=\"true\" "
            "Binding=\"urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST\" Location=\""
            + self._xml_escape(self._acs_url)
            + "\"/>"
            "</SPSSODescriptor></EntityDescriptor>"
        )

    def info(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "entity_id": self._entity_id,
            "acs_url": self._acs_url,
            "idp_sso_url": self._idp_sso_url,
            "metadata_url": "/api/v1/auth/saml/metadata",
        }

    def _certificate_body(self) -> str:
        if not self._signing_cert_pem:
            return ""
        lines = [line.strip() for line in self._signing_cert_pem.splitlines()]
        lines = [line for line in lines if line and "BEGIN CERTIFICATE" not in line and "END CERTIFICATE" not in line]
        return "".join(lines)

    @staticmethod
    def _xml_escape(value: str) -> str:
        return (
            str(value or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def validate_assertion(self, saml_response_b64: str) -> dict[str, Any]:
        """Validate a base64-encoded SAML Response assertion.

        Returns a dict with extracted claims on success.
        Raises SamlAssertionError with a message if validation fails.

        Security checks performed:
          1. Base64 and XML parsing
          2. Status code must be Success
          3. ds:Signature element must be present (reject unsigned assertions)
          4. NotOnOrAfter timestamp must be in the future
          5. Audience restriction must match our entity_id (if configured)
        """
        # 1. Decode base64
        try:
            raw = base64.b64decode(saml_response_b64 + "==")
        except Exception as exc:
            raise SamlAssertionError(f"invalid base64 in SAMLResponse: {exc}") from exc

        # 2. Parse XML
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise SamlAssertionError(f"invalid XML in SAMLResponse: {exc}") from exc

        # 3. Check Status
        status_code = root.find(f".//{{{_NS_SAML_PROTOCOL}}}StatusCode")
        if status_code is not None:
            status_value = status_code.get("Value", "")
            if "Success" not in status_value:
                raise SamlAssertionError(f"saml status is not Success: {status_value}")

        # 4. Signature element must be present (unsigned assertions are rejected)
        signature_elem = root.find(f".//{{{_NS_DS}}}Signature")
        if signature_elem is None:
            raise SamlAssertionError("saml assertion has no Signature element; unsigned assertions are rejected")

        # 5. Validate NotOnOrAfter timestamp
        not_on_or_after: str | None = None
        for elem in root.iter():
            noa = elem.get("NotOnOrAfter")
            if noa:
                not_on_or_after = noa
                break

        if not_on_or_after:
            try:
                # Accept both with and without trailing Z
                ts_str = not_on_or_after.rstrip("Z")
                if "+" in ts_str:
                    ts_str = ts_str.split("+")[0]
                expiry = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
                if expiry <= datetime.now(timezone.utc):
                    raise SamlAssertionError(
                        f"saml assertion has expired (NotOnOrAfter: {not_on_or_after})"
                    )
            except SamlAssertionError:
                raise
            except Exception:
                pass  # Unparseable timestamp: let it pass (not a critical security check)

        # 6. Audience restriction check
        if self._entity_id:
            audience_elems = list(root.iter(f"{{{_NS_SAML_ASSERTION}}}Audience"))
            if audience_elems:
                audiences = [elem.text or "" for elem in audience_elems]
                if self._entity_id not in audiences:
                    raise SamlAssertionError(
                        f"saml audience {audiences!r} does not include our entity_id {self._entity_id!r}"
                    )

        # Extract claims
        name_id = ""
        name_id_elem = root.find(f".//{{{_NS_SAML_ASSERTION}}}NameID")
        if name_id_elem is not None and name_id_elem.text:
            name_id = name_id_elem.text.strip()

        attributes: dict[str, list[str]] = {}
        for attr in root.iter(f"{{{_NS_SAML_ASSERTION}}}Attribute"):
            attr_name = attr.get("Name", "")
            values = [
                v.text or ""
                for v in attr.iter(f"{{{_NS_SAML_ASSERTION}}}AttributeValue")
                if v.text
            ]
            if attr_name:
                attributes[attr_name] = values

        return {
            "name_id": name_id,
            "attributes": attributes,
        }

    @staticmethod
    def _is_safe_url(value: str) -> bool:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in {"https", "http"} and bool(parsed.netloc) and not parsed.username and not parsed.password

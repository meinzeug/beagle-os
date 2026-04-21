from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlparse


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

    @staticmethod
    def _is_safe_url(value: str) -> bool:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in {"https", "http"} and bool(parsed.netloc) and not parsed.username and not parsed.password

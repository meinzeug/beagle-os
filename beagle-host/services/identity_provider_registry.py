from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


class IdentityProviderRegistryService:
    """Loads and normalizes configured login providers for the Web Console."""

    def __init__(
        self,
        *,
        load_json_file: Callable[[Path, Any], Any],
        registry_file: Path,
        oidc_auth_url: str,
        saml_login_url: str,
        public_manager_url: str,
    ) -> None:
        self._load_json_file = load_json_file
        self._registry_file = Path(registry_file)
        self._oidc_auth_url = str(oidc_auth_url or "").strip()
        self._saml_login_url = str(saml_login_url or "").strip()
        self._public_manager_url = str(public_manager_url or "").strip()

    def list_providers(self) -> list[dict[str, Any]]:
        configured = self._load_from_registry_file()
        if configured:
            return configured

        providers = [
            {
                "id": "local",
                "type": "local",
                "label": "Lokaler Account",
                "description": "Benutzername + Passwort (Break-Glass).",
                "mode": "password",
                "enabled": True,
                "login_url": "",
            }
        ]

        oidc_url = self._normalize_url(self._oidc_auth_url)
        if oidc_url:
            providers.append(
                {
                    "id": "oidc",
                    "type": "oidc",
                    "label": "OIDC",
                    "description": "Single Sign-On ueber OpenID Connect.",
                    "mode": "redirect",
                    "enabled": True,
                    "login_url": oidc_url,
                }
            )

        saml_url = self._normalize_url(self._saml_login_url)
        if saml_url:
            providers.append(
                {
                    "id": "saml",
                    "type": "saml",
                    "label": "SAML",
                    "description": "Enterprise-Login ueber SAML 2.0.",
                    "mode": "redirect",
                    "enabled": True,
                    "login_url": saml_url,
                }
            )

        return providers

    def payload(self) -> dict[str, Any]:
        return {
            "ok": True,
            "providers": self.list_providers(),
            "provider_hint": self._provider_hint_url(),
        }

    def _load_from_registry_file(self) -> list[dict[str, Any]]:
        raw = self._load_json_file(self._registry_file, {})
        if not isinstance(raw, dict):
            return []
        raw_items = raw.get("providers")
        if not isinstance(raw_items, list):
            return []

        providers: list[dict[str, Any]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            provider_type = str(raw_item.get("type") or raw_item.get("id") or "").strip().lower()
            if provider_type not in {"local", "oidc", "saml"}:
                continue
            provider_id = str(raw_item.get("id") or provider_type).strip().lower()
            label = str(raw_item.get("label") or provider_type.upper()).strip()
            description = str(raw_item.get("description") or "").strip()
            enabled = bool(raw_item.get("enabled", True))
            login_url = self._normalize_url(str(raw_item.get("login_url") or "").strip())
            mode = "password" if provider_type == "local" else "redirect"
            if mode == "redirect" and not login_url:
                enabled = False
            providers.append(
                {
                    "id": provider_id,
                    "type": provider_type,
                    "label": label,
                    "description": description,
                    "mode": mode,
                    "enabled": enabled,
                    "login_url": login_url,
                }
            )

        if not any(item.get("type") == "local" for item in providers):
            providers.insert(
                0,
                {
                    "id": "local",
                    "type": "local",
                    "label": "Lokaler Account",
                    "description": "Benutzername + Passwort (Break-Glass).",
                    "mode": "password",
                    "enabled": True,
                    "login_url": "",
                },
            )
        return providers

    def _provider_hint_url(self) -> str:
        if not self._public_manager_url:
            return ""
        return f"{self._public_manager_url.rstrip('/')}/#panel=overview&provider=<provider-id>"

    @staticmethod
    def _normalize_url(value: str) -> str:
        parsed = urlparse(str(value or "").strip())
        if parsed.scheme not in {"http", "https"}:
            return ""
        if not parsed.netloc:
            return ""
        if parsed.username or parsed.password:
            return ""
        return parsed.geturl()

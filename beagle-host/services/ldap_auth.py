from __future__ import annotations

from typing import Any


class LdapAuthService:
    def __init__(
        self,
        *,
        server_uri: str,
        bind_dn_template: str,
        default_role: str = "viewer",
        start_tls: bool = False,
        ca_cert_file: str = "",
    ) -> None:
        self._server_uri = str(server_uri or "").strip()
        self._bind_dn_template = str(bind_dn_template or "").strip()
        self._default_role = str(default_role or "viewer").strip().lower() or "viewer"
        self._start_tls = bool(start_tls)
        self._ca_cert_file = str(ca_cert_file or "").strip()

    def configured(self) -> bool:
        return bool(self._server_uri and self._bind_dn_template and "{username}" in self._bind_dn_template)

    def authenticate(self, *, username: str, password: str) -> dict[str, Any] | None:
        user_name = str(username or "").strip()
        passwd = str(password or "")
        if not self.configured() or not user_name or not passwd:
            return None
        try:
            import ldap3  # type: ignore[import-not-found]
        except Exception:
            return None

        tls = None
        if self._ca_cert_file:
            try:
                tls = ldap3.Tls(ca_certs_file=self._ca_cert_file)
            except Exception:
                tls = None

        server = ldap3.Server(self._server_uri, tls=tls, get_info=ldap3.NONE)
        bind_dn = self._bind_dn_template.format(username=user_name)
        connection = ldap3.Connection(server, user=bind_dn, password=passwd, auto_bind=False)
        try:
            if self._start_tls:
                connection.open()
                connection.start_tls()
            if not connection.bind():
                return None
            return {
                "username": user_name,
                "role": self._default_role,
                "auth_source": "ldap",
            }
        except Exception:
            return None
        finally:
            try:
                connection.unbind()
            except Exception:
                pass

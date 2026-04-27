"""Installer template patching helpers.

This service owns the canonical shell and PowerShell template rewrites used by
generated installer artifacts. The control plane keeps thin wrappers so
existing helper signatures stay stable while template-patching semantics leave
the entrypoint.
"""

from __future__ import annotations

import re


class InstallerTemplatePatchService:
    @staticmethod
    def shell_double_quoted(value: str) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("$", "\\$")
            .replace("`", "\\`")
        )

    @staticmethod
    def ensure_shell_installer_log_defaults(script_text: str) -> str:
        if re.search(r'^INSTALLER_LOG_URL="\$\{BEAGLE_INSTALLER_LOG_URL:-[^"]*}"$', script_text, flags=re.MULTILINE):
            return script_text
        marker = 'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-'
        lines = script_text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith(marker):
                insert_at = index + 1
                lines[insert_at:insert_at] = [
                    'INSTALLER_LOG_URL="${BEAGLE_INSTALLER_LOG_URL:-}"',
                    'INSTALLER_LOG_TOKEN="${BEAGLE_INSTALLER_LOG_TOKEN:-}"',
                    'INSTALLER_LOG_SESSION_ID="${BEAGLE_INSTALLER_LOG_SESSION_ID:-}"',
                ]
                suffix = "\n" if script_text.endswith("\n") else ""
                return "\n".join(lines) + suffix
        raise ValueError("failed to patch installer template for missing installer log insertion marker")

    def patch_installer_defaults(
        self,
        script_text: str,
        preset_name: str,
        preset_b64: str,
        installer_iso_url: str,
        installer_bootstrap_url: str,
        installer_payload_url: str,
        writer_variant: str,
        installer_log_url: str = "",
        installer_log_token: str = "",
        installer_log_session_id: str = "",
    ) -> str:
        script_text = self.ensure_shell_installer_log_defaults(script_text)
        replacements = {
            r'^USB_WRITER_VARIANT="\$\{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-[^"]*}"$':
                f'USB_WRITER_VARIANT="${{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-{self.shell_double_quoted(writer_variant)}}}"',
            r'^INSTALLER_LOG_URL="\$\{BEAGLE_INSTALLER_LOG_URL:-[^"]*}"$':
                f'INSTALLER_LOG_URL="${{BEAGLE_INSTALLER_LOG_URL:-{self.shell_double_quoted(installer_log_url)}}}"',
            r'^INSTALLER_LOG_TOKEN="\$\{BEAGLE_INSTALLER_LOG_TOKEN:-[^"]*}"$':
                f'INSTALLER_LOG_TOKEN="${{BEAGLE_INSTALLER_LOG_TOKEN:-{self.shell_double_quoted(installer_log_token)}}}"',
            r'^INSTALLER_LOG_SESSION_ID="\$\{BEAGLE_INSTALLER_LOG_SESSION_ID:-[^"]*}"$':
                f'INSTALLER_LOG_SESSION_ID="${{BEAGLE_INSTALLER_LOG_SESSION_ID:-{self.shell_double_quoted(installer_log_session_id)}}}"',
            r'^PVE_THIN_CLIENT_PRESET_NAME="\$\{PVE_THIN_CLIENT_PRESET_NAME:-[^"]*}"$':
                f'PVE_THIN_CLIENT_PRESET_NAME="${{PVE_THIN_CLIENT_PRESET_NAME:-{self.shell_double_quoted(preset_name)}}}"',
            r'^PVE_THIN_CLIENT_PRESET_B64="\$\{PVE_THIN_CLIENT_PRESET_B64:-[^"]*}"$':
                f'PVE_THIN_CLIENT_PRESET_B64="${{PVE_THIN_CLIENT_PRESET_B64:-{self.shell_double_quoted(preset_b64)}}}"',
            r'^RELEASE_ISO_URL="\$\{RELEASE_ISO_URL:-[^"]*}"$':
                f'RELEASE_ISO_URL="${{RELEASE_ISO_URL:-{self.shell_double_quoted(installer_iso_url)}}}"',
            r'^RELEASE_BOOTSTRAP_URL="\$\{RELEASE_BOOTSTRAP_URL:-[^"]*}"$':
                f'RELEASE_BOOTSTRAP_URL="${{RELEASE_BOOTSTRAP_URL:-{self.shell_double_quoted(installer_bootstrap_url)}}}"',
            r'^RELEASE_PAYLOAD_URL="\$\{RELEASE_PAYLOAD_URL:-[^"]*}"$':
                f'RELEASE_PAYLOAD_URL="${{RELEASE_PAYLOAD_URL:-{self.shell_double_quoted(installer_payload_url)}}}"',
            r'^INSTALL_PAYLOAD_URL="\$\{INSTALL_PAYLOAD_URL:-[^"]*}"$':
                f'INSTALL_PAYLOAD_URL="${{INSTALL_PAYLOAD_URL:-{self.shell_double_quoted(installer_payload_url)}}}"',
            r'^BOOTSTRAP_DISABLE_CACHE="\$\{PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-[^"]*}"$':
                'BOOTSTRAP_DISABLE_CACHE="${PVE_DCV_BOOTSTRAP_DISABLE_CACHE:-1}"',
        }
        updated = script_text
        for pattern, replacement in replacements.items():
            updated, count = re.subn(pattern, replacement, updated, count=1, flags=re.MULTILINE)
            if count != 1:
                raise ValueError(f"failed to patch installer template for pattern: {pattern}")
        return updated

    @staticmethod
    def patch_windows_installer_defaults(
        script_text: str,
        preset_name: str,
        preset_b64: str,
        installer_iso_url: str,
        writer_variant: str,
        installer_log_url: str = "",
        installer_log_token: str = "",
        installer_log_session_id: str = "",
    ) -> str:
        return (
            script_text
            .replace("__BEAGLE_DEFAULT_RELEASE_ISO_URL__", str(installer_iso_url or ""))
            .replace("__BEAGLE_DEFAULT_WRITER_VARIANT__", str(writer_variant or ""))
            .replace("__BEAGLE_DEFAULT_PRESET_NAME__", str(preset_name or ""))
            .replace("__BEAGLE_DEFAULT_PRESET_B64__", str(preset_b64 or ""))
            .replace("__BEAGLE_DEFAULT_INSTALLER_LOG_URL__", str(installer_log_url or ""))
            .replace("__BEAGLE_DEFAULT_INSTALLER_LOG_TOKEN__", str(installer_log_token or ""))
            .replace("__BEAGLE_DEFAULT_INSTALLER_LOG_SESSION_ID__", str(installer_log_session_id or ""))
        )

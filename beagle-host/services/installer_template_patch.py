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

    def patch_installer_defaults(
        self,
        script_text: str,
        preset_name: str,
        preset_b64: str,
        installer_iso_url: str,
        installer_bootstrap_url: str,
        installer_payload_url: str,
        writer_variant: str,
    ) -> str:
        replacements = {
            r'^USB_WRITER_VARIANT="\$\{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-[^"]*}"$':
                f'USB_WRITER_VARIANT="${{PVE_THIN_CLIENT_USB_WRITER_VARIANT:-{self.shell_double_quoted(writer_variant)}}}"',
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
    ) -> str:
        return (
            script_text
            .replace("__BEAGLE_DEFAULT_RELEASE_ISO_URL__", str(installer_iso_url or ""))
            .replace("__BEAGLE_DEFAULT_PRESET_NAME__", str(preset_name or ""))
            .replace("__BEAGLE_DEFAULT_PRESET_B64__", str(preset_b64 or ""))
        )

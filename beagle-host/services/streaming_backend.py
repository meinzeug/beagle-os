from __future__ import annotations

from dataclasses import dataclass


_VALID_BACKENDS = {"beagle-stream-server", "apollo"}


@dataclass(frozen=True)
class StreamingBackendDecision:
    guest_os: str
    backend: str
    fallback_backend: str
    virtual_display_supported: bool
    reason: str


class StreamingBackendService:
    """Selects a streaming backend based on guest OS and optional backend preference."""

    def __init__(
        self,
        *,
        default_linux_backend: str = "beagle-stream-server",
        default_windows_backend: str = "apollo",
        fallback_backend: str = "beagle-stream-server",
        allow_apollo_on_linux: bool = False,
    ) -> None:
        self._default_linux_backend = self._normalize_backend(default_linux_backend, default="beagle-stream-server")
        self._default_windows_backend = self._normalize_backend(default_windows_backend, default="apollo")
        self._fallback_backend = self._normalize_backend(fallback_backend, default="beagle-stream-server")
        self._allow_apollo_on_linux = bool(allow_apollo_on_linux)

    @staticmethod
    def _normalize_guest_os(guest_os: str) -> str:
        value = str(guest_os or "").strip().lower()
        if value in {"linux", "ubuntu", "debian"}:
            return "linux"
        if value in {"windows", "win", "win11", "win10"}:
            return "windows"
        return "unknown"

    @staticmethod
    def _normalize_backend(backend: str, *, default: str) -> str:
        value = str(backend or "").strip().lower()
        if value in _VALID_BACKENDS:
            return value
        return default

    def _virtual_display_supported(self, guest_os: str, backend: str) -> bool:
        if backend == "beagle-stream-server":
            return guest_os == "linux"
        if backend == "apollo":
            return guest_os == "windows"
        return False

    def select_backend(self, *, guest_os: str, preferred_backend: str = "") -> StreamingBackendDecision:
        normalized_os = self._normalize_guest_os(guest_os)
        requested = str(preferred_backend or "").strip().lower()

        if requested and requested not in _VALID_BACKENDS:
            requested = ""

        if normalized_os == "windows":
            selected = requested or self._default_windows_backend
            return StreamingBackendDecision(
                guest_os=normalized_os,
                backend=selected,
                fallback_backend=self._fallback_backend,
                virtual_display_supported=self._virtual_display_supported(normalized_os, selected),
                reason="windows_default" if not requested else "preferred_backend",
            )

        if normalized_os == "linux":
            if requested == "apollo" and not self._allow_apollo_on_linux:
                return StreamingBackendDecision(
                    guest_os=normalized_os,
                    backend=self._default_linux_backend,
                    fallback_backend=self._fallback_backend,
                    virtual_display_supported=self._virtual_display_supported(normalized_os, self._default_linux_backend),
                    reason="apollo_linux_not_supported",
                )
            selected = requested or self._default_linux_backend
            return StreamingBackendDecision(
                guest_os=normalized_os,
                backend=selected,
                fallback_backend=self._fallback_backend,
                virtual_display_supported=self._virtual_display_supported(normalized_os, selected),
                reason="linux_default" if not requested else "preferred_backend",
            )

        selected = requested or self._fallback_backend
        return StreamingBackendDecision(
            guest_os=normalized_os,
            backend=selected,
            fallback_backend=self._fallback_backend,
            virtual_display_supported=False,
            reason="unknown_guest_os",
        )

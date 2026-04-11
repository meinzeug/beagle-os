"""Shared pure utility helpers for the host control plane.

This service owns the small reusable formatting and secret-generation helpers
that were previously free functions in the control-plane entrypoint. Keeping
them here makes the helpers testable and lets extracted services depend on a
stable utility seam instead of the HTTP runtime module.
"""

from __future__ import annotations

import re
from typing import Callable


class UtilitySupportService:
    def __init__(
        self,
        *,
        choice: Callable[[str], str],
        randbelow: Callable[[int], int],
    ) -> None:
        self._choice = choice
        self._randbelow = randbelow
        self._secret_alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    def safe_slug(self, value: str, default: str = "item") -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-")
        return cleaned or default

    def random_secret(self, length: int = 24) -> str:
        target_length = max(12, int(length))
        return "".join(self._choice(self._secret_alphabet) for _ in range(target_length))

    def random_pin(self) -> str:
        return f"{self._randbelow(10000):04d}"

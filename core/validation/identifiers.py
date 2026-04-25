"""Input validators for common Beagle identifiers.

All validators raise ``ValueError`` on invalid input and return the
(possibly coerced) validated value on success.

Use these at API/service boundaries before passing values to
subprocess commands or file paths.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# VM / resource identifiers
# ---------------------------------------------------------------------------

_RE_VMID = re.compile(r"^[0-9]{1,9}$")
_RE_NETWORK_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")
_RE_POOL_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")
_RE_NODE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.\-_]{0,63}$")
_RE_DEVICE_ID = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")
_RE_ZONE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")
_RE_SECRET_NAME = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def validate_vmid(value: str | int) -> int:
    """Validate and return a VM ID as int.

    Accepts integers or string representations.
    Range: 1 – 999_999_999.

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_VMID.match(s):
        raise ValueError(
            f"Invalid VM ID {value!r}. Must be 1-9 digits (e.g. 100, 200)."
        )
    n = int(s)
    if n < 1:
        raise ValueError(f"VM ID must be >= 1, got {n}")
    return n


def validate_network_name(value: str) -> str:
    """Validate a network/bridge name (Linux interface naming constraints).

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_NETWORK_NAME.match(s):
        raise ValueError(
            f"Invalid network name {value!r}. "
            "Must start with [a-zA-Z0-9], contain only [a-zA-Z0-9_-], max 63 chars."
        )
    return s


def validate_pool_id(value: str) -> str:
    """Validate a pool identifier.

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_POOL_ID.match(s):
        raise ValueError(
            f"Invalid pool ID {value!r}. "
            "Must start with [a-zA-Z0-9], contain only [a-zA-Z0-9_-], max 64 chars."
        )
    return s


def validate_node_id(value: str) -> str:
    """Validate a cluster node ID (hostname-like).

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_NODE_ID.match(s):
        raise ValueError(
            f"Invalid node ID {value!r}. "
            "Must start with [a-zA-Z0-9], contain only [a-zA-Z0-9._-], max 64 chars."
        )
    return s


def validate_device_id(value: str) -> str:
    """Validate a device ID (TPM-bound stable identifier).

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_DEVICE_ID.match(s):
        raise ValueError(
            f"Invalid device ID {value!r}. "
            "Must contain only [a-zA-Z0-9_-], max 128 chars."
        )
    return s


def validate_zone_id(value: str) -> str:
    """Validate a network zone ID.

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_ZONE_ID.match(s):
        raise ValueError(
            f"Invalid zone ID {value!r}. "
            "Must start with [a-zA-Z0-9], contain only [a-zA-Z0-9_-], max 64 chars."
        )
    return s


def validate_secret_name(value: str) -> str:
    """Validate a secret name.

    Raises ValueError for invalid input.
    """
    s = str(value).strip()
    if not _RE_SECRET_NAME.match(s):
        raise ValueError(
            f"Invalid secret name {value!r}. "
            "Must contain only [a-zA-Z0-9_-], max 64 chars."
        )
    return s

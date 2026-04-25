"""Unit tests for core.validation.identifiers."""
from __future__ import annotations

import pytest

from core.validation.identifiers import (
    validate_device_id,
    validate_network_name,
    validate_node_id,
    validate_pool_id,
    validate_secret_name,
    validate_vmid,
    validate_zone_id,
)


# ---------------------------------------------------------------------------
# validate_vmid
# ---------------------------------------------------------------------------

class TestValidateVmid:
    def test_valid_int(self) -> None:
        assert validate_vmid(100) == 100

    def test_valid_string(self) -> None:
        assert validate_vmid("200") == 200

    def test_max_valid(self) -> None:
        assert validate_vmid(999999999) == 999_999_999

    def test_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid(-1)

    def test_float_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid("1.5")

    def test_path_traversal_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid("../../etc/passwd")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid("")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_vmid("1234567890")  # 10 digits


# ---------------------------------------------------------------------------
# validate_network_name
# ---------------------------------------------------------------------------

class TestValidateNetworkName:
    def test_valid(self) -> None:
        assert validate_network_name("vmbr0") == "vmbr0"
        assert validate_network_name("beagle-net") == "beagle-net"
        assert validate_network_name("A") == "A"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_network_name("")

    def test_starts_with_dash_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_network_name("-bad")

    def test_special_chars_raises(self) -> None:
        for bad in ["; rm -rf /", "net name", "net/name", "net\x00name"]:
            with pytest.raises(ValueError):
                validate_network_name(bad)

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_network_name("a" * 64)


# ---------------------------------------------------------------------------
# validate_pool_id
# ---------------------------------------------------------------------------

class TestValidatePoolId:
    def test_valid(self) -> None:
        assert validate_pool_id("pool-1") == "pool-1"
        assert validate_pool_id("VDI_Pool_A") == "VDI_Pool_A"

    def test_injection_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_pool_id("pool'; DROP TABLE pools;--")


# ---------------------------------------------------------------------------
# validate_node_id
# ---------------------------------------------------------------------------

class TestValidateNodeId:
    def test_valid(self) -> None:
        assert validate_node_id("srv1") == "srv1"
        assert validate_node_id("srv1.beagle-os.com") == "srv1.beagle-os.com"

    def test_injection_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_node_id("srv1; rm -rf /")


# ---------------------------------------------------------------------------
# validate_device_id
# ---------------------------------------------------------------------------

class TestValidateDeviceId:
    def test_valid(self) -> None:
        assert validate_device_id("abc-123_DEF") == "abc-123_DEF"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_device_id("")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_device_id("a" * 129)

    def test_path_traversal_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_device_id("../../etc/shadow")


# ---------------------------------------------------------------------------
# validate_secret_name
# ---------------------------------------------------------------------------

class TestValidateSecretName:
    def test_valid(self) -> None:
        assert validate_secret_name("api_token") == "api_token"

    def test_space_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_secret_name("api token")

    def test_too_long_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_secret_name("a" * 65)

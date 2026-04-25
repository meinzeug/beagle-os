"""Tests for Seed Config Parser (GoEnterprise Plan 08, Schritt 2)."""
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "server-installer") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "server-installer"))

from seed_config_parser import SeedConfigParser, SeedConfig


MINIMAL_YAML = """\
hostname: beagle-node-01
disk: /dev/sda
raid: 1
network:
  interface: eth0
  mode: dhcp
"""

STATIC_YAML = """\
hostname: beagle-srv
disk: /dev/nvme0n1
raid: 0
locale: de_DE.UTF-8
timezone: Europe/Berlin
network:
  interface: enp3s0
  mode: static
  ip: 192.168.10.20/24
  gateway: 192.168.10.1
  dns:
    - 192.168.10.1
    - 8.8.8.8
cluster:
  join: 192.168.10.5
  token: abc123secret
"""


def parse(yaml_text: str) -> SeedConfig:
    return SeedConfigParser().parse(yaml_text)


def test_parse_minimal_yaml():
    cfg = parse(MINIMAL_YAML)
    assert cfg.hostname == "beagle-node-01"
    assert cfg.disk == "/dev/sda"
    assert cfg.raid == 1
    assert cfg.network.mode == "dhcp"


def test_parse_static_network():
    cfg = parse(STATIC_YAML)
    assert cfg.network.mode == "static"
    assert cfg.network.ip == "192.168.10.20/24"
    assert cfg.network.gateway == "192.168.10.1"
    assert "192.168.10.1" in cfg.network.dns


def test_parse_locale_and_timezone():
    cfg = parse(STATIC_YAML)
    assert cfg.locale == "de_DE.UTF-8"
    assert cfg.timezone == "Europe/Berlin"


def test_parse_cluster_config():
    cfg = parse(STATIC_YAML)
    assert cfg.cluster.join == "192.168.10.5"
    assert cfg.cluster.token == "abc123secret"


def test_parse_from_file(tmp_path):
    f = tmp_path / "seed.yaml"
    f.write_text(MINIMAL_YAML)
    cfg = SeedConfigParser().parse_file(f)
    assert cfg.hostname == "beagle-node-01"


def test_validate_ok():
    cfg = parse(MINIMAL_YAML)
    errors = SeedConfigParser().validate(cfg)
    assert errors == []


def test_validate_invalid_hostname():
    cfg = parse(MINIMAL_YAML)
    cfg.hostname = "invalid hostname!"
    errors = SeedConfigParser().validate(cfg)
    assert any("hostname" in e for e in errors)


def test_validate_invalid_disk():
    cfg = parse(MINIMAL_YAML)
    cfg.disk = "sda"  # missing /dev/
    errors = SeedConfigParser().validate(cfg)
    assert any("disk" in e for e in errors)


def test_validate_invalid_raid_level():
    cfg = parse(MINIMAL_YAML)
    cfg.raid = 3
    errors = SeedConfigParser().validate(cfg)
    assert any("raid" in e for e in errors)


def test_validate_static_without_gateway():
    cfg = parse(STATIC_YAML)
    cfg.network.gateway = ""
    errors = SeedConfigParser().validate(cfg)
    assert any("gateway" in e for e in errors)


def test_validate_static_invalid_cidr():
    cfg = parse(STATIC_YAML)
    cfg.network.ip = "192.168.1.1"  # missing prefix length
    errors = SeedConfigParser().validate(cfg)
    assert any("ip" in e for e in errors)


def test_default_locale():
    cfg = parse(MINIMAL_YAML)
    assert cfg.locale == "en_US.UTF-8"


def test_comments_ignored():
    yaml = "# full comment\nhostname: test-host\ndisk: /dev/sda\nraid: 1\nnetwork:\n  mode: dhcp\n"
    cfg = parse(yaml)
    assert cfg.hostname == "test-host"

import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/ops/beagle-public-tls-heal'


def load():
    loader = importlib.machinery.SourceFileLoader('beagle_tls_heal_test', str(SCRIPT))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def test_route_repair_preserves_existing_vhost_and_is_idempotent(tmp_path, monkeypatch):
    module = load()
    path = tmp_path / 'vhost_ssl.conf'
    original = 'ProxyPass / http://127.0.0.1:3000/\n'
    path.write_text(original)
    calls = []
    monkeypatch.setattr(module, 'run', lambda args, **kwargs: calls.append(args))
    assert module.ensure_route(path)
    assert path.read_text() == module.BLOCK + original
    assert not module.ensure_route(path)
    assert calls == [['apache2ctl', 'configtest'], ['systemctl', 'reload', 'apache2']]


def test_route_repair_restores_original_when_apache_config_invalid(tmp_path, monkeypatch):
    module = load()
    path = tmp_path / 'vhost_ssl.conf'
    path.write_text('existing config\n')
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, 'apache2ctl')
    monkeypatch.setattr(module, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        module.ensure_route(path)
    assert path.read_text() == 'existing config\n'


def test_unexpected_managed_block_is_not_overwritten(tmp_path):
    module = load()
    path = tmp_path / 'vhost_ssl.conf'
    path.write_text('unrelated\n' + module.BEGIN + 'modified\n')
    with pytest.raises(RuntimeError):
        module.ensure_route(path)
    assert path.read_text().endswith('modified\n')


def test_expiring_certificate_triggers_targeted_renewal_then_verification(tmp_path, monkeypatch):
    module = load()
    lock = tmp_path / 'lock'
    monkeypatch.setattr(module, 'open', lambda *_a, **_k: lock.open('w'), raising=False)
    monkeypatch.setattr(module, 'ensure_route', lambda: False)
    monkeypatch.setattr(module, 'local_domain_address', lambda: '192.0.2.1')
    monkeypatch.setattr(module, 'probe_route', lambda address: None)
    states = iter([True, False])
    monkeypatch.setattr(module, 'certificate_needs_renewal', lambda address: next(states))
    calls = []
    monkeypatch.setattr(module, 'run', lambda args, **kwargs: calls.append(args))
    module.main()
    assert calls == [[
        'plesk', 'ext', 'sslit', '--certificate', '-issue', '-domain',
        'beagle-os.com', '-secure-domain', '-secure-www', '-challenge', 'http',
    ]]


def test_current_certificate_is_not_reissued(tmp_path, monkeypatch):
    module = load()
    lock = tmp_path / 'lock'
    monkeypatch.setattr(module, 'open', lambda *_a, **_k: lock.open('w'), raising=False)
    monkeypatch.setattr(module, 'ensure_route', lambda: False)
    monkeypatch.setattr(module, 'local_domain_address', lambda: '192.0.2.1')
    monkeypatch.setattr(module, 'probe_route', lambda address: None)
    monkeypatch.setattr(module, 'certificate_needs_renewal', lambda address: False)
    monkeypatch.setattr(module, 'run', lambda *args, **kwargs: pytest.fail('unexpected renewal'))
    module.main()


def test_repair_moves_managed_route_ahead_of_later_proxy_rules(tmp_path, monkeypatch):
    module = load()
    path = tmp_path / 'vhost_ssl.conf'
    path.write_text('new proxy rule\n' + module.BLOCK + 'existing config\n')
    monkeypatch.setattr(module, 'run', lambda args, **kwargs: None)
    assert module.ensure_route(path)
    assert path.read_text() == module.BLOCK + 'new proxy rule\nexisting config\n'

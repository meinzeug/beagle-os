from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'scripts/install-beagle-proxy.sh'
SERVICE = ROOT / 'beagle-host/systemd/beagle-managed-tls-renew.service'
TIMER = ROOT / 'beagle-host/systemd/beagle-managed-tls-renew.timer'


def render_hook(tmp_path):
    source = INSTALLER.read_text()
    marker = 'cat > /etc/letsencrypt/renewal-hooks/deploy/beagle-tls.sh <<HOOK\n'
    body = source.split(marker, 1)[1].split('\nHOOK\n', 1)[0]
    env = dict(os.environ, SERVER_NAME='srv1.beagle-os.com', CERT_FILE=str(tmp_path / 'live.crt'), KEY_FILE=str(tmp_path / 'live.key'), BEAGLE_CONTROL_USER='beagle-manager')
    result = subprocess.run(['bash', '-c', 'cat <<HOOK\n' + body + '\nHOOK'], env=env, text=True, capture_output=True, check=True)
    path = tmp_path / 'hook'
    path.write_text(result.stdout)
    path.chmod(0o755)
    return path


def test_manager_certbot_has_own_periodic_renewal_and_deploy_hook():
    service = SERVICE.read_text()
    timer = TIMER.read_text()
    installer = INSTALLER.read_text()
    assert 'User=beagle-manager' in service
    assert '--config-dir /var/lib/beagle/beagle-manager/letsencrypt/config' in service
    assert '--deploy-hook /usr/local/sbin/beagle-managed-tls-deploy' in service
    assert 'Persistent=true' in timer
    assert 'systemctl enable --now beagle-managed-tls-renew.timer' in installer


def test_deploy_hook_uses_renewed_lineage_and_skips_other_domains(tmp_path):
    hook = render_hook(tmp_path)
    source = tmp_path / 'renewed'
    source.mkdir()
    (source / 'fullchain.pem').write_text('new certificate')
    (source / 'privkey.pem').write_text('new private key')
    cert, key = tmp_path / 'live.crt', tmp_path / 'live.key'
    cert.write_text('old certificate')
    key.write_text('old private key')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, content in {'id': 'echo 1000', 'sudo': 'exit 0'}.items():
        path = bin_dir / name
        path.write_text('#!/bin/sh\n' + content + '\n')
        path.chmod(0o755)
    env = dict(os.environ, PATH=f'{bin_dir}:' + os.environ['PATH'], RENEWED_LINEAGE=str(source), RENEWED_DOMAINS='other.example')
    subprocess.run([str(hook)], env=env, check=True)
    assert cert.read_text() == 'old certificate'
    env['RENEWED_DOMAINS'] = 'srv1.beagle-os.com'
    subprocess.run([str(hook)], env=env, check=True)
    assert cert.read_text() == 'new certificate'
    assert key.read_text() == 'new private key'
    assert (key.stat().st_mode & 0o777) == 0o600


def test_deploy_hook_restores_certificate_if_nginx_check_fails(tmp_path):
    hook = render_hook(tmp_path)
    source = tmp_path / 'renewed'
    source.mkdir()
    (source / 'fullchain.pem').write_text('new certificate')
    (source / 'privkey.pem').write_text('new private key')
    cert, key = tmp_path / 'live.crt', tmp_path / 'live.key'
    cert.write_text('old certificate')
    key.write_text('old private key')
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, content in {'id': 'echo 1000', 'sudo': 'exit 1'}.items():
        path = bin_dir / name
        path.write_text('#!/bin/sh\n' + content + '\n')
        path.chmod(0o755)
    env = dict(os.environ, PATH=f'{bin_dir}:' + os.environ['PATH'], RENEWED_LINEAGE=str(source), RENEWED_DOMAINS='srv1.beagle-os.com')
    assert subprocess.run([str(hook)], env=env, capture_output=True).returncode != 0
    assert cert.read_text() == 'old certificate'
    assert key.read_text() == 'old private key'

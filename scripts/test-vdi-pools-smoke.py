#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from core.virtualization.desktop_pool import DesktopPoolMode, DesktopPoolSpec
from core.virtualization.desktop_template import DesktopTemplateBuildSpec
from auth_session import AuthSessionService
from desktop_template_builder import DesktopTemplateBuilderService
from entitlement_service import EntitlementService
from pool_manager import PoolManagerService


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_equal(actual: object, expected: object, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    body = None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return int(exc.code), json.loads(raw or "{}")


def wait_for_server_ready(base_url: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error = "server did not become ready"
    while time.time() < deadline:
        try:
            status, payload = http_json("GET", f"{base_url}/api/v1/health")
            if status == 200 and payload.get("ok") is True:
                return
            last_error = f"unexpected status {status}: {payload}"
        except Exception as exc:  # pragma: no cover - readiness retry path
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(last_error)


def load_json_file(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def write_json_file(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_auth_service(data_dir: Path) -> AuthSessionService:
    return AuthSessionService(
        data_dir=data_dir,
        load_json_file=load_json_file,
        write_json_file=write_json_file,
        now=time.time,
        token_urlsafe=lambda length: f"tok-{length}-{int(time.time() * 1000000)}",
    )


def authorization_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def run_service_smoke(temp_dir: Path) -> str:
    qemu_img = shutil.which("qemu-img")
    if not qemu_img:
        raise RuntimeError("qemu-img is required for the VDI pool smoke test")

    source_disk = temp_dir / "golden-source.qcow2"
    subprocess.run([qemu_img, "create", "-f", "qcow2", str(source_disk), "128M"], check=True, capture_output=True)

    stop_calls: list[int] = []
    start_calls: list[int] = []
    reset_calls: list[tuple[int, str]] = []
    state_file = temp_dir / "desktop-pools-service.json"
    entitlement_state = temp_dir / "pool-entitlements-service.json"
    template_state = temp_dir / "desktop-templates.json"
    images_dir = temp_dir / "template-images"

    template_service = DesktopTemplateBuilderService(
        state_file=template_state,
        template_images_dir=images_dir,
        vm_disk_path_fn=lambda vmid: str(source_disk),
        stop_vm_fn=lambda vmid: stop_calls.append(int(vmid)),
        utcnow=lambda: "2026-04-22T12:00:00Z",
    )
    template = template_service.build_template(
        DesktopTemplateBuildSpec(
            template_id="tmpl-smoke",
            source_vmid=9000,
            template_name="Smoke Golden",
            os_family="windows",
            storage_pool="local",
            snapshot_name="sealed",
            backing_image="",
            cpu_cores=2,
            memory_mib=4096,
            software_packages=("xfce4", "sunshine"),
            notes="synthetic smoke image",
        )
    )
    assert_equal(template.template_id, "tmpl-smoke", "template builder should keep requested template id")
    assert_true(Path(template.backing_image).exists(), "template builder should export a backing image")
    assert_equal(stop_calls, [9000], "template builder should stop the source VM once")

    entitlement_service = EntitlementService(state_file=entitlement_state)
    assert_true(not entitlement_service.is_entitled("pool-smoke", user_id="outsider"), "outsider must not be entitled before setup")
    entitlement = entitlement_service.set_entitlements(
        "pool-smoke",
        users=["alice", "bob", "carol", "dave", "erin"],
        groups=["vdi-users"],
    )
    assert_equal(entitlement["users"], ["alice", "bob", "carol", "dave", "erin"], "entitlements should persist users in order")
    assert_true(entitlement_service.is_entitled("pool-smoke", user_id="alice"), "alice must be entitled after setup")
    assert_true(not entitlement_service.is_entitled("pool-smoke", user_id="mallory"), "mallory must remain unentitled")

    pool_service = PoolManagerService(
        state_file=state_file,
        utcnow=lambda: "2026-04-22T12:00:00Z",
        start_vm=lambda vmid: start_calls.append(int(vmid)),
        stop_vm=lambda vmid: None,
        reset_vm_to_template=lambda vmid, template_id: reset_calls.append((int(vmid), str(template_id))),
    )
    pool_service.create_pool(
        DesktopPoolSpec(
            pool_id="pool-smoke",
            template_id=template.template_id,
            mode=DesktopPoolMode.FLOATING_NON_PERSISTENT,
            min_pool_size=1,
            max_pool_size=5,
            warm_pool_size=5,
            cpu_cores=2,
            memory_mib=4096,
            storage_pool="local",
        )
    )
    for vmid in range(501, 506):
        pool_service.register_vm("pool-smoke", vmid)

    allocated_vmids: list[int] = []
    for user_id in ["alice", "bob", "carol", "dave", "erin"]:
        lease = pool_service.allocate_desktop("pool-smoke", user_id)
        allocated_vmids.append(int(lease.vmid))
        assert_equal(lease.state, "in_use", "allocated desktops must be marked in_use")
    assert_equal(sorted(allocated_vmids), [501, 502, 503, 504, 505], "five pool slots should allocate uniquely")
    assert_equal(sorted(start_calls), [501, 502, 503, 504, 505], "all five allocated desktops should invoke the start hook")

    recycle_started = time.monotonic()
    released = pool_service.release_desktop("pool-smoke", 501, "alice")
    assert_equal(released.state, "recycling", "non-persistent release should enter recycling")
    recycled = pool_service.recycle_desktop("pool-smoke", 501)
    recycle_elapsed = time.monotonic() - recycle_started
    assert_equal(recycled.state, "free", "recycled desktop should return to free state")
    assert_equal(recycled.user_id, "", "recycled desktop must clear the user assignment")
    assert_equal(reset_calls, [(501, template.template_id)], "recycle must reset the desktop against the template")
    assert_true(recycle_elapsed < 60.0, "non-persistent recycle should complete within 60 seconds")

    persistent_service = PoolManagerService(
        state_file=temp_dir / "desktop-pools-persistent.json",
        utcnow=lambda: "2026-04-22T12:00:00Z",
    )
    persistent_service.create_pool(
        DesktopPoolSpec(
            pool_id="pool-persistent",
            template_id=template.template_id,
            mode=DesktopPoolMode.FLOATING_PERSISTENT,
            min_pool_size=1,
            max_pool_size=2,
            warm_pool_size=1,
            cpu_cores=2,
            memory_mib=4096,
            storage_pool="local",
        )
    )
    persistent_service.register_vm("pool-persistent", 701)
    first = persistent_service.allocate_desktop("pool-persistent", "alice")
    persistent_service.release_desktop("pool-persistent", 701, "alice")
    second = persistent_service.allocate_desktop("pool-persistent", "alice")
    assert_equal(first.vmid, second.vmid, "persistent pool should reassign the same VM on the second login")

    return template.template_id


def run_api_smoke(temp_dir: Path, template_id: str) -> None:
    port = find_free_port()
    provider_state_dir = temp_dir / "provider-state"
    provider_state_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "BEAGLE_MANAGER_LISTEN_HOST": "127.0.0.1",
            "BEAGLE_MANAGER_LISTEN_PORT": str(port),
            "BEAGLE_MANAGER_DATA_DIR": str(temp_dir),
            "BEAGLE_MANAGER_ALLOW_LOCALHOST_NOAUTH": "1",
            "BEAGLE_BEAGLE_PROVIDER_STATE_DIR": str(provider_state_dir),
            "BEAGLE_AUTH_BOOTSTRAP_DISABLE": "1",
            "PYTHONPATH": f"{ROOT_DIR}:{SERVICES_DIR}:{env.get('PYTHONPATH', '')}".rstrip(":"),
        }
    )

    process = subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "beagle-host" / "bin" / "beagle-control-plane.py")],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        wait_for_server_ready(base_url)

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools",
            {
                "pool_id": "api-floating-5",
                "template_id": template_id,
                "mode": "floating_non_persistent",
                "min_pool_size": 1,
                "max_pool_size": 5,
                "warm_pool_size": 5,
                "cpu_cores": 2,
                "memory_mib": 4096,
                "storage_pool": "local",
                "enabled": True,
                "labels": ["smoke"],
            },
        )
        assert_equal(status, 201, "pool create route should return 201")
        assert_true(payload.get("ok") is True, "pool create route should return ok=true")

        for vmid in range(801, 806):
            status, payload = http_json(
                "POST",
                f"{base_url}/api/v1/pools/api-floating-5/vms",
                {"vmid": vmid},
            )
            assert_equal(status, 201, "vm registration route should return 201")
            assert_equal(payload.get("vmid"), vmid, "registered vmid should round-trip")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-floating-5/allocate",
            {"user_id": "mallory"},
        )
        assert_equal(status, 403, "unentitled pool allocation should be forbidden")
        assert_equal(payload.get("error"), "not entitled to this pool", "forbidden response should explain the entitlement failure")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-floating-5/entitlements",
            {"users": ["alice", "bob", "carol", "dave", "erin"]},
        )
        assert_equal(status, 200, "entitlement update route should return 200")
        assert_equal(payload.get("users"), ["alice", "bob", "carol", "dave", "erin"], "entitlement route should persist the allowed users")

        allocated_vmids: list[int] = []
        for user_id in ["alice", "bob", "carol", "dave", "erin"]:
            status, payload = http_json(
                "POST",
                f"{base_url}/api/v1/pools/api-floating-5/allocate",
                {"user_id": user_id},
            )
            assert_equal(status, 200, "entitled pool allocation should return 200")
            allocated_vmids.append(int(payload["vmid"]))
        assert_equal(sorted(allocated_vmids), [801, 802, 803, 804, 805], "api pool should allocate all five desktops")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-floating-5/release",
            {"vmid": 801, "user_id": "alice"},
        )
        assert_equal(status, 200, "release route should return 200")
        assert_equal(payload.get("state"), "recycling", "released non-persistent desktop should enter recycling")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-floating-5/recycle",
            {"vmid": 801},
        )
        assert_equal(status, 200, "recycle route should return 200")
        assert_equal(payload.get("state"), "free", "recycle route should return desktop to free")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools",
            {
                "pool_id": "api-persistent",
                "template_id": template_id,
                "mode": "floating_persistent",
                "min_pool_size": 1,
                "max_pool_size": 2,
                "warm_pool_size": 1,
                "cpu_cores": 2,
                "memory_mib": 4096,
                "storage_pool": "local",
            },
        )
        assert_equal(status, 201, "persistent pool create route should return 201")

        status, _ = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-persistent/vms",
            {"vmid": 901},
        )
        assert_equal(status, 201, "persistent pool vm registration should return 201")

        status, _ = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-persistent/entitlements",
            {"users": ["alice"]},
        )
        assert_equal(status, 200, "persistent entitlement route should return 200")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-persistent/allocate",
            {"user_id": "alice"},
        )
        assert_equal(status, 200, "persistent first allocation should return 200")
        first_vmid = int(payload["vmid"])

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-persistent/release",
            {"vmid": first_vmid, "user_id": "alice"},
        )
        assert_equal(status, 200, "persistent release should return 200")
        assert_equal(payload.get("state"), "free", "persistent release should return the desktop to free")

        status, payload = http_json(
            "POST",
            f"{base_url}/api/v1/pools/api-persistent/allocate",
            {"user_id": "alice"},
        )
        assert_equal(status, 200, "persistent second allocation should return 200")
        assert_equal(int(payload["vmid"]), first_vmid, "persistent api allocation should reuse the same vmid")
    finally:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        if process.returncode not in (0, -15):
            raise RuntimeError(
                "throwaway control plane exited unexpectedly\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            )


def run_authenticated_visibility_smoke(temp_dir: Path, template_id: str) -> None:
    auth_temp_dir = temp_dir / "auth-visibility"
    auth_temp_dir.mkdir(parents=True, exist_ok=True)
    port = find_free_port()
    provider_state_dir = auth_temp_dir / "provider-state-auth"
    provider_state_dir.mkdir(parents=True, exist_ok=True)
    auth_service = build_auth_service(auth_temp_dir)
    auth_service.save_role(name="pool-reader", permissions=["pool:read"])
    auth_service.create_user(username="pool-admin", password="AdminPass123", role="superadmin", enabled=True)
    auth_service.create_user(username="alice", password="AlicePass123", role="pool-reader", enabled=True)
    auth_service.create_user(username="mallory", password="MalloryPass123", role="pool-reader", enabled=True)
    admin_session = auth_service.login(username="pool-admin", password="AdminPass123")
    alice_session = auth_service.login(username="alice", password="AlicePass123")
    mallory_session = auth_service.login(username="mallory", password="MalloryPass123")
    assert_true(admin_session is not None, "admin session should be issuable")
    assert_true(alice_session is not None, "alice session should be issuable")
    assert_true(mallory_session is not None, "mallory session should be issuable")

    env = os.environ.copy()
    env.update(
        {
            "BEAGLE_MANAGER_LISTEN_HOST": "127.0.0.1",
            "BEAGLE_MANAGER_LISTEN_PORT": str(port),
            "BEAGLE_MANAGER_DATA_DIR": str(auth_temp_dir),
            "BEAGLE_BEAGLE_PROVIDER_STATE_DIR": str(provider_state_dir),
            "BEAGLE_AUTH_BOOTSTRAP_DISABLE": "1",
            "PYTHONPATH": f"{ROOT_DIR}:{SERVICES_DIR}:{env.get('PYTHONPATH', '')}".rstrip(":"),
        }
    )

    process = subprocess.Popen(
        [sys.executable, str(ROOT_DIR / "beagle-host" / "bin" / "beagle-control-plane.py")],
        cwd=str(ROOT_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        wait_for_server_ready(base_url)
        admin_headers = authorization_headers(str(admin_session["access_token"]))
        alice_headers = authorization_headers(str(alice_session["access_token"]))
        mallory_headers = authorization_headers(str(mallory_session["access_token"]))

        for pool_id in ["pool-open", "pool-visible", "pool-hidden"]:
            status, payload = http_json(
                "POST",
                f"{base_url}/api/v1/pools",
                {
                    "pool_id": pool_id,
                    "template_id": template_id,
                    "mode": "floating_non_persistent",
                    "min_pool_size": 1,
                    "max_pool_size": 2,
                    "warm_pool_size": 1,
                    "cpu_cores": 2,
                    "memory_mib": 4096,
                    "storage_pool": "local",
                },
                headers=admin_headers,
            )
            assert_equal(status, 201, f"admin should create {pool_id}")
            assert_true(payload.get("ok") is True, f"create {pool_id} should return ok=true")

        status, _ = http_json(
            "POST",
            f"{base_url}/api/v1/pools/pool-visible/entitlements",
            {"users": ["alice"]},
            headers=admin_headers,
        )
        assert_equal(status, 200, "visible pool entitlements should be writable")
        status, _ = http_json(
            "POST",
            f"{base_url}/api/v1/pools/pool-hidden/entitlements",
            {"users": ["carol"]},
            headers=admin_headers,
        )
        assert_equal(status, 200, "hidden pool entitlements should be writable")

        status, payload = http_json("GET", f"{base_url}/api/v1/pools", headers=admin_headers)
        assert_equal(status, 200, "admin pool list should return 200")
        admin_pool_ids = sorted(str(item.get("pool_id") or "") for item in payload.get("pools", []))
        assert_equal(admin_pool_ids, ["pool-hidden", "pool-open", "pool-visible"], "admin should see every pool")

        status, payload = http_json("GET", f"{base_url}/api/v1/pools", headers=alice_headers)
        assert_equal(status, 200, "alice pool list should return 200")
        alice_pool_ids = sorted(str(item.get("pool_id") or "") for item in payload.get("pools", []))
        assert_equal(alice_pool_ids, ["pool-open", "pool-visible"], "alice should only see unrestricted and entitled pools")

        status, payload = http_json("GET", f"{base_url}/api/v1/pools", headers=mallory_headers)
        assert_equal(status, 200, "mallory pool list should return 200")
        mallory_pool_ids = sorted(str(item.get("pool_id") or "") for item in payload.get("pools", []))
        assert_equal(mallory_pool_ids, ["pool-open"], "mallory should not see restricted pools without entitlement")

        status, payload = http_json("GET", f"{base_url}/api/v1/pools/pool-hidden", headers=alice_headers)
        assert_equal(status, 404, "alice should not be able to fetch hidden pool details")
        assert_equal(payload.get("error"), "pool not found", "hidden pool lookup should be masked as not found")

        status, payload = http_json("GET", f"{base_url}/api/v1/pools/pool-visible", headers=alice_headers)
        assert_equal(status, 200, "alice should be able to fetch the entitled pool")
        assert_equal(payload.get("pool_id"), "pool-visible", "entitled pool detail should round-trip")
    finally:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=10)
        if process.returncode not in (0, -15):
            raise RuntimeError(
                "authenticated visibility control plane exited unexpectedly\n"
                f"stdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="beagle-vdi-smoke-") as temp_root:
        temp_dir = Path(temp_root)
        template_id = run_service_smoke(temp_dir)
        run_api_smoke(temp_dir, template_id)
        run_authenticated_visibility_smoke(temp_dir, template_id)
    print("VDI_POOL_SMOKE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
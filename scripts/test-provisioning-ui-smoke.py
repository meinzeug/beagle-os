#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


@dataclass
class MockState:
    token: str = "smoke-token"
    provision_posts: int = 0
    seen_api_calls: list[str] = field(default_factory=list)
    recent_requests: list[dict[str, Any]] = field(default_factory=list)
    next_vmid: int = 990
    vms: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "vmid": 120,
                "name": "baseline-vm",
                "node": "beagle-0",
                "status": "running",
                "profile": {
                    "vmid": 120,
                    "name": "baseline-vm",
                    "node": "beagle-0",
                    "status": "running",
                },
            }
        ]
    )


def _ok(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _api_path(url: str) -> str:
    path = urlparse(url).path
    for prefix in ("/beagle-api/api/v1", "/api/v1"):
        if path.startswith(prefix):
            return path[len(prefix) :] or "/"
    return path


def _find_vm(state: MockState, vmid: int) -> dict[str, Any] | None:
    for vm in state.vms:
        if int(vm.get("vmid") or 0) == vmid:
            return vm
    return None


def _route_api(route, state: MockState) -> bool:
    request = route.request
    method = request.method.upper()
    if "/beagle-api/api/v1/" not in request.url and "/api/v1/" not in request.url:
        return False

    path = _api_path(request.url)
    state.seen_api_calls.append(f"{method} {path}")

    if path == "/auth/me" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"user": {"username": "admin", "role": "admin", "permissions": ["*"]}}))
        return True

    if path == "/auth/providers" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"providers": []}))
        return True

    if path == "/health" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True, "healthy": True, "vm_count": len(state.vms)}))
        return True

    if path == "/vms" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"vms": state.vms}))
        return True

    if path.startswith("/vms/") and method == "GET":
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "vms" and parts[1].isdigit():
            vmid = int(parts[1])
            vm = _find_vm(state, vmid)
            if vm is None:
                route.fulfill(status=404, content_type="application/json", body=_ok({"error": "not found"}))
                return True
            if len(parts) == 2:
                route.fulfill(status=200, content_type="application/json", body=_ok({"vm": vm, **vm}))
                return True
            route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True}))
            return True

    if path in {"/endpoints", "/policies"} and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({path.strip("/"): []}))
        return True

    if path == "/virtualization/overview" and method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_ok(
                {
                    "nodes": [{"name": "beagle-0", "status": "online", "vm_count": len(state.vms), "maxmem": 16384, "cpu": 0.1}],
                    "storage": [{"name": "local", "type": "dir", "used": 10, "total": 100}],
                    "bridges": [{"name": "vmbr0", "cidr": "192.168.123.0/24"}],
                }
            ),
        )
        return True

    if path == "/ha/status" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True, "ha_state": "ok", "quorum": {"ok": True}, "fencing": {"active": False}, "nodes": [], "alerts": []}))
        return True

    if path == "/cluster/status" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True, "cluster": {"initialized": True, "members": [{"name": "srv-local", "status": "online"}]}}))
        return True

    if path == "/nodes/install-checks" and method == "GET":
        route.fulfill(status=200, content_type="application/json", body=_ok({"nodes": []}))
        return True

    if path in {"/auth/users", "/auth/roles", "/pools", "/pool-templates", "/sessions"} and method == "GET":
        key = path.strip("/").replace("-", "_")
        if key == "pool_templates":
            key = "templates"
        route.fulfill(status=200, content_type="application/json", body=_ok({key: []}))
        return True

    if path == "/provisioning/catalog" and method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_ok(
                {
                    "catalog": {
                        "defaults": {
                            "node": "beagle-0",
                            "next_vmid": state.next_vmid,
                            "desktop": "ubuntu-22.04",
                            "memory": 4096,
                            "cores": 4,
                            "disk_gb": 64,
                            "bridge": "vmbr0",
                            "disk_storage": "local",
                            "iso_storage": "local",
                            "guest_user": "beagle",
                        },
                        "nodes": [{"name": "beagle-0", "status": "online"}],
                        "desktop_profiles": [{"id": "ubuntu-22.04", "label": "Ubuntu 22.04"}],
                        "bridges": ["vmbr0"],
                        "storages": {
                            "images": [{"id": "local", "type": "dir"}],
                            "iso": [{"id": "local", "type": "dir"}],
                        },
                        "recent_requests": state.recent_requests,
                    },
                }
            ),
        )
        return True

    if path == "/provisioning/vms" and method == "POST":
        state.provision_posts += 1
        payload = json.loads(request.post_data or "{}")
        vmid = int(payload.get("vmid") or state.next_vmid)
        name = str(payload.get("name") or f"ubuntu-beagle-{vmid}")
        node = str(payload.get("node") or "beagle-0")
        state.next_vmid = max(state.next_vmid + 1, vmid + 1)
        state.recent_requests.insert(
            0,
            {
                "vmid": vmid,
                "name": name,
                "node": node,
                "desktop_id": str(payload.get("desktop") or "ubuntu-22.04"),
                "provision_status": "queued",
                "created_at": "2026-04-29T12:00:00Z",
                "updated_at": "2026-04-29T12:00:01Z",
            },
        )
        state.vms.append(
            {
                "vmid": vmid,
                "name": name,
                "node": node,
                "status": "installing",
                "profile": {"vmid": vmid, "name": name, "node": node, "status": "installing"},
            }
        )
        route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True, "provisioned_vm": {"vmid": vmid, "name": name, "node": node}}))
        return True

    route.fulfill(status=200, content_type="application/json", body=_ok({"ok": True}))
    return True


def _browser_common_shim() -> str:
    return r"""
(() => {
  function sessionStorageOrNull() {
    try {
      return window.sessionStorage;
    } catch (_error) {
      return null;
    }
  }

  function createSessionTokenStore(storageKey) {
    const key = String(storageKey || '').trim();
    return {
      read() {
        const storage = sessionStorageOrNull();
        if (!storage || !key) return '';
        try {
          return String(storage.getItem(key) || '').trim();
        } catch (_error) {
          return '';
        }
      },
      write(token) {
        const storage = sessionStorageOrNull();
        if (!storage || !key) return;
        try {
          storage.setItem(key, String(token || '').trim());
        } catch (_error) {
          void _error;
        }
      },
      clear() {
        const storage = sessionStorageOrNull();
        if (!storage || !key) return;
        try {
          storage.removeItem(key);
        } catch (_error) {
          void _error;
        }
      }
    };
  }

  function normalizeBeagleApiPath(path) {
    const value = String(path || '').trim() || '/';
    return value.indexOf('/beagle-api/') === 0 ? value.slice('/beagle-api'.length) : value;
  }

  function joinBaseAndPath(base, path) {
    const baseText = String(base || '').trim();
    let normalizedPath = normalizeBeagleApiPath(path);
    if (!baseText) return normalizedPath;
    if (normalizedPath.charAt(0) !== '/') normalizedPath = '/' + normalizedPath;
    return baseText.replace(/\/$/, '') + normalizedPath;
  }

  window.BeagleBrowserCommon = {
    createSessionTokenStore,
    joinBaseAndPath,
    normalizeBeagleApiPath,
    appendHashToken(url) { return String(url || ''); },
    fillTemplate(template) { return String(template || ''); },
    managerUrlFromHealthUrl(url) { return String(url || ''); },
    withNoCache(url) { return String(url || ''); }
  };
})();
"""


def run(args: argparse.Namespace) -> int:
    state = MockState()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        console_errors: list[str] = []
        page_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        page.route("**/beagle-api/api/v1/**", lambda route: _route_api(route, state))
        page.route("**/api/v1/**", lambda route: _route_api(route, state))
        page.add_init_script(_browser_common_shim())

        page.goto(args.base_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        page.wait_for_selector("#api-token", timeout=args.timeout_ms)
        page.fill("#auth-username", "")
        page.fill("#auth-password", "")
        page.fill("#api-token", state.token)
        page.click("#connect-button")

        deadline = time.monotonic() + (args.timeout_ms / 1000.0)
        while time.monotonic() < deadline:
            if not page.evaluate("() => document.body.classList.contains('auth-only')"):
                break
            page.wait_for_timeout(100)
        else:
            banner_text = page.locator("#auth-status").inner_text() if page.locator("#auth-status").count() else ""
            body_classes = page.evaluate("() => document.body.className")
            raise RuntimeError(
                "dashboard did not leave auth-only mode after login; "
                f"banner={banner_text!r}; body_classes={body_classes!r}; api_calls={state.seen_api_calls!r}"
            )

        page.evaluate(
            """() => {
              const button = document.querySelector('[data-panel="provisioning"]');
              if (button) button.click();
            }"""
        )
        deadline = time.monotonic() + (args.timeout_ms / 1000.0)
        active = {"modalOpen": False}
        while time.monotonic() < deadline:
            active = page.evaluate(
                """() => ({
                  modalOpen: !!document.getElementById('provision-modal') && !document.getElementById('provision-modal').hasAttribute('hidden'),
                })"""
            )
            if active.get("modalOpen"):
                break
            page.wait_for_timeout(100)
        else:
            raise RuntimeError(f"provisioning modal did not open: {active!r}")

        page.wait_for_function(
            """() => {
              const select = document.getElementById('prov-modal-node');
              return !!select && select.options && select.options.length >= 1 && String(select.value || '').length >= 1;
            }""",
            timeout=args.timeout_ms,
        )
        page.fill("#prov-modal-guest-password", "Sm0kePass!2026")
        page.fill("#prov-modal-name", "ci-provisioning-smoke")
        page.click("#provision-modal-create")
        page.wait_for_selector("#provision-progress-modal:not([hidden])", timeout=args.timeout_ms)
        page.wait_for_function(
            """() => {
              const msg = document.getElementById('provision-progress-message');
              const openBtn = document.getElementById('provision-progress-open-vm');
              return !!msg && !!openBtn && msg.textContent.includes('erfolgreich gestartet') && !openBtn.hidden;
            }""",
            timeout=args.timeout_ms,
        )
        page.click("#provision-progress-close")
        page.wait_for_function(
            """() => {
              const modal = document.getElementById('provision-progress-modal');
              return !!modal && modal.hasAttribute('hidden');
            }""",
            timeout=args.timeout_ms,
        )
        page.wait_for_function("() => document.querySelectorAll('#provision-recent-body tr[data-vmid]').length >= 1", timeout=args.timeout_ms)

        browser.close()

    filtered_console = [item for item in console_errors if "favicon" not in item.lower()]
    if filtered_console:
        raise RuntimeError("console errors: " + " | ".join(filtered_console))
    if page_errors:
        raise RuntimeError("page errors: " + " | ".join(page_errors))
    if state.provision_posts != 1:
        raise RuntimeError(f"expected exactly one provisioning POST, got {state.provision_posts}")

    print(
        "PROVISIONING_UI_SMOKE_OK",
        f"base_url={args.base_url}",
        f"provision_posts={state.provision_posts}",
        f"api_calls={len(state.seen_api_calls)}",
        f"recent_requests={len(state.recent_requests)}",
    )
    print("PROVISIONING_UI_SMOKE=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Provisioning panel UI smoke with mocked API for CI.")
    parser.add_argument("--base-url", default="http://127.0.0.1:4173", help="Base URL where website/index.html is served")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="test1234")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

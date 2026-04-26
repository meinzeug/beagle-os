#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.parse
import urllib.request
from typing import Any

from playwright.sync_api import sync_playwright


def _login_api(base_url: str, username: str, password: str) -> str:
    payload = json.dumps({"username": username, "password": password}).encode()
    request = urllib.request.Request(
        base_url.rstrip("/") + "/beagle-api/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, context=context, timeout=20) as response:
        body = json.loads(response.read().decode())
    token = str(body.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("login did not return access_token")
    return token


def _get_json(base_url: str, path: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        headers={"Authorization": "Bearer " + token},
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, context=context, timeout=20) as response:
        return json.loads(response.read().decode())


def _login_ui(page: Any, username: str, password: str, timeout_ms: int) -> None:
    page.wait_for_selector("#auth-username", timeout=timeout_ms)
    page.fill("#auth-username", username)
    page.fill("#auth-password", password)
    page.click("#connect-button")
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-only')",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1200)


def _open_virtualization_panel(page: Any, timeout_ms: int) -> None:
    page.click('[data-panel="virtualization"]')
    page.wait_for_selector('#virtualization-workspace-section.panel-section-active', state="attached", timeout=timeout_ms)
    page.wait_for_timeout(1200)


def _count(page: Any, selector: str) -> int:
    return int(page.locator(selector).count())


def _run_for_host(base_url: str, username: str, password: str, timeout_ms: int, show_browser: bool) -> dict[str, Any]:
    token = _login_api(base_url, username, password)
    overview = _get_json(base_url, "/beagle-api/api/v1/virtualization/overview", token)
    vms_payload = _get_json(base_url, "/beagle-api/api/v1/vms", token)
    vm_items = vms_payload.get("vms") if isinstance(vms_payload, dict) else []
    first_vmid = None
    if isinstance(vm_items, list):
        for item in vm_items:
            if not isinstance(item, dict):
                continue
            vmid = int(item.get("vmid") or 0)
            if vmid > 0:
                first_vmid = vmid
                break

    console_errors: list[str] = []
    page_errors: list[str] = []
    result: dict[str, Any] = {
        "base_url": base_url,
        "node_cards": 0,
        "storage_cards": 0,
        "bridge_cards": 0,
        "inspector_vmid": first_vmid,
        "console_errors": console_errors,
        "page_errors": page_errors,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not show_browser)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        page.goto(base_url, wait_until="domcontentloaded", timeout=timeout_ms)
        _login_ui(page, username, password, timeout_ms)
        _open_virtualization_panel(page, timeout_ms)

        page.wait_for_function(
            """() => {
              const nodes = document.querySelectorAll('#nodes-grid .node-card').length;
              const storage = document.querySelectorAll('#virtualization-storage-cards .storage-card').length;
              const bridges = document.querySelectorAll('#virtualization-bridge-cards .bridge-card').length;
              return nodes >= 1 && storage >= 1 && bridges >= 1;
            }""",
            timeout=timeout_ms,
        )

        result["node_cards"] = _count(page, "#nodes-grid .node-card")
        result["storage_cards"] = _count(page, "#virtualization-storage-cards .storage-card")
        result["bridge_cards"] = _count(page, "#virtualization-bridge-cards .bridge-card")

        expected_nodes = len(overview.get("nodes") or [])
        expected_storage = len(overview.get("storage") or [])
        expected_bridges = len(overview.get("bridges") or [])
        assert result["node_cards"] >= expected_nodes, f"expected >= {expected_nodes} node cards, got {result['node_cards']}"
        assert result["storage_cards"] >= min(expected_storage, max(1, expected_storage)), f"expected storage cards, got {result['storage_cards']}"
        assert result["bridge_cards"] >= min(expected_bridges, max(1, expected_bridges)), f"expected bridge cards, got {result['bridge_cards']}"

        if page.locator("button[data-virt-node-detail]").count():
            page.evaluate(
                """() => {
                  const btn = document.querySelector('button[data-virt-node-detail]');
                  if (btn) btn.click();
                }"""
            )
            page.wait_for_selector("#virt-node-detail-modal", state="attached", timeout=timeout_ms)
            page.click("#virt-node-detail-close")

        if page.locator("button[data-virt-bridge-detail]").count():
            page.evaluate(
                """() => {
                  const btn = document.querySelector('button[data-virt-bridge-detail]');
                  if (btn) btn.click();
                }"""
            )
            page.wait_for_selector("#virt-bridge-detail-modal", state="attached", timeout=timeout_ms)
            page.click("#virt-bridge-detail-close")

        if first_vmid:
            page.fill("#virt-inspector-vmid", str(first_vmid))
            page.click("#virt-inspector-load", force=True)
            page.wait_for_function(
                f"""() => {{
                  const summary = document.getElementById('virt-inspector-summary');
                  const recent = document.getElementById('virt-inspector-recent');
                  return summary && summary.textContent.includes('{first_vmid}') && recent && recent.textContent.includes('{first_vmid}');
                }}""",
                timeout=timeout_ms,
            )
            if page.locator("#virt-inspector-use-last").count():
                page.click("#virt-inspector-use-last", force=True)
                page.wait_for_timeout(400)

        browser.close()

    result["console_errors"] = [item for item in console_errors if "favicon" not in item.lower()]
    result["page_errors"] = page_errors
    if result["console_errors"]:
        raise RuntimeError("console errors: " + " | ".join(result["console_errors"]))
    if result["page_errors"]:
        raise RuntimeError("page errors: " + " | ".join(result["page_errors"]))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Virtualization panel smoke for Beagle WebUI.")
    parser.add_argument("--base-urls", nargs="+", required=True, help="One or more WebUI base URLs")
    parser.add_argument("--username", required=True, help="WebUI username")
    parser.add_argument("--password", required=True, help="WebUI password")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()

    failures: list[str] = []
    for base_url in args.base_urls:
        try:
            result = _run_for_host(
                base_url=base_url,
                username=args.username,
                password=args.password,
                timeout_ms=int(args.timeout_ms),
                show_browser=bool(args.show_browser),
            )
            print(
                "VIRT_PANEL_SMOKE_OK",
                result["base_url"],
                f"nodes={result['node_cards']}",
                f"storage={result['storage_cards']}",
                f"bridges={result['bridge_cards']}",
                f"inspector_vmid={result['inspector_vmid'] or '-'}",
            )
        except Exception as exc:
            failures.append(f"{base_url}: {exc}")
            print("VIRT_PANEL_SMOKE_FAIL", base_url, str(exc), file=sys.stderr)

    if failures:
        print("VIRT_PANEL_SMOKE=FAIL")
        for item in failures:
            print(item, file=sys.stderr)
        return 1
    print("VIRT_PANEL_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any

from playwright.sync_api import sync_playwright


def _login(page: Any, username: str, password: str, timeout_ms: int) -> None:
    page.wait_for_selector("#auth-username", timeout=timeout_ms)
    page.fill("#auth-username", username)
    page.fill("#auth-password", password)
    page.click("#connect-button")
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-only')",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1200)


def _open_cluster_panel(page: Any) -> None:
    page.evaluate(
        """
() => {
  window.location.hash = 'panel=cluster';
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}
        """
    )
    page.wait_for_timeout(800)
    page.wait_for_selector("#cluster-section", state="visible")


def run(args: argparse.Namespace) -> int:
    status_requests = {"count": 0}
    auto_join_payloads: list[dict[str, Any]] = []
    maintenance_preview_payloads: list[dict[str, Any]] = []
    maintenance_async_payloads: list[dict[str, Any]] = []
    job_reads = {"auto-join-job": 0, "maint-job": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        def handle_route(route) -> None:
            request = route.request
            url = request.url
            method = request.method.upper()

            if "/beagle-api/api/v1/cluster/status" in url and method == "GET":
                status_requests["count"] += 1
                route.continue_()
                return

            if url.endswith("/beagle-api/api/v1/cluster/auto-join-async") and method == "POST":
                payload = json.loads(request.post_data or "{}")
                auto_join_payloads.append(payload)
                route.fulfill(
                    status=202,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "job_id": "auto-join-job",
                            "node_name": payload.get("node_name"),
                            "advertise_host": payload.get("advertise_host"),
                        }
                    ),
                )
                return

            if "/beagle-api/api/v1/jobs/auto-join-job/stream" in url and method == "GET":
                route.abort()
                return

            if url.endswith("/beagle-api/api/v1/jobs/auto-join-job") and method == "GET":
                job_reads["auto-join-job"] += 1
                if job_reads["auto-join-job"] < 2:
                    body = {
                        "job_id": "auto-join-job",
                        "status": "running",
                        "progress": 30,
                        "message": "Token: erstelle kurzlebigen Join-Code auf dem Leader ...",
                        "result": None,
                        "error": "",
                    }
                else:
                    body = {
                        "job_id": "auto-join-job",
                        "status": "completed",
                        "progress": 100,
                        "message": "Abgeschlossen: srv2 ist jetzt Cluster-Mitglied",
                        "error": "",
                        "result": {
                            "ok": True,
                            "preflight": {
                                "checks": [
                                    {"name": "dns", "status": "pass", "message": "srv2.beagle-os.com aufgeloest", "required": True},
                                    {"name": "api", "status": "pass", "message": "HTTPS erreichbar", "required": True},
                                ]
                            },
                            "target": {
                                "cluster_id": "cluster-1",
                                "member": {"name": "srv2"},
                                "member_count": 2,
                            },
                        },
                    }
                route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                return

            if url.endswith("/beagle-api/api/v1/ha/maintenance/preview") and method == "POST":
                payload = json.loads(request.post_data or "{}")
                maintenance_preview_payloads.append(payload)
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(
                        {
                            "ok": True,
                            "node_name": payload.get("node_name"),
                            "maintenance_enabled": False,
                            "evaluated_vm_count": 2,
                            "handled_vm_count": 2,
                            "actions": [
                                {"vmid": 101, "vm_name": "desktop-a", "result": "live_migration", "target_node": "srv2", "handled": True},
                                {"vmid": 102, "vm_name": "desktop-b", "result": "cold_restart", "target_node": "srv2", "handled": True},
                            ],
                            "maintenance_nodes": [],
                        }
                    ),
                )
                return

            if url.endswith("/beagle-api/api/v1/ha/maintenance/drain-async") and method == "POST":
                payload = json.loads(request.post_data or "{}")
                maintenance_async_payloads.append(payload)
                route.fulfill(
                    status=202,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "job_id": "maint-job", "node_name": payload.get("node_name")}),
                )
                return

            if "/beagle-api/api/v1/jobs/maint-job/stream" in url and method == "GET":
                route.abort()
                return

            if url.endswith("/beagle-api/api/v1/jobs/maint-job") and method == "GET":
                job_reads["maint-job"] += 1
                body = {
                    "job_id": "maint-job",
                    "status": "completed" if job_reads["maint-job"] > 1 else "running",
                    "progress": 100 if job_reads["maint-job"] > 1 else 55,
                    "message": "Abgeschlossen: srv1 ist jetzt in Maintenance" if job_reads["maint-job"] > 1 else "Maintenance wird gesetzt und VM-Aktionen werden ausgefuehrt ...",
                    "error": "",
                    "result": {
                        "ok": True,
                        "node_name": "srv1",
                        "handled_vm_count": 2,
                        "actions": [
                            {"vmid": 101, "vm_name": "desktop-a", "result": "live_migration", "target_node": "srv2", "handled": True},
                            {"vmid": 102, "vm_name": "desktop-b", "result": "cold_restart", "target_node": "srv2", "handled": True},
                        ],
                    } if job_reads["maint-job"] > 1 else None,
                }
                route.fulfill(status=200, content_type="application/json", body=json.dumps(body))
                return

            route.continue_()

        page.route("**/*", handle_route)
        page.goto(args.base_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        _login(page, args.username, args.password, args.timeout_ms)
        _open_cluster_panel(page)

        page.click("#cluster-action-add-server")
        page.wait_for_selector("#cluster-add-server-modal:not([hidden])", timeout=args.timeout_ms)

        page.click("#cluster-add-server-preflight-btn")
        page.wait_for_timeout(500)
        assert not auto_join_payloads, "auto-join request should not be sent when setup code is missing"

        before_status_refresh = status_requests["count"]
        page.fill("#cluster-add-server-hostname", "srv2.beagle-os.com")
        page.fill("#cluster-add-server-setup-code", "BGL-TEST-CODE")
        page.click("#cluster-add-server-preflight-btn")
        page.wait_for_function(
            "() => { const el = document.getElementById('cluster-add-server-token-output'); return el && el.value.includes('Cluster: cluster-1'); }",
            timeout=args.timeout_ms,
        )
        page.wait_for_timeout(2500)
        assert auto_join_payloads, "cluster auto-join request not sent"
        assert auto_join_payloads[-1]["node_name"] == "srv2"
        assert auto_join_payloads[-1]["api_url"] == "https://srv2.beagle-os.com/beagle-api/api/v1"
        assert auto_join_payloads[-1]["rpc_url"] == "https://srv2.beagle-os.com:9089/rpc"
        assert status_requests["count"] > before_status_refresh, "dashboard refresh not triggered after auto-join success"
        page.click("#cluster-add-server-modal [data-close-cluster-modal]")
        page.wait_for_timeout(400)

        page.wait_for_selector("[data-cluster-maintenance-node]", timeout=args.timeout_ms)
        maintenance_node_name = page.locator("[data-cluster-maintenance-node]").first.get_attribute("data-cluster-maintenance-node") or ""
        assert maintenance_node_name, "maintenance button has no target node"
        page.locator("[data-cluster-maintenance-node]").first.click()
        page.wait_for_function(
            "() => document.body.textContent.includes('desktop-a') && document.body.textContent.includes('desktop-b')",
            timeout=args.timeout_ms,
        )
        page.click(f"#maintenance-preview-confirm-{maintenance_node_name}")
        page.wait_for_function(
            f"() => !document.querySelector('#maintenance-preview-modal-{maintenance_node_name}')",
            timeout=args.timeout_ms,
        )
        page.wait_for_timeout(2500)
        assert maintenance_preview_payloads, "maintenance preview request not sent"
        assert maintenance_preview_payloads[-1]["node_name"] == maintenance_node_name
        assert maintenance_async_payloads, "maintenance async request not sent"
        assert maintenance_async_payloads[-1]["node_name"] == maintenance_node_name

        browser.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cluster wizard regression smoke for the Beagle WebUI.")
    parser.add_argument("--base-url", default="https://srv1.beagle-os.com/", help="Base URL of the WebUI")
    parser.add_argument("--username", required=True, help="WebUI username")
    parser.add_argument("--password", required=True, help="WebUI password")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

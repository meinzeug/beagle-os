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


def _open_updates_panel(page: Any, timeout_ms: int) -> None:
    page.evaluate(
        """
() => {
  window.location.hash = 'panel=settings_updates';
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}
        """
    )
    page.wait_for_selector("#settings-updates-section.panel-section-active", timeout=timeout_ms)
    page.wait_for_timeout(800)


def _artifact_payload(*, status: str, progress: int, message: str, public_ready: bool) -> dict[str, Any]:
    missing_latest = [] if public_ready else ["pve-thin-client-live-usb-latest.ps1"]
    missing_versioned = [] if public_ready else ["pve-thin-client-live-usb-v6.7.0.ps1"]
    return {
        "ok": True,
        "ready": public_ready,
        "running_refresh": status in {"queued", "running"},
        "version": "6.7.0",
        "artifacts": [
            {
                "path": "beagle-downloads-status.json",
                "exists": public_ready,
                "size_bytes": 512,
                "mtime_epoch": 1777212000,
            },
            {
                "path": "pve-thin-client-live-usb-latest.ps1",
                "exists": public_ready,
                "size_bytes": 30554 if public_ready else 0,
                "mtime_epoch": 1777212000 if public_ready else None,
            },
        ],
        "missing": [] if public_ready else ["pve-thin-client-live-usb-latest.ps1"],
        "refresh_status": {
            "status": status,
            "step": "package" if status == "running" else "finalize",
            "progress": progress,
            "message": message,
            "last_result": status,
            "updated_at": "2026-04-26T14:24:42+00:00",
            "finished_at": "2026-04-26T14:29:42+00:00" if status in {"ok", "failed"} else "",
            "error_excerpt": "Command failed: ./scripts/package.sh" if status == "failed" else "",
        },
        "preflight": {
            "free_bytes": 512 * 1024 * 1024 * 1024,
            "total_bytes": 1024 * 1024 * 1024 * 1024,
            "running_refresh": status in {"queued", "running"},
            "service_unit_present": True,
            "systemd_start_capable": True,
            "missing_required_tools": [],
            "missing_optional_build_tools": [],
            "ok": status not in {"queued", "running"},
        },
        "publish_gate": {
            "public_ready": public_ready,
            "missing_latest": missing_latest,
            "missing_versioned": missing_versioned,
            "latest_expected": ["pve-thin-client-live-usb-latest.ps1"],
            "versioned_expected": ["pve-thin-client-live-usb-v6.7.0.ps1"],
        },
        "links": {
            "status_json": "/beagle-downloads/beagle-downloads-status.json",
            "downloads_index": "/beagle-downloads/beagle-downloads-index.html",
        },
        "services": {
            "beagle-artifacts-refresh.service": "active" if status == "running" else "inactive",
            "beagle-artifacts-refresh.timer": "active",
        },
    }


def run(args: argparse.Namespace) -> int:
    artifact_get_count = {"value": 0}
    artifact_post_count = {"value": 0}
    updates_get_count = {"value": 0}

    running_payload = _artifact_payload(
        status="running",
        progress=20,
        message="Release- und Thin-Client-Artefakte werden gebaut ...",
        public_ready=False,
    )
    failed_payload = _artifact_payload(
        status="failed",
        progress=20,
        message="Fehler bei Schritt 'package'.",
        public_ready=False,
    )
    success_payload = _artifact_payload(
        status="ok",
        progress=100,
        message="Host-Artefakte erfolgreich aktualisiert.",
        public_ready=True,
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        def handle_route(route) -> None:
            request = route.request
            url = request.url
            method = request.method.upper()

            if url.endswith("/beagle-api/api/v1/settings/updates") and method == "GET":
                updates_get_count["value"] += 1
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "upgradable_count": 0, "upgradable": []}),
                )
                return

            if url.endswith("/beagle-api/api/v1/settings/artifacts") and method == "GET":
                artifact_get_count["value"] += 1
                if artifact_get_count["value"] == 1:
                    payload = running_payload
                elif artifact_get_count["value"] == 2:
                    payload = failed_payload
                else:
                    payload = success_payload
                route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))
                return

            if url.endswith("/beagle-api/api/v1/settings/artifacts/refresh") and method == "POST":
                artifact_post_count["value"] += 1
                route.fulfill(
                    status=202,
                    content_type="application/json",
                    body=json.dumps({"ok": True, "artifacts": running_payload}),
                )
                return

            route.continue_()

        page.route("**/*", handle_route)
        page.goto(args.base_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
        _login(page, args.username, args.password, args.timeout_ms)
        _open_updates_panel(page, args.timeout_ms)

        page.wait_for_function(
            """() => {
              const msg = document.getElementById('artifact-refresh-message');
              const step = document.getElementById('artifact-refresh-step');
              return msg && step && msg.textContent.includes('Artefakte werden gebaut') && step.textContent.includes('package');
            }""",
            timeout=args.timeout_ms,
        )

        page.wait_for_timeout(5500)
        page.wait_for_function(
            """() => {
              const msg = document.getElementById('artifact-refresh-message');
              const result = document.getElementById('artifact-refresh-result');
              return msg && result && msg.textContent.includes("Fehler bei Schritt") && result.textContent.includes('failed');
            }""",
            timeout=args.timeout_ms,
        )

        page.once("dialog", lambda dialog: dialog.accept())
        page.click("#artifacts-refresh-start")
        page.wait_for_timeout(200)
        page.click("#settings-artifacts-refresh")
        page.wait_for_function(
            """() => {
              const gate = document.getElementById('artifact-gate-message');
              const result = document.getElementById('artifact-refresh-result');
              const ready = document.getElementById('artifact-ready');
              return gate && result && ready &&
                gate.textContent.includes('freigegeben') &&
                result.textContent.includes('ok') &&
                ready.textContent.includes('Ja');
            }""",
            timeout=args.timeout_ms,
        )

        assert updates_get_count["value"] >= 1, "settings/updates was not loaded"
        assert artifact_get_count["value"] >= 3, "artifact status should be fetched for running, failed and success states"
        assert artifact_post_count["value"] == 1, "artifact refresh POST should be triggered once"

        browser.close()

    print(
        "SETTINGS_ARTIFACTS_SMOKE_OK",
        f"artifact_gets={artifact_get_count['value']}",
        f"artifact_posts={artifact_post_count['value']}",
        f"updates_gets={updates_get_count['value']}",
    )
    print("SETTINGS_ARTIFACTS_SMOKE=PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Settings/Artifacts WebUI smoke for Beagle.")
    parser.add_argument("--base-url", default="https://srv1.beagle-os.com/", help="Base URL of the WebUI")
    parser.add_argument("--username", required=True, help="WebUI username")
    parser.add_argument("--password", required=True, help="WebUI password")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())

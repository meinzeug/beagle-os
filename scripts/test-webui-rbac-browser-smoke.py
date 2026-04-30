#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import sync_playwright


def _https_context() -> ssl.SSLContext:
    return ssl._create_unverified_context()


@dataclass
class APIClient:
    base_url: str
    timeout_seconds: int = 20

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = self.base_url.rstrip("/") + path
        payload = json.dumps(body) if body is not None else ""
        command = [
            "curl",
            "-k",
            "-sS",
            "-m",
            str(self.timeout_seconds),
            "-X",
            method.upper(),
            "-H",
            "Accept: application/json",
            "-w",
            "\n__HTTP_STATUS__:%{http_code}",
        ]
        if body is not None:
            command.extend(["-H", "Content-Type: application/json", "--data", payload])
        if token:
            command.extend(["-H", f"Authorization: Bearer {token}"])
        command.append(url)

        last_error: BaseException | None = None
        for attempt in range(1, 4):
            try:
                completed = subprocess.run(command, capture_output=True, text=True, check=False)
            except OSError as exc:
                raise RuntimeError(f"failed to execute curl: {exc}") from exc
            if completed.returncode != 0:
                last_error = RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"curl rc={completed.returncode}")
                if attempt == 3:
                    break
                time.sleep(1.0 * attempt)
                continue
            raw = completed.stdout or ""
            marker = "\n__HTTP_STATUS__:"
            if marker not in raw:
                raise RuntimeError(f"unexpected curl response without status marker: {raw[:200]!r}")
            body_raw, status_raw = raw.rsplit(marker, 1)
            status = int(status_raw.strip() or "0")
            body_text = body_raw.strip() or "{}"
            try:
                payload_dict = json.loads(body_text)
            except json.JSONDecodeError:
                payload_dict = {"raw": body_text}
            return status, payload_dict
        raise RuntimeError(f"request failed after retries: {method.upper()} {path}: {last_error}")

    def login(self, username: str, password: str) -> str:
        status, payload = self._request(
            "POST",
            "/beagle-api/api/v1/auth/login",
            body={"username": username, "password": password},
        )
        if status != 200:
            raise RuntimeError(f"admin login failed: HTTP {status} payload={payload}")
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("login did not return access_token")
        return token

    def create_user(self, token: str, *, username: str, password: str, role: str) -> None:
        status, payload = self._request(
            "POST",
            "/beagle-api/api/v1/auth/users",
            token=token,
            body={"username": username, "password": password, "role": role, "enabled": True},
        )
        if status != 201:
            raise RuntimeError(f"user create failed: HTTP {status} payload={payload}")

    def delete_user(self, token: str, username: str) -> None:
        status, payload = self._request(
            "DELETE",
            f"/beagle-api/api/v1/auth/users/{urllib.parse.quote(username, safe='')}",
            token=token,
        )
        if status not in {200, 404}:
            raise RuntimeError(f"user delete failed: HTTP {status} payload={payload}")


def _login_ui(page: Any, username: str, password: str, timeout_ms: int) -> None:
    page.wait_for_selector("#auth-username", timeout=timeout_ms)
    page.fill("#auth-username", username)
    page.fill("#auth-password", password)
    page.click("#connect-button")
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-only')",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1500)


def _collect_browser_state(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """
() => {
  const isVisible = (node) => {
    if (!node) return false;
    const style = window.getComputedStyle(node);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  };

  const adminItems = Array.from(document.querySelectorAll('.sidebar-admin-item'))
    .map((node) => ({
      panel: String(node.getAttribute('data-panel') || '').trim(),
      visible: isVisible(node),
    }));

  const visibleAdminPanels = adminItems.filter((item) => item.visible).map((item) => item.panel);
  const settingsLabel = document.getElementById('settings-section-label');
  const authChip = document.getElementById('session-chip');

  return {
    body_classes: document.body.className,
    auth_chip: authChip ? String(authChip.textContent || '').trim() : '',
    settings_label_visible: isVisible(settingsLabel),
    visible_admin_panels: visibleAdminPanels,
    active_panel: String(document.body.getAttribute('data-panel') || ''),
  };
}
        """
    )


def run(args: argparse.Namespace) -> int:
    client = APIClient(args.base_url, timeout_seconds=max(20, int(args.timeout_ms / 1000)))
    admin_token = client.login(args.admin_username, args.admin_password)
    temp_username = f"smoke-viewer-{int(time.time())}"
    temp_password = args.viewer_password
    client.delete_user(admin_token, temp_username)
    client.create_user(admin_token, username=temp_username, password=temp_password, role="viewer")

    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_api_calls: list[str] = []
    state: dict[str, Any] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not args.show_browser)
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            page.on(
                "response",
                lambda response: failed_api_calls.append(f"{response.status} {response.url}")
                if response.status >= 400 and "/beagle-api/api/v1/" in response.url
                else None,
            )

            page.goto(args.base_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            _login_ui(page, temp_username, temp_password, args.timeout_ms)
            page.wait_for_timeout(1200)
            state = _collect_browser_state(page)
            browser.close()
    finally:
        client.delete_user(admin_token, temp_username)

    filtered_console = [item for item in console_errors if "favicon" not in item.lower()]
    if filtered_console:
        detail = " | failed_api_calls=" + ", ".join(failed_api_calls) if failed_api_calls else ""
        raise RuntimeError("console errors: " + " | ".join(filtered_console) + detail)
    if page_errors:
        raise RuntimeError("page errors: " + " | ".join(page_errors))
    if state.get("visible_admin_panels"):
        raise RuntimeError("viewer still sees admin panels: " + ", ".join(state["visible_admin_panels"]))
    if bool(state.get("settings_label_visible")):
        raise RuntimeError("viewer still sees settings section label")
    auth_chip = str(state.get("auth_chip") or "")
    if temp_username not in auth_chip:
        raise RuntimeError(f"viewer login did not update auth chip: {auth_chip!r}")

    print("WEBUI_RBAC_BROWSER_SMOKE=PASS")
    print(f"viewer_user={temp_username}")
    print(f"auth_chip={auth_chip}")
    print("visible_admin_panels=0")
    print(f"console_errors={len(filtered_console)}")
    print(f"page_errors={len(page_errors)}")
    print(f"failed_api_calls={len(failed_api_calls)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Real browser smoke: viewer login has no console errors and sees no admin actions.")
    parser.add_argument("--base-url", default="https://srv1.beagle-os.com", help="WebUI base URL")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--viewer-password", default="SmokeView!2026")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--show-browser", action="store_true")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
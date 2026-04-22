#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _set_mode(page: Any, mode: str) -> None:
    if mode not in {"light", "dark"}:
        raise ValueError(f"invalid mode: {mode}")
    page.evaluate(
        """
(mode) => {
  if (mode === 'light') {
    document.body.classList.add('light-mode');
    localStorage.setItem('beagle.darkMode', '0');
  } else {
    document.body.classList.remove('light-mode');
    localStorage.setItem('beagle.darkMode', '1');
  }
  const event = new Event('storage');
  window.dispatchEvent(event);
}
        """,
        mode,
    )


def _collect_layout_metrics(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """
() => {
  const selectors = [
    '#main-column',
    '#auth-status',
    '#inventory-body',
    '#virtualization-panel',
    '#cluster-panel',
    '#provisioning-panel',
    '#policies-panel',
    '#iam-panel',
    '#audit-panel',
    '#sessions-panel',
    '#settings-content',
    '.stat-grid',
    '.panel-title',
  ];

  const visibleRect = (el) => {
    if (!el) return null;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    return {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
    };
  };

  const metrics = {
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight,
    },
    body: {
      scrollHeight: document.body.scrollHeight,
      scrollWidth: document.body.scrollWidth,
    },
    selectors: {},
  };

  for (const selector of selectors) {
    const element = document.querySelector(selector);
    const rect = visibleRect(element);
    if (rect) {
      metrics.selectors[selector] = rect;
    }
  }
  return metrics;
}
        """
    )


def _compute_layout_delta(light: dict[str, Any], dark: dict[str, Any]) -> dict[str, Any]:
    selector_deltas: dict[str, Any] = {}
    max_delta = 0

    light_selectors = light.get("selectors", {})
    dark_selectors = dark.get("selectors", {})
    common = sorted(set(light_selectors.keys()) & set(dark_selectors.keys()))

    for selector in common:
      l = light_selectors[selector]
      d = dark_selectors[selector]
      delta = {
          "dx": abs(int(l["x"]) - int(d["x"])),
          "dy": abs(int(l["y"]) - int(d["y"])),
          "dw": abs(int(l["w"]) - int(d["w"])),
          "dh": abs(int(l["h"]) - int(d["h"])),
      }
      selector_deltas[selector] = delta
      max_delta = max(max_delta, delta["dx"], delta["dy"], delta["dw"], delta["dh"])

    body_delta = {
        "scrollHeight": abs(int(light.get("body", {}).get("scrollHeight", 0)) - int(dark.get("body", {}).get("scrollHeight", 0))),
        "scrollWidth": abs(int(light.get("body", {}).get("scrollWidth", 0)) - int(dark.get("body", {}).get("scrollWidth", 0))),
    }
    max_delta = max(max_delta, body_delta["scrollHeight"], body_delta["scrollWidth"])

    return {
        "max_delta": max_delta,
        "selector_deltas": selector_deltas,
        "body_delta": body_delta,
        "common_selector_count": len(common),
    }


def _wait_dashboard_ready(page: Any, timeout_ms: int) -> None:
    page.wait_for_selector("#auth-username", timeout=timeout_ms)
    page.wait_for_selector("#auth-password", timeout=timeout_ms)
    page.wait_for_selector("#connect-button", timeout=timeout_ms)


def _login(page: Any, username: str, password: str, timeout_ms: int) -> None:
    _wait_dashboard_ready(page, timeout_ms)
    page.fill("#auth-username", username)
    page.fill("#auth-password", password)
    page.click("#connect-button")
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-only')",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(1500)


def _panel_ids(page: Any) -> list[str]:
    return page.evaluate(
        """
() => {
  return Array.from(document.querySelectorAll('#sidebar-nav [data-panel]'))
    .map((node) => String(node.getAttribute('data-panel') || '').trim())
    .filter(Boolean);
}
        """
    )


def _close_overlays(page: Any) -> None:
        page.evaluate(
                """
() => {
    const modalIds = [
        'auth-modal',
        'onboarding-modal',
        'confirm-modal',
        'provision-modal',
        'provision-progress-modal',
        'template-builder-modal',
        'template-builder-progress-modal',
    ];
    for (const id of modalIds) {
        const node = document.getElementById(id);
        if (!node) continue;
        node.hidden = true;
        node.setAttribute('aria-hidden', 'true');
    }
    document.body.classList.remove('modal-open', 'auth-modal-open');
}
                """
        )


def _navigate_panel(page: Any, panel_id: str) -> None:
    page.evaluate(
        """
(panelId) => {
    window.location.hash = 'panel=' + encodeURIComponent(panelId);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
}
        """,
        panel_id,
    )


def _capture_panel(page: Any, panel_id: str, mode: str, output_dir: Path) -> dict[str, Any]:
    _close_overlays(page)
    _navigate_panel(page, panel_id)
    page.wait_for_timeout(900)
    _set_mode(page, mode)
    page.wait_for_timeout(250)

    panel_dir = output_dir / mode
    _ensure_dir(panel_dir)
    screenshot_path = panel_dir / f"{panel_id}.png"
    page.screenshot(path=str(screenshot_path), full_page=True)

    metrics = _collect_layout_metrics(page)
    metrics["screenshot"] = str(screenshot_path)
    return metrics


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    _ensure_dir(output_dir)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        context = browser.new_context(
            viewport={"width": int(args.viewport_width), "height": int(args.viewport_height)},
            ignore_https_errors=True,
        )
        page = context.new_page()

        try:
            page.goto(args.base_url, wait_until="domcontentloaded", timeout=args.timeout_ms)
            _login(page, args.username, args.password, args.timeout_ms)
            panels = _panel_ids(page)
            if not panels:
                raise RuntimeError("no sidebar panels found after login")

            report: dict[str, Any] = {
                "base_url": args.base_url,
                "captured_at": int(time.time()),
                "viewport": {
                    "width": int(args.viewport_width),
                    "height": int(args.viewport_height),
                },
                "panels": {},
                "threshold_px": int(args.max_layout_delta_px),
            }

            failures: list[str] = []
            for panel in panels:
                light_metrics = _capture_panel(page, panel, "light", output_dir)
                dark_metrics = _capture_panel(page, panel, "dark", output_dir)
                delta = _compute_layout_delta(light_metrics, dark_metrics)
                report["panels"][panel] = {
                    "light": light_metrics,
                    "dark": dark_metrics,
                    "delta": delta,
                }
                if int(delta.get("max_delta", 0)) > int(args.max_layout_delta_px):
                    failures.append(f"{panel}: max layout delta {delta['max_delta']}px")

            report_path = output_dir / "report.json"
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

            print(f"VISUAL_SMOKE_REPORT={report_path}")
            print(f"VISUAL_SMOKE_PANELS={len(report['panels'])}")
            if failures:
                print("VISUAL_SMOKE_RESULT=FAIL")
                for item in failures:
                    print(f"VISUAL_SMOKE_FAILURE={item}")
                return 1

            print("VISUAL_SMOKE_RESULT=PASS")
            return 0
        except PlaywrightTimeoutError as exc:
            print(f"VISUAL_SMOKE_RESULT=FAIL")
            print(f"VISUAL_SMOKE_ERROR=timeout: {exc}")
            return 2
        finally:
            context.close()
            browser.close()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture Beagle WebUI panel screenshots in light/dark mode and assert layout stability.",
    )
    parser.add_argument("--base-url", default="https://srv1.beagle-os.com", help="WebUI base URL")
    parser.add_argument("--username", required=True, help="WebUI username")
    parser.add_argument("--password", required=True, help="WebUI password")
    parser.add_argument("--output-dir", default="artifacts/webui-visual-smoke", help="Directory for screenshots/report")
    parser.add_argument("--viewport-width", type=int, default=1600)
    parser.add_argument("--viewport-height", type=int, default=980)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--max-layout-delta-px", type=int, default=4)
    parser.add_argument("--show-browser", action="store_true", help="Run browser in non-headless mode")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))

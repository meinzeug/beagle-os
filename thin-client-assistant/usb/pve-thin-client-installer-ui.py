#!/usr/bin/env python3
import json
import logging
import os
import shlex
import shutil
import subprocess
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_INSTALLER = SCRIPT_DIR / "pve-thin-client-local-installer.sh"
FALLBACK_MENU = SCRIPT_DIR / "pve-thin-client-live-menu.sh"
ASSET_DIR = SCRIPT_DIR / "assets"
HOST = "127.0.0.1"
PORT = 37999
LOG_DIR = Path(os.environ.get("PVE_THIN_CLIENT_LOG_DIR", "/tmp/pve-thin-client-logs"))
LOG_FILE = LOG_DIR / "installer-ui.log"


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


setup_logging()

HTML = """<!doctype html>
<html lang="de" translate="no" class="notranslate">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="google" content="notranslate" />
  <meta http-equiv="Content-Language" content="de" />
  <title>Beagle OS Installer</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #10161c;
      --panel: #18212a;
      --panel-soft: #131a21;
      --border: #2c3947;
      --text: #eff4f7;
      --muted: #aab8c4;
      --accent: #2da3ff;
      --accent-strong: #1676c8;
      --warn: #ffcc6b;
      --danger: #e06666;
      --ok: #69c27d;
      font-family: "DejaVu Sans", "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: linear-gradient(180deg, #0c1117, #151d26);
      color: var(--text);
    }
    .layout {
      max-width: 1240px;
      margin: 0 auto;
      padding: 28px;
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(380px, 0.9fr);
      gap: 22px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 22px;
    }
    .stack {
      display: grid;
      gap: 18px;
    }
    .tag {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: #0f2435;
      border: 1px solid #284055;
      color: #9ed2ff;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    h1, h2, h3, p {
      margin: 0;
    }
    h1 {
      font-size: 38px;
      line-height: 1.05;
      margin-top: 10px;
    }
    .lede {
      color: var(--muted);
      font-size: 18px;
      line-height: 1.5;
      max-width: 52ch;
    }
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .summary-card {
      background: var(--panel-soft);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 16px;
    }
    .summary-card strong {
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .summary-card span {
      display: block;
      font-size: 22px;
      font-weight: 700;
      line-height: 1.2;
      word-break: break-word;
    }
    .banner {
      border-radius: 14px;
      padding: 16px 18px;
      border: 1px solid var(--border);
      background: #132230;
      color: #dbe8f2;
      line-height: 1.5;
    }
    .banner.warn {
      background: #2a2114;
      border-color: #5e4722;
      color: #ffe3a8;
    }
    .banner.ok {
      background: #15251a;
      border-color: #2d5a39;
      color: #d8f2de;
    }
    .section-title {
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 10px;
    }
    .mode-list {
      display: grid;
      gap: 10px;
    }
    .mode-card {
      width: 100%;
      text-align: left;
      border-radius: 14px;
      border: 1px solid var(--border);
      background: var(--panel-soft);
      color: var(--text);
      padding: 16px;
      cursor: pointer;
    }
    .mode-card.selected {
      border-color: var(--accent);
      background: #15293a;
    }
    .mode-card.unavailable {
      opacity: 0.45;
      cursor: default;
    }
    .mode-card strong {
      display: block;
      font-size: 18px;
      margin-bottom: 8px;
    }
    .mode-card span {
      display: block;
      color: var(--muted);
      line-height: 1.45;
    }
    label {
      display: block;
      margin-bottom: 10px;
      font-size: 14px;
      color: var(--muted);
    }
    select {
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      border: 1px solid var(--border);
      background: #0f151b;
      color: var(--text);
      font-size: 16px;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    button {
      appearance: none;
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel-soft);
      color: var(--text);
      padding: 14px 16px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }
    button.primary {
      background: linear-gradient(180deg, var(--accent), var(--accent-strong));
      border-color: #1b6eb7;
      color: #f8fbff;
    }
    button.danger {
      background: #2b1717;
      border-color: #6a3535;
      color: #ffd1d1;
    }
    button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    .status {
      min-height: 24px;
      color: var(--muted);
      font-size: 14px;
    }
    .status.error {
      color: #ffb3b3;
    }
    .details {
      display: grid;
      gap: 8px;
      font-size: 14px;
    }
    .details div {
      display: grid;
      grid-template-columns: 130px minmax(0, 1fr);
      gap: 12px;
      padding-top: 8px;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
    }
    .details strong {
      color: var(--muted);
      font-weight: 600;
    }
    @media (max-width: 980px) {
      .layout {
        grid-template-columns: 1fr;
        padding: 18px;
      }
      .summary-grid,
      .actions {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body class="notranslate">
  <main class="layout">
    <section class="stack">
      <div class="panel stack">
        <div class="tag">Beagle OS Installer</div>
        <div class="stack">
          <h1 id="vm-name">Installer wird vorbereitet</h1>
          <p class="lede" id="vm-hint">Der Stick liest sein gebuendeltes VM-Profil und die verfuegbaren Installationsziele ein.</p>
        </div>
        <div class="summary-grid">
          <div class="summary-card"><strong>Preset</strong><span id="meta-preset">-</span></div>
          <div class="summary-card"><strong>Host</strong><span id="meta-host">-</span></div>
          <div class="summary-card"><strong>Node / VMID</strong><span id="meta-node">-</span></div>
          <div class="summary-card"><strong>Verfuegbare Modi</strong><span id="meta-modes">-</span></div>
        </div>
        <div class="banner" id="banner">Initialisiere Installer-Zustand...</div>
      </div>

      <div class="panel">
        <div class="section-title">Diagnose</div>
        <div class="details">
          <div><strong>Preset-Datei</strong><span id="detail-preset-file">-</span></div>
          <div><strong>Preset-Quelle</strong><span id="detail-preset-source">-</span></div>
          <div><strong>Live-Medium</strong><span id="detail-live-medium">-</span></div>
          <div><strong>Live-Assets</strong><span id="detail-live-assets">-</span></div>
          <div><strong>Log-Verzeichnis</strong><span id="detail-log-dir">-</span></div>
        </div>
      </div>
    </section>

    <aside class="panel stack">
      <div>
        <div class="section-title">Streaming-Modus</div>
        <div class="mode-list" id="mode-grid"></div>
      </div>

      <div>
        <label for="disk-select">Zielplatte</label>
        <select id="disk-select"></select>
      </div>

      <div class="actions">
        <button class="primary" id="install-btn">Installation starten</button>
        <button id="reload-btn">Zustand neu laden</button>
        <button id="preset-btn">Preset anzeigen</button>
        <button id="shell-btn">Shell oeffnen</button>
        <button id="reboot-btn">Neustart</button>
        <button class="danger" id="poweroff-btn">Ausschalten</button>
      </div>

      <div class="status" id="status"></div>
    </aside>
  </main>

  <script>
    const MODE_META = {
      BEAGLE_STREAM_CLIENT: "Beagle Stream Server-Streaming mit dem vorkonfigurierten Ziel.",
      SPICE: "Klassische Beagle- oder SPICE-Konsole.",
      NOVNC: "Browserbasierte Konsole fuer Notfaelle.",
      DCV: "Low-latency Streaming mit DCV."
    };

    let state = null;
    let selectedMode = null;

    async function api(path, method = "GET", payload = null) {
      const response = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json" },
        body: payload ? JSON.stringify(payload) : null
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || data.ok === false) {
        throw new Error(data.error || `HTTP ${response.status}`);
      }
      return data;
    }

    function setStatus(message, isError = false) {
      const node = document.getElementById("status");
      node.textContent = message || "";
      node.className = isError ? "status error" : "status";
    }

    function setBanner(text, tone = "") {
      const node = document.getElementById("banner");
      node.textContent = text;
      node.className = tone ? `banner ${tone}` : "banner";
    }

    function buildPresetLines() {
      const preset = state?.preset || {};
      const debug = state?.debug || {};
      return [
        `VM: ${preset.vm_name || preset.profile_name || "n/a"}`,
        `Host: ${preset.beagle_host || "n/a"}`,
        `Node: ${preset.beagle_node || "n/a"}`,
        `VMID: ${preset.beagle_vmid || "n/a"}`,
        `Modi: ${(preset.available_modes || []).join(" ") || "keine"}`,
        `Default: ${preset.default_mode || "n/a"}`,
        `Beagle Stream Client Host: ${preset.beagle_stream_client_host || "n/a"}`,
        `Preset Quelle: ${debug.preset_source || "n/a"}`,
        `Preset Datei: ${debug.preset_file || "n/a"}`,
        `Live Medium: ${debug.live_medium || "n/a"}`,
        `Log-Verzeichnis: ${state?.log_dir || "/tmp/pve-thin-client-logs"}`
      ];
    }

    function renderModeCards(modes) {
      const grid = document.getElementById("mode-grid");
      grid.innerHTML = "";
      ["BEAGLE_STREAM_CLIENT", "SPICE", "NOVNC", "DCV"].forEach((mode) => {
        const available = modes.includes(mode);
        const button = document.createElement("button");
        button.type = "button";
        button.className = `mode-card${available ? "" : " unavailable"}${selectedMode === mode ? " selected" : ""}`;
        button.innerHTML = `<strong>${mode}</strong><span>${MODE_META[mode]}</span>`;
        button.addEventListener("click", () => {
          if (!available) return;
          selectedMode = mode;
          renderState();
        });
        grid.appendChild(button);
      });
    }

    function renderDisks(disks) {
      const select = document.getElementById("disk-select");
      select.innerHTML = "";
      if (!disks.length) {
        const option = document.createElement("option");
        option.textContent = "Keine Zielplatten gefunden";
        select.appendChild(option);
        return;
      }
      disks.forEach((disk) => {
        const option = document.createElement("option");
        option.value = disk.device;
        option.textContent = `${disk.device}  ${disk.model || "disk"}  ${disk.size || ""}  ${disk.transport || ""}`;
        select.appendChild(option);
      });
    }

    function renderState() {
      const preset = state?.preset || {};
      const debug = state?.debug || {};
      const disks = state?.disks || [];
      const modes = preset.available_modes || [];
      const presetReady = Boolean(preset.preset_active);

      if (!selectedMode || !modes.includes(selectedMode)) {
        selectedMode = preset.default_mode && modes.includes(preset.default_mode) ? preset.default_mode : (modes[0] || null);
      }

      document.getElementById("vm-name").textContent = preset.vm_name || preset.profile_name || "VM-Profil nicht erkannt";
      document.getElementById("vm-hint").textContent = presetReady
        ? "Dieses Medium ist an eine bestimmte VM gebunden. Waehle nur Modus und Zielplatte."
        : "Das gebuendelte VM-Preset wurde nicht gefunden. In diesem Fall ist das Textmenue der sichere Fallback.";
      document.getElementById("meta-preset").textContent = presetReady ? "bereit" : "fehlt";
      document.getElementById("meta-host").textContent = preset.beagle_host || "n/a";
      document.getElementById("meta-node").textContent =
        preset.beagle_node && preset.beagle_vmid ? `${preset.beagle_node} / ${preset.beagle_vmid}` : "n/a";
      document.getElementById("meta-modes").textContent = modes.length ? modes.join("  ") : "keine";
      document.getElementById("detail-preset-file").textContent = debug.preset_file || "n/a";
      document.getElementById("detail-preset-source").textContent = debug.preset_source || "n/a";
      document.getElementById("detail-live-medium").textContent = debug.live_medium || "n/a";
      document.getElementById("detail-live-assets").textContent = debug.live_asset_dir || "n/a";
      document.getElementById("detail-log-dir").textContent = state?.log_dir || "/tmp/pve-thin-client-logs";

      if (presetReady) {
        setBanner("Preset erkannt. Die grafische Ansicht bleibt bewusst schlank und startet die eigentliche Installation nur in einem separaten Terminal.", "ok");
      } else {
        setBanner(`Preset fehlt. Quelle: ${debug.preset_source || "unbekannt"}, Datei: ${debug.preset_file || "n/a"}. Nutze in diesem Fall das Textmenue oder pruefe die USB-Logs.`, "warn");
      }

      renderModeCards(modes);
      renderDisks(disks);

      document.getElementById("install-btn").disabled = !presetReady || !selectedMode || !disks.length;
    }

    async function loadState() {
      setStatus("Lade Installer-Zustand...");
      state = await api("/api/state");
      renderState();
      setStatus("");
    }

    async function postAction(action, payload = {}) {
      try {
        await api(`/api/${action}`, "POST", payload);
        return true;
      } catch (error) {
        setStatus(error.message, true);
        return false;
      }
    }

    document.getElementById("install-btn").addEventListener("click", async () => {
      const disk = document.getElementById("disk-select").value;
      if (!selectedMode) {
        setStatus("Kein Streaming-Modus verfuegbar.", true);
        return;
      }
      if (!disk || disk.startsWith("Keine Zielplatten")) {
        setStatus("Keine Zielplatte ausgewaehlt.", true);
        return;
      }
      setStatus("Installation wird in einem Terminal gestartet...");
      if (await postAction("install", { mode: selectedMode, disk })) {
        setStatus(`Installation fuer ${selectedMode} auf ${disk} gestartet.`);
      }
    });

    document.getElementById("shell-btn").addEventListener("click", () => postAction("shell"));
    document.getElementById("reload-btn").addEventListener("click", () => loadState().catch((error) => setStatus(error.message, true)));
    document.getElementById("preset-btn").addEventListener("click", () => window.alert(buildPresetLines().join("\\n")));
    document.getElementById("reboot-btn").addEventListener("click", () => postAction("reboot"));
    document.getElementById("poweroff-btn").addEventListener("click", () => postAction("poweroff"));

    loadState().catch((error) => {
      setBanner("Der grafische Installer konnte den Initialzustand nicht lesen. Wechsle in das Textmenue oder pruefe die Logs unter /tmp/pve-thin-client-logs.", "warn");
      setStatus(error.message, true);
    });
  </script>
</body>
</html>
"""


def run_json_command(*args):
    command = list(args)
    if command and Path(command[0]) == LOCAL_INSTALLER and os.geteuid() != 0 and shutil.which("sudo"):
        command = [
            "sudo",
            "-n",
            "env",
            f"PVE_THIN_CLIENT_LOG_DIR={LOG_DIR}",
            f"PVE_THIN_CLIENT_LOG_SESSION_ID={os.environ.get('PVE_THIN_CLIENT_LOG_SESSION_ID', LOG_DIR.name)}",
            "PVE_THIN_CLIENT_PRESET_LOAD_RETRIES=1",
            "PVE_THIN_CLIENT_PRESET_LOAD_RETRY_DELAY=0",
            *command,
        ]
    logging.info("run_json_command: %s", " ".join(shlex.quote(part) for part in command))
    result = subprocess.run(command, capture_output=True, text=True, timeout=45)
    logging.info(
        "command result rc=%s stdout=%s stderr=%s",
        result.returncode,
        (result.stdout or "").strip(),
        (result.stderr or "").strip(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "command failed")
    return json.loads(result.stdout or "{}")


def build_state():
    state = run_json_command(str(LOCAL_INSTALLER), "--print-ui-state-json")
    logging.info("build_state: %s", state)
    return state


def spawn_terminal(command, title):
    xterm = shutil.which("xterm")
    if not xterm:
        raise RuntimeError("xterm is not installed in the live environment")

    wrapped = " ".join(shlex.quote(part) for part in command)
    shell_cmd = f"{wrapped}; code=$?; printf '\\n\\nExit code: %s\\nPress ENTER to close.' \"$code\"; read _"
    subprocess.Popen(
        [
            xterm,
            "-title",
            title,
            "-fa",
            "DejaVu Sans Mono",
            "-fs",
            "11",
            "-bg",
            "#07111b",
            "-fg",
            "#f5eadf",
            "-geometry",
            "136x40",
            "-e",
            "bash",
            "-lc",
            shell_cmd,
        ]
    )
    logging.info("spawned terminal %s with command %s", title, command)


def install_target(mode, disk):
    if mode not in {"BEAGLE_STREAM_CLIENT", "SPICE", "NOVNC", "DCV"}:
        raise RuntimeError(f"unsupported mode: {mode}")
    if not disk.startswith("/dev/"):
        raise RuntimeError(f"invalid disk: {disk}")

    spawn_terminal(
        [
            "sudo",
            str(LOCAL_INSTALLER),
            "--mode",
            mode,
            "--target-disk",
            disk,
            "--yes",
        ],
        f"Beagle OS Install {mode}",
    )
    logging.info("requested install mode=%s disk=%s", mode, disk)


def launch_shell():
    spawn_terminal(["bash", "--login"], "Beagle OS Shell")
    logging.info("requested shell")


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path):
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = "image/jpeg"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/state":
            try:
                self._send_json(build_state())
            except Exception as exc:  # noqa: BLE001
                logging.exception("failed to build UI state")
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if parsed.path.startswith("/assets/"):
            asset_name = unquote(parsed.path.removeprefix("/assets/"))
            self._send_file(ASSET_DIR / asset_name)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw.decode("utf-8") or "{}")

        try:
            if parsed.path == "/api/install":
                install_target(str(payload.get("mode", "")).upper(), str(payload.get("disk", "")))
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/shell":
                launch_shell()
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/reboot":
                subprocess.Popen(["sudo", "reboot"])
                self._send_json({"ok": True})
                return
            if parsed.path == "/api/poweroff":
                subprocess.Popen(["sudo", "poweroff"])
                self._send_json({"ok": True})
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as exc:  # noqa: BLE001
            logging.exception("POST handler failed for %s", parsed.path)
            self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, _format, *_args):
        return


def fallback_to_tui():
    logging.warning("falling back to TUI menu")
    os.execv(str(FALLBACK_MENU), [str(FALLBACK_MENU)])


def should_use_graphical_ui(state):
    preset = state.get("preset", {}) if isinstance(state, dict) else {}
    return bool(preset.get("preset_active"))


def main():
    if not LOCAL_INSTALLER.is_file() or not FALLBACK_MENU.is_file():
        raise SystemExit("Installer UI dependencies are missing.")

    logging.info("starting installer UI display=%s", os.environ.get("DISPLAY", ""))
    browser = shutil.which("chromium") or shutil.which("chromium-browser")
    if not browser or not os.environ.get("DISPLAY"):
        fallback_to_tui()

    try:
        initial_state = build_state()
    except Exception:  # noqa: BLE001
        logging.exception("unable to build initial graphical installer state")
        fallback_to_tui()
        return

    if not should_use_graphical_ui(initial_state):
        logging.warning("graphical installer disabled because no bundled preset is active")
        fallback_to_tui()
        return

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        browser_env = os.environ.copy()
        browser_env.setdefault("LANG", "de_DE.UTF-8")
        browser_env.setdefault("LC_ALL", "de_DE.UTF-8")
        subprocess.run(
            [
                browser,
                f"--app=http://{HOST}:{PORT}/",
                "--kiosk",
                "--incognito",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-translate",
                "--disable-features=Translate,TranslateUI,OptimizationGuideModelDownloading,OnDeviceTranslation,MediaRouter,GlobalMediaControls",
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-gpu-rasterization",
                "--disable-session-crashed-bubble",
                "--disable-infobars",
                "--noerrdialogs",
                "--password-store=basic",
                "--lang=de-DE",
                "--check-for-update-interval=31536000",
                "--window-size=1440,900",
            ],
            env=browser_env,
            check=False,
        )
    finally:
        logging.info("shutting down installer UI")
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

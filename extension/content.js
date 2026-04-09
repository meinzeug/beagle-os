(() => {
  const PRODUCT_LABEL = "Beagle OS";
  const MENU_TEXT = "Konsole";
  const BUTTON_MARKER = "data-beagle-integration";
  const STYLE_ID = "beagle-os-extension-style";
  const OVERLAY_ID = "beagle-os-extension-overlay";
  const common = window.BeagleExtensionCommon;
  const virtualizationService = window.BeagleExtensionVirtualizationService;
  const platformService = window.BeagleExtensionPlatformService;

  if (!common) throw new Error("BeagleExtensionCommon must be loaded before extension/content.js");
  if (!virtualizationService) throw new Error("BeagleExtensionVirtualizationService must be loaded before extension/content.js");
  if (!platformService) throw new Error("BeagleExtensionPlatformService must be loaded before extension/content.js");

  const sleep = common.sleep;

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      #${OVERLAY_ID} { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.58); z-index: 2147483647; display: flex; align-items: center; justify-content: center; padding: 24px; }
      #${OVERLAY_ID} .beagle-modal { width: min(980px, 100%); max-height: calc(100vh - 48px); overflow: auto; background: linear-gradient(180deg, #fff8ef 0%, #ffffff 100%); border: 1px solid #fed7aa; border-radius: 22px; box-shadow: 0 30px 70px rgba(15, 23, 42, 0.25); color: #111827; }
      #${OVERLAY_ID} .beagle-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding: 24px 28px 18px; background: radial-gradient(circle at top right, rgba(59,130,246,0.12), transparent 30%), radial-gradient(circle at top left, rgba(249,115,22,0.18), transparent 36%); border-bottom: 1px solid #fdba74; }
      #${OVERLAY_ID} .beagle-title { font: 700 28px/1.1 'Trebuchet MS', 'Segoe UI', sans-serif; margin: 0 0 6px; }
      #${OVERLAY_ID} .beagle-subtitle { margin: 0; color: #7c2d12; font-size: 14px; }
      #${OVERLAY_ID} .beagle-close { border: 0; background: #111827; color: #fff; border-radius: 999px; width: 36px; height: 36px; cursor: pointer; font-size: 20px; line-height: 36px; }
      #${OVERLAY_ID} .beagle-body { padding: 22px 28px 28px; display: grid; gap: 18px; }
      #${OVERLAY_ID} .beagle-banner { padding: 12px 14px; border-radius: 14px; font-weight: 600; }
      #${OVERLAY_ID} .beagle-banner.info { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }
      #${OVERLAY_ID} .beagle-banner.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }
      #${OVERLAY_ID} .beagle-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
      #${OVERLAY_ID} .beagle-card { background: linear-gradient(180deg, #ffffff 0%, #fffaf3 100%); border: 1px solid #d6d3d1; border-radius: 18px; padding: 16px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 8px 20px rgba(15, 23, 42, 0.06); }
      #${OVERLAY_ID} .beagle-card h3 { margin: -16px -16px 14px; padding: 12px 16px; border-bottom: 1px solid #fed7aa; border-radius: 18px 18px 0 0; background: linear-gradient(90deg, #fff1dc 0%, #fff7ed 52%, #eef6ff 100%); font: 700 15px/1.2 'Trebuchet MS', 'Segoe UI', sans-serif; color: #7c2d12; }
      #${OVERLAY_ID} .beagle-kv { display: grid; gap: 8px; }
      #${OVERLAY_ID} .beagle-kv-row { display: grid; gap: 6px; padding: 10px 12px; border: 1px solid #e7e5e4; border-left: 4px solid #f97316; border-radius: 12px; background: #ffffff; }
      #${OVERLAY_ID} .beagle-kv-row:nth-child(even) { background: #f8fbff; border-left-color: #0ea5e9; }
      #${OVERLAY_ID} .beagle-kv-row strong { color: #9a3412; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
      #${OVERLAY_ID} .beagle-kv-row span { word-break: break-word; color: #111827; font-weight: 600; line-height: 1.45; }
      #${OVERLAY_ID} .beagle-actions { display: flex; flex-wrap: wrap; gap: 10px; }
      #${OVERLAY_ID} .beagle-btn { border: 0; border-radius: 999px; padding: 10px 16px; font-weight: 700; cursor: pointer; }
      #${OVERLAY_ID} .beagle-btn.primary { background: linear-gradient(135deg, #f97316, #0ea5e9); color: #fff; }
      #${OVERLAY_ID} .beagle-btn.secondary { background: #fff; color: #111827; border: 1px solid #d1d5db; }
      #${OVERLAY_ID} .beagle-code { width: 100%; min-height: 180px; resize: vertical; border-radius: 14px; border: 1px solid #d1d5db; padding: 12px; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #0f172a; color: #e2e8f0; }
      #${OVERLAY_ID} .beagle-notes { margin: 0; padding-left: 18px; }
      #${OVERLAY_ID} .beagle-muted { color: #6b7280; }
    `;
    document.head.appendChild(style);
  }

  function removeOverlay() {
    document.getElementById(OVERLAY_ID)?.remove();
  }

  function escapeHtml(text) {
    return String(text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function maskSecret(value) {
    if (!value) return "nicht gesetzt";
    if (value.length <= 4) return "****";
    return `${value.slice(0, 2)}***${value.slice(-2)}`;
  }

  async function copyText(text, message) {
    const value = String(text || "");
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      window.alert(message || "In die Zwischenablage kopiert.");
    } catch {
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
      window.alert(message || "In die Zwischenablage kopiert.");
    }
  }

  function parseDescriptionMeta(description) {
    const meta = {};
    String(description || "")
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      .split("\n")
      .forEach((rawLine) => {
        const line = rawLine.trim();
        const index = line.indexOf(":");
        if (index <= 0) return;
        const key = line.slice(0, index).trim().toLowerCase();
        const value = line.slice(index + 1).trim();
        if (key && !(key in meta)) meta[key] = value;
      });
    return meta;
  }

  function firstGuestIpv4(interfaces) {
    for (const iface of Array.isArray(interfaces) ? interfaces : []) {
      for (const address of Array.isArray(iface?.["ip-addresses"]) ? iface["ip-addresses"] : []) {
        const ip = address?.["ip-address"] || "";
        if (address?.["ip-address-type"] !== "ipv4") continue;
        if (!ip || /^127\./.test(ip) || /^169\.254\./.test(ip)) continue;
        return ip;
      }
    }
    return "";
  }

  function buildEndpointEnv(profile) {
    const endpointProfileName = profile.expectedProfileName || `vm-${profile.vmid}`;
    return [
      'PVE_THIN_CLIENT_MODE="MOONLIGHT"',
      `PVE_THIN_CLIENT_PROFILE_NAME="${endpointProfileName}"`,
      'PVE_THIN_CLIENT_AUTOSTART="1"',
      `PVE_THIN_CLIENT_PROXMOX_HOST="${profile.proxmoxHost || window.location.hostname}"`,
      'PVE_THIN_CLIENT_PROXMOX_PORT="8006"',
      `PVE_THIN_CLIENT_PROXMOX_NODE="${profile.node || ""}"`,
      `PVE_THIN_CLIENT_PROXMOX_VMID="${String(profile.vmid || "")}"`,
      `PVE_THIN_CLIENT_BEAGLE_MANAGER_URL="${profile.managerUrl || ""}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_HOST="${profile.streamHost || ""}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_PORT="${profile.moonlightPort || ""}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_APP="${profile.app || "Desktop"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION="${profile.resolution || "auto"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_FPS="${profile.fps || "60"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_BITRATE="${profile.bitrate || "20000"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC="${profile.codec || "H.264"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER="${profile.decoder || "auto"}"`,
      `PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG="${profile.audio || "stereo"}"`,
      `PVE_THIN_CLIENT_SUNSHINE_API_URL="${profile.sunshineApiUrl || ""}"`,
      `PVE_THIN_CLIENT_SUNSHINE_USERNAME="${profile.sunshineUsername || ""}"`,
      `PVE_THIN_CLIENT_SUNSHINE_PASSWORD="${profile.sunshinePassword || ""}"`,
      `PVE_THIN_CLIENT_SUNSHINE_PIN="${profile.sunshinePin || ""}"`
    ].join("\n") + "\n";
  }

  function buildNotes(profile) {
    const notes = [];
    if (!profile.streamHost) notes.push("Kein Moonlight-/Sunshine-Ziel in der VM-Metadatenbeschreibung gefunden.");
    if (!profile.sunshineApiUrl) notes.push("Keine Sunshine API URL gesetzt. Pairing und Healthchecks koennen nicht vorab validiert werden.");
    if (!profile.sunshinePassword) notes.push("Kein Sunshine-Passwort hinterlegt. Fuer direkte API-Aktionen ist dann ein vorregistriertes Zertifikat oder manuelles Pairing noetig.");
    if (!profile.guestIp) notes.push("Keine Guest-Agent-IPv4 erkannt. Beagle kann dann nur mit Metadaten arbeiten.");
    if (!notes.length) notes.push("VM-Profil ist vollstaendig genug fuer einen vorkonfigurierten Beagle-Endpoint mit Moonlight-Autostart.");
    if (profile.assignedTarget) notes.push(`Endpoint ist auf Ziel-VM ${profile.assignedTarget.name} (#${profile.assignedTarget.vmid}) zugewiesen.`);
    if (profile.appliedPolicy?.name) notes.push(`Manager-Policy aktiv: ${profile.appliedPolicy.name}.`);
    if (profile.compliance?.status === "drifted") notes.push(`Endpoint driftet vom gewuenschten Profil ab (${String(profile.compliance.drift_count || 0)} Abweichungen).`);
    if (profile.compliance?.status === "degraded") notes.push(`Endpoint ist konfigurationsgleich, aber betrieblich degradiert (${String(profile.compliance.alert_count || 0)} Warnungen).`);
    if (Number(profile.pendingActionCount || 0) > 0) notes.push(`Fuer diesen Endpoint warten ${String(profile.pendingActionCount)} Beagle-Aktion(en) auf Ausfuehrung.`);
    if (profile.lastAction?.action) notes.push(`Letzte Endpoint-Aktion: ${profile.lastAction.action} (${formatActionState(profile.lastAction.ok)}).`);
    if (profile.lastAction?.stored_artifact_path) notes.push("Diagnoseartefakt ist zentral auf dem Beagle-Manager gespeichert.");
    return notes;
  }

  function formatActionState(ok) {
    if (ok === true) return "ok";
    if (ok === false) return "error";
    return "pending";
  }

  function installerTargetState(profile, state) {
    if (profile?.installerTargetEligible === false) {
      return {
        label: "Ziel ungeeignet",
        message: profile.installerTargetMessage || "Diese VM wird nicht als Streaming-Ziel angeboten.",
        unsupported: true
      };
    }
    if (String(state?.status || "").toLowerCase() === "ready") {
      return {
        label: "USB Installer bereit",
        message: state?.message || "Das VM-spezifische USB-Installer-Skript kann direkt geladen werden.",
        unsupported: false
      };
    }
    return {
      label: "Sunshine wird vorbereitet",
      message: state?.message || "Die VM wird fuer Sunshine und den Internet-Stream vorbereitet.",
      unsupported: false
    };
  }

  function shouldReuseInstallerPrepState(state) {
    const status = String(state?.status || "").toLowerCase();
    if (!state) return false;
    if (state.ready) return true;
    return Boolean(status) && !["idle", "error", "failed"].includes(status);
  }

  const installerEligibilityCache = new Map();

  function getInstallerEligibilityKey(ctx) {
    return `${String(ctx?.node || "")}:${String(ctx?.vmid || "")}`;
  }

  async function getVmInstallerEligibility(ctx) {
    const key = getInstallerEligibilityKey(ctx);
    if (installerEligibilityCache.has(key)) {
      return installerEligibilityCache.get(key);
    }
    const pending = platformService.fetchInstallerTargetEligibility(ctx);
    installerEligibilityCache.set(key, pending);
    return pending;
  }

  async function resolveVmProfile(ctx) {
    const [config, resources, guestInterfaces, installerUrl, installerIsoUrl, controlPlaneHealthUrl, endpointPayload, installerPrep] = await Promise.all([
      virtualizationService.getVmConfig(ctx),
      virtualizationService.listVms().catch(() => []),
      virtualizationService.getVmGuestInterfaces(ctx).catch(() => []),
      platformService.resolveUsbInstallerUrl(ctx),
      platformService.resolveInstallerIsoUrl(ctx),
      platformService.resolveControlPlaneHealthUrl(),
      platformService.fetchPublicVmState(ctx.vmid),
      platformService.fetchInstallerPreparation(ctx.vmid).catch(() => null)
    ]);

    const resource = (Array.isArray(resources) ? resources : []).find(
      (item) => item && item.type === "qemu" && Number(item.vmid) === Number(ctx.vmid)
    ) || {};
    const meta = parseDescriptionMeta(config?.description || "");
    const guestIp = firstGuestIpv4(guestInterfaces);
    const controlPlaneProfile = endpointPayload?.profile || null;
    const streamHost = controlPlaneProfile?.stream_host || meta["moonlight-host"] || meta["sunshine-ip"] || meta["sunshine-host"] || guestIp || "";
    const moonlightPort = controlPlaneProfile?.moonlight_port || meta["moonlight-port"] || meta["beagle-public-moonlight-port"] || "";
    const sunshineApiUrl = controlPlaneProfile?.sunshine_api_url || meta["sunshine-api-url"] || (streamHost ? `https://${streamHost}:${moonlightPort ? Number(moonlightPort) + 1 : 47990}` : "");
    const profile = {
      vmid: Number(ctx.vmid),
      node: ctx.node,
      name: config?.name || resource?.name || `vm-${ctx.vmid}`,
      status: resource?.status || "unknown",
      guestIp,
      streamHost,
      moonlightPort,
      sunshineApiUrl,
      sunshineUsername: controlPlaneProfile?.sunshine_username || meta["sunshine-user"] || "",
      sunshinePassword: meta["sunshine-password"] || "",
      sunshinePin: meta["sunshine-pin"] || String(ctx.vmid % 10000).padStart(4, "0"),
      app: controlPlaneProfile?.moonlight_app || meta["moonlight-app"] || meta["sunshine-app"] || "Desktop",
      resolution: controlPlaneProfile?.moonlight_resolution || meta["moonlight-resolution"] || "auto",
      fps: controlPlaneProfile?.moonlight_fps || meta["moonlight-fps"] || "60",
      bitrate: controlPlaneProfile?.moonlight_bitrate || meta["moonlight-bitrate"] || "20000",
      codec: controlPlaneProfile?.moonlight_video_codec || meta["moonlight-video-codec"] || "H.264",
      decoder: controlPlaneProfile?.moonlight_video_decoder || meta["moonlight-video-decoder"] || "auto",
      audio: controlPlaneProfile?.moonlight_audio_config || meta["moonlight-audio-config"] || "stereo",
      proxmoxHost: meta["proxmox-host"] || window.location.hostname,
      installerUrl,
      installerWindowsUrl: controlPlaneProfile?.installer_windows_url || `/beagle-api/api/v1/vms/${encodeURIComponent(String(ctx.vmid))}/installer.ps1`,
      installerIsoUrl: controlPlaneProfile?.installer_iso_url || installerIsoUrl,
      controlPlaneHealthUrl,
      managerUrl: common.managerUrlFromHealthUrl(controlPlaneHealthUrl),
      endpointSummary: endpointPayload?.endpoint || null,
      compliance: endpointPayload?.compliance || null,
      lastAction: endpointPayload?.last_action || null,
      pendingActionCount: endpointPayload?.pending_action_count || 0,
      installerPrep,
      installerTargetEligible: typeof controlPlaneProfile?.installer_target_eligible === "boolean" ? controlPlaneProfile.installer_target_eligible : Boolean(streamHost),
      installerTargetMessage: controlPlaneProfile?.installer_target_message || "",
      assignedTarget: controlPlaneProfile?.assigned_target || null,
      assignmentSource: controlPlaneProfile?.assignment_source || "",
      appliedPolicy: controlPlaneProfile?.applied_policy || null,
      expectedProfileName: controlPlaneProfile?.expected_profile_name || ""
    };
    profile.notes = buildNotes(profile);
    if (!profile.endpointSummary) profile.notes.push("Endpoint hat noch keinen Check-in an die Beagle Control Plane geliefert.");
    profile.endpointEnv = buildEndpointEnv(profile);
    return profile;
  }

  function kvRow(label, value) {
    return `<div class="beagle-kv-row"><strong>${label}</strong><span>${value || '<span class="beagle-muted">nicht gesetzt</span>'}</span></div>`;
  }

  function renderProfileModal(profile) {
    const overlay = document.createElement("div");
    const notesHtml = profile.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("");
    const profileJson = JSON.stringify(
      {
        vmid: profile.vmid,
        node: profile.node,
        name: profile.name,
        status: profile.status,
        stream_host: profile.streamHost,
        sunshine_api_url: profile.sunshineApiUrl,
        sunshine_username: profile.sunshineUsername,
        sunshine_password_configured: Boolean(profile.sunshinePassword),
        sunshine_pin: profile.sunshinePin,
        moonlight_app: profile.app,
        moonlight_resolution: profile.resolution,
        moonlight_fps: profile.fps,
        moonlight_bitrate: profile.bitrate,
        moonlight_video_codec: profile.codec,
        moonlight_video_decoder: profile.decoder,
        moonlight_audio_config: profile.audio,
        manager_url: profile.managerUrl,
        installer_url: profile.installerUrl,
        installer_windows_url: profile.installerWindowsUrl,
        installer_iso_url: profile.installerIsoUrl,
        control_plane_health_url: profile.controlPlaneHealthUrl,
        assigned_target: profile.assignedTarget,
        assignment_source: profile.assignmentSource,
        applied_policy: profile.appliedPolicy,
        expected_profile_name: profile.expectedProfileName,
        endpoint_summary: profile.endpointSummary,
        compliance: profile.compliance,
        last_action: profile.lastAction,
        pending_action_count: profile.pendingActionCount
      },
      null,
      2
    );

    overlay.id = OVERLAY_ID;
    overlay.innerHTML = `
      <div class="beagle-modal" role="dialog" aria-modal="true" aria-label="Beagle OS Profil">
        <div class="beagle-header">
          <div>
            <h2 class="beagle-title">Beagle Profil fuer VM ${escapeHtml(profile.name)} (#${String(profile.vmid)})</h2>
            <p class="beagle-subtitle">Moonlight-Endpunkt, Sunshine-Ziel und Proxmox-Bereitstellung in einer Sicht.</p>
          </div>
          <button type="button" class="beagle-close" aria-label="Schliessen">×</button>
        </div>
        <div class="beagle-body">
          <div class="beagle-banner ${profile.streamHost ? "info" : "warn"}">${escapeHtml(profile.streamHost ? `Streaming-Ziel erkannt: ${profile.streamHost}` : "Streaming-Ziel fehlt in den VM-Metadaten.")}</div>
          <div class="beagle-banner ${profile.installerTargetEligible === false ? "warn" : "info"}"><strong>${escapeHtml(installerTargetState(profile, profile.installerPrep).label)}</strong>: ${escapeHtml(installerTargetState(profile, profile.installerPrep).message)}</div>
          <div class="beagle-actions">
            ${profile.installerTargetEligible === false ? "" : '<button type="button" class="beagle-btn primary" data-beagle-action="download">USB Installer Skript</button>'}
            ${profile.installerTargetEligible === false ? "" : '<button type="button" class="beagle-btn secondary" data-beagle-action="download-windows">Windows USB Installer</button>'}
            <button type="button" class="beagle-btn secondary" data-beagle-action="download-iso">ISO Download</button>
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-web-ui">Open Web UI</button>
            <button type="button" class="beagle-btn secondary" data-beagle-action="copy-json">Profil JSON kopieren</button>
            <button type="button" class="beagle-btn secondary" data-beagle-action="copy-env">Endpoint Env kopieren</button>
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-sunshine">Sunshine Web UI</button>
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-health">Control Plane Status</button>
          </div>
          <div class="beagle-grid">
            <section class="beagle-card"><h3>VM</h3><div class="beagle-kv">
              ${kvRow("Name", escapeHtml(profile.name))}
              ${kvRow("VMID", escapeHtml(String(profile.vmid)))}
              ${kvRow("Node", escapeHtml(profile.node))}
              ${kvRow("Status", escapeHtml(profile.status))}
              ${kvRow("Guest IP", escapeHtml(profile.guestIp || ""))}
            </div></section>
            <section class="beagle-card"><h3>Streaming</h3><div class="beagle-kv">
              ${kvRow("Stream Host", escapeHtml(profile.streamHost || ""))}
              ${kvRow("Moonlight Port", escapeHtml(profile.moonlightPort || "default"))}
              ${kvRow("Sunshine API", escapeHtml(profile.sunshineApiUrl || ""))}
              ${kvRow("App", escapeHtml(profile.app))}
              ${kvRow("Manager", escapeHtml(profile.managerUrl || ""))}
              ${kvRow("Assigned Target", escapeHtml(profile.assignedTarget ? `${profile.assignedTarget.name} (#${profile.assignedTarget.vmid})` : ""))}
              ${kvRow("Assignment Source", escapeHtml(profile.assignmentSource || ""))}
              ${kvRow("Applied Policy", escapeHtml(profile.appliedPolicy?.name || ""))}
              ${kvRow("USB Script", escapeHtml(profile.installerUrl))}
              ${kvRow("Windows USB Script", escapeHtml(profile.installerWindowsUrl))}
              ${kvRow("Installer ISO", escapeHtml(profile.installerIsoUrl))}
              ${kvRow("Health", escapeHtml(profile.controlPlaneHealthUrl))}
            </div></section>
            <section class="beagle-card"><h3>Endpoint Defaults</h3><div class="beagle-kv">
              ${kvRow("Resolution", escapeHtml(profile.resolution))}
              ${kvRow("FPS", escapeHtml(profile.fps))}
              ${kvRow("Bitrate", escapeHtml(profile.bitrate))}
              ${kvRow("Codec", escapeHtml(profile.codec))}
              ${kvRow("Decoder", escapeHtml(profile.decoder))}
              ${kvRow("Audio", escapeHtml(profile.audio))}
            </div></section>
            <section class="beagle-card"><h3>Pairing</h3><div class="beagle-kv">
              ${kvRow("Sunshine User", escapeHtml(profile.sunshineUsername || ""))}
              ${kvRow("Sunshine Password", escapeHtml(maskSecret(profile.sunshinePassword)))}
              ${kvRow("Pairing PIN", escapeHtml(profile.sunshinePin || ""))}
            </div></section>
            <section class="beagle-card"><h3>Endpoint State</h3><div class="beagle-kv">
              ${kvRow("Compliance", escapeHtml(profile.compliance?.status || ""))}
              ${kvRow("Drift Count", escapeHtml(String(profile.compliance?.drift_count || 0)))}
              ${kvRow("Alert Count", escapeHtml(String(profile.compliance?.alert_count || 0)))}
              ${kvRow("Pending Actions", escapeHtml(String(profile.pendingActionCount || 0)))}
              ${kvRow("Last Seen", escapeHtml(profile.endpointSummary?.reported_at || ""))}
              ${kvRow("Target Reachable", escapeHtml(profile.endpointSummary?.moonlight_target_reachable || ""))}
              ${kvRow("Sunshine Reachable", escapeHtml(profile.endpointSummary?.sunshine_api_reachable || ""))}
              ${kvRow("Prepare", escapeHtml(profile.endpointSummary?.prepare_state || ""))}
              ${kvRow("Last Launch", escapeHtml(profile.endpointSummary?.last_launch_mode || ""))}
              ${kvRow("Launch Target", escapeHtml(profile.endpointSummary?.last_launch_target || ""))}
              ${kvRow("Last Action", escapeHtml(profile.lastAction?.action || ""))}
              ${kvRow("Action Result", escapeHtml(formatActionState(profile.lastAction?.ok)))}
              ${kvRow("Action Time", escapeHtml(profile.lastAction?.completed_at || ""))}
              ${kvRow("Action Message", escapeHtml(profile.lastAction?.message || ""))}
              ${kvRow("Stored Artifact", escapeHtml(profile.lastAction?.stored_artifact_path || ""))}
              ${kvRow("Artifact Size", escapeHtml(String(profile.lastAction?.stored_artifact_size || 0)))}
            </div></section>
            <section class="beagle-card"><h3>Installer Readiness</h3><div class="beagle-kv">
              ${kvRow("Zielstatus", escapeHtml(installerTargetState(profile, profile.installerPrep).label))}
              ${kvRow("Prepare", escapeHtml(profile.installerPrep?.status || "idle"))}
              ${kvRow("Phase", escapeHtml(profile.installerPrep?.phase || "inspect"))}
              ${kvRow("Progress", escapeHtml(`${String(profile.installerPrep?.progress || 0)}%`))}
              ${kvRow("Message", escapeHtml(profile.installerPrep?.message || profile.installerTargetMessage || ""))}
            </div></section>
          </div>
          <section class="beagle-card"><h3>Operator Notes</h3><ul class="beagle-notes">${notesHtml}</ul></section>
          <section class="beagle-card"><h3>Beagle Endpoint Env</h3><textarea class="beagle-code" readonly>${escapeHtml(profile.endpointEnv)}</textarea></section>
          <section class="beagle-card"><h3>Profile JSON</h3><textarea class="beagle-code" readonly>${escapeHtml(profileJson)}</textarea></section>
        </div>
      </div>
    `;

    overlay.addEventListener("click", async (event) => {
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
        return;
      }
      if (!(event.target instanceof HTMLElement)) return;
      switch (event.target.getAttribute("data-beagle-action")) {
        case "download":
          if (profile.installerTargetEligible === false) break;
          try {
            let state = await platformService.fetchInstallerPreparation(profile.vmid).catch(() => profile.installerPrep || null);
            if (String(state?.status || "").toLowerCase() === "ready") {
              await platformService.downloadUrl(profile.installerUrl);
              return;
            }
            if (!shouldReuseInstallerPrepState(state)) {
              state = await platformService.prepareInstallerTarget(profile.vmid);
            }
            for (let attempt = 0; attempt < 180; attempt += 1) {
              if (String(state?.status || "").toLowerCase() === "ready") {
                await platformService.downloadUrl(profile.installerUrl);
                return;
              }
              if (String(state?.status || "").toLowerCase() === "error") {
                throw new Error(state?.message || "Installer-Vorbereitung fehlgeschlagen.");
              }
              await sleep(2000);
              state = await platformService.fetchInstallerPreparation(profile.vmid);
            }
            throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
          } catch (error) {
            window.alert(`USB Installer konnte nicht vorbereitet werden: ${error?.message || error}`);
          }
          break;
        case "download-windows":
          if (profile.installerTargetEligible === false) break;
          try {
            let state = await platformService.fetchInstallerPreparation(profile.vmid).catch(() => profile.installerPrep || null);
            if (String(state?.status || "").toLowerCase() === "ready") {
              await platformService.downloadUrl(profile.installerWindowsUrl);
              return;
            }
            if (!shouldReuseInstallerPrepState(state)) {
              state = await platformService.prepareInstallerTarget(profile.vmid);
            }
            for (let attempt = 0; attempt < 180; attempt += 1) {
              if (String(state?.status || "").toLowerCase() === "ready") {
                await platformService.downloadUrl(profile.installerWindowsUrl);
                return;
              }
              if (String(state?.status || "").toLowerCase() === "error") {
                throw new Error(state?.message || "Installer-Vorbereitung fehlgeschlagen.");
              }
              await sleep(2000);
              state = await platformService.fetchInstallerPreparation(profile.vmid);
            }
            throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
          } catch (error) {
            window.alert(`Windows USB Installer konnte nicht vorbereitet werden: ${error?.message || error}`);
          }
          break;
        case "download-iso":
          await platformService.downloadUrl(profile.installerIsoUrl);
          break;
        case "open-web-ui":
          {
            const url = await platformService.webUiUrlWithToken(true);
            window.open(url, "_blank", "noopener,noreferrer");
          }
          break;
        case "copy-json":
          await copyText(profileJson, "Beagle Profil als JSON kopiert.");
          break;
        case "copy-env":
          await copyText(profile.endpointEnv, "Beagle Endpoint-Umgebung kopiert.");
          break;
        case "open-sunshine":
          try {
            const access = await platformService.createSunshineAccess(profile.vmid);
            window.open(access?.url || profile.sunshineApiUrl, "_blank", "noopener,noreferrer");
          } catch (error) {
            window.alert(`Sunshine Web UI konnte nicht geoeffnet werden: ${error?.message || error}`);
          }
          break;
        case "open-health":
          window.open(profile.controlPlaneHealthUrl, "_blank", "noopener,noreferrer");
          break;
        default:
          break;
      }
    });

    document.body.appendChild(overlay);
  }

  async function showProfileModal() {
    const ctx = await virtualizationService.parseVmContext();
    if (!ctx) {
      window.alert("Beagle OS: Keine VM-Ansicht erkannt.");
      return;
    }

    ensureStyles();
    removeOverlay();

    const overlay = document.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = `<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Profil wird geladen</h2><p class="beagle-subtitle">VM ${String(ctx.vmid)} auf Node ${escapeHtml(ctx.node || "")}</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Proxmox-Konfiguration, Guest-Agent-Daten und Beagle-Metadaten werden aufgeloest.</div></div></div>`;
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);

    try {
      const profile = await resolveVmProfile(ctx);
      removeOverlay();
      renderProfileModal(profile);
    } catch (error) {
      removeOverlay();
      window.alert(`Beagle OS: ${error.message}`);
    }
  }

  async function downloadUsbInstaller() {
    const ctx = await virtualizationService.parseVmContext();
    if (!ctx) {
      window.alert("Beagle OS: Keine VM-Ansicht erkannt.");
      return;
    }
    const profile = await resolveVmProfile(ctx);
    if (profile.installerTargetEligible === false) {
      window.alert(profile.installerTargetMessage || "Diese VM ist kein geeignetes Streaming-Ziel.");
      return;
    }
    platformService.downloadUrl(profile.installerUrl).catch((error) => {
      window.alert(`Beagle OS Installer konnte nicht geladen werden: ${error?.message || error}`);
    });
  }

  function createToolbarButton(label, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute(BUTTON_MARKER, label);
    button.className = "x-btn-text";
    button.style.marginLeft = "6px";
    button.style.padding = "4px 10px";
    button.style.border = "1px solid #b5b8c8";
    button.style.background = "#f5f5f5";
    button.style.borderRadius = "3px";
    button.style.cursor = "pointer";
    button.style.lineHeight = "20px";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      onClick();
    });
    return button;
  }

  function isConsoleMenuTrigger(element) {
    const text = String(element.textContent || "").trim();
    return text === MENU_TEXT || text.includes(MENU_TEXT);
  }

  function findToolbarRow() {
    const buttons = Array.from(document.querySelectorAll("button, a, div, span"));
    for (const element of buttons) {
      if (!isConsoleMenuTrigger(element)) continue;
      const row =
        element.closest(".x-toolbar") ||
        element.closest(".x-box-inner") ||
        element.closest(".x-panel-header") ||
        element.parentElement;
      if (row) return row;
    }
    return null;
  }

  function ensureToolbarButtons() {
    document.querySelectorAll(`[${BUTTON_MARKER}]`).forEach((node) => {
      if (!virtualizationService.isVmView()) node.remove();
    });

    if (!virtualizationService.isVmView()) return;

    const toolbar = findToolbarRow();
    if (!toolbar) return;

    const existingButton = toolbar.querySelector(`[${BUTTON_MARKER}="${PRODUCT_LABEL}"]`);
    const existingWebButton = toolbar.querySelector(`[${BUTTON_MARKER}="${PRODUCT_LABEL} Web UI"]`);

    if (!existingButton) {
      const profileButton = createToolbarButton(PRODUCT_LABEL, showProfileModal);
      profileButton.title = "Zeigt das aufgeloeste Beagle-Profil fuer diese VM und bietet Download-, Export- und Health-Aktionen.";
      toolbar.appendChild(profileButton);
    }
    if (!existingWebButton) {
      const webUiButton = createToolbarButton(`${PRODUCT_LABEL} Web UI`, async () => {
        const url = await platformService.webUiUrlWithToken(true);
        window.open(url, "_blank", "noopener,noreferrer");
      });
      webUiButton.title = "Oeffnet die zentrale Beagle Web UI auf diesem Host.";
      toolbar.appendChild(webUiButton);
    }
  }

  function getVisibleMenu() {
    const menus = Array.from(document.querySelectorAll(".x-menu, [role='menu']"));
    return menus.find((menu) => menu.offsetParent !== null) || null;
  }

  function menuAlreadyHasLabel(menu, label) {
    return Array.from(menu.querySelectorAll("*")).some((node) => String(node.textContent || "").trim() === label);
  }

  function createMenuItem(label, onClick) {
    const item = document.createElement("a");
    item.href = "#";
    item.setAttribute(BUTTON_MARKER, label);
    item.className = "x-menu-item";
    item.style.display = "block";
    item.style.padding = "4px 24px";
    item.style.cursor = "pointer";
    item.textContent = label;
    item.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      onClick();
    });
    return item;
  }

  function ensureMenuItems() {
    if (!virtualizationService.isVmView()) return;
    const menu = getVisibleMenu();
    if (!menu) return;

    const hasConsoleItems = Array.from(menu.querySelectorAll("*")).some((node) => {
      const text = String(node.textContent || "").trim();
      return text === "noVNC" || text === "SPICE" || text === "xterm.js";
    });

    if (!hasConsoleItems) return;
    if (!menuAlreadyHasLabel(menu, `${PRODUCT_LABEL} Profil`)) {
      menu.appendChild(createMenuItem(`${PRODUCT_LABEL} Profil`, showProfileModal));
    }
    virtualizationService.parseVmContext().then((ctx) => {
      if (!ctx) return;
      return getVmInstallerEligibility(ctx).then((result) => {
        const existingInstaller = Array.from(menu.querySelectorAll(`[${BUTTON_MARKER}]`)).find(
          (node) => String(node.textContent || "").trim() === `${PRODUCT_LABEL} Installer`
        );
        if (result?.eligible) {
          if (!existingInstaller) {
            menu.appendChild(createMenuItem(`${PRODUCT_LABEL} Installer`, downloadUsbInstaller));
          }
          return;
        }
        if (existingInstaller) {
          existingInstaller.remove();
        }
      });
    }).catch(() => {});
  }

  async function boot() {
    for (let i = 0; i < 12; i += 1) {
      ensureToolbarButtons();
      ensureMenuItems();
      await sleep(500);
    }

    window.addEventListener("hashchange", () => {
      ensureToolbarButtons();
      ensureMenuItems();
    });

    document.addEventListener(
      "click",
      () => {
        window.setTimeout(() => {
          ensureToolbarButtons();
          ensureMenuItems();
        }, 50);
      },
      true
    );

    const observer = new MutationObserver(() => {
      ensureToolbarButtons();
      ensureMenuItems();
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  boot();
})();

(() => {
  const PRODUCT_LABEL = "Beagle OS";
  const MENU_TEXT = "Konsole";
  const BUTTON_MARKER = "data-beagle-integration";
  const STYLE_ID = "beagle-os-extension-style";
  const OVERLAY_ID = "beagle-os-extension-overlay";
  const common = window.BeagleExtensionCommon;
  const virtualizationService = window.BeagleExtensionVirtualizationService;
  const platformService = window.BeagleExtensionPlatformService;
  const profileService = window.BeagleExtensionProfileService;
  const profileModal = window.BeagleExtensionProfileModal;
  const vmPageIntegration = window.BeagleExtensionVmPageIntegration;

  if (!common) throw new Error("BeagleExtensionCommon must be loaded before extension/content.js");
  if (!virtualizationService) throw new Error("BeagleExtensionVirtualizationService must be loaded before extension/content.js");
  if (!platformService) throw new Error("BeagleExtensionPlatformService must be loaded before extension/content.js");
  if (!profileService) throw new Error("BeagleExtensionProfileService must be loaded before extension/content.js");
  if (!profileModal) throw new Error("BeagleExtensionProfileModal must be loaded before extension/content.js");
  if (!vmPageIntegration) throw new Error("BeagleExtensionVmPageIntegration must be loaded before extension/content.js");

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

  function renderProfileModal(profile) {
    profileModal.renderProfileModal({
      profile,
      overlayId: OVERLAY_ID,
      removeOverlay,
      escapeHtml,
      maskSecret,
      copyText,
      platformService,
      profileService,
      sleep
    });
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
    overlay.innerHTML = `<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Profil wird geladen</h2><p class="beagle-subtitle">VM ${String(ctx.vmid)} auf Node ${escapeHtml(ctx.node || "")}</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Host-Konfiguration, Guest-Agent-Daten und Beagle-Metadaten werden aufgeloest.</div></div></div>`;
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);

    try {
      const profile = await profileService.resolveVmProfile(ctx);
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
    const profile = await profileService.resolveVmProfile(ctx);
    if (profile.installerTargetEligible === false) {
      window.alert(profile.installerTargetMessage || "Diese VM ist kein geeignetes Streaming-Ziel.");
      return;
    }
    platformService.downloadUrl(profile.installerUrl).catch((error) => {
      window.alert(`Beagle OS Installer konnte nicht geladen werden: ${error?.message || error}`);
    });
  }

  function openWebUi() {
    return platformService.webUiUrlWithToken(true).then((url) => {
      window.open(url, "_blank", "noopener,noreferrer");
    });
  }

  vmPageIntegration.boot({
    buttonMarker: BUTTON_MARKER,
    downloadUsbInstaller,
    getVmInstallerEligibility,
    menuText: MENU_TEXT,
    openWebUi,
    productLabel: PRODUCT_LABEL,
    showProfileModal,
    sleep,
    virtualizationService
  });
})();

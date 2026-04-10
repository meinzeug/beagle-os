(function() {
  "use strict";

  var PRODUCT_LABEL = "Beagle OS";
  var STYLE_ID = "beagle-os-modal-style";
  var OVERLAY_ID = "beagle-os-overlay";
  var FLEET_LAUNCHER_ID = "beagle-os-fleet-launcher";
  var CREATE_VM_DOM_BUTTON_ID = "beagle-os-create-vm-dom-button";
  var common = window.BeagleUiCommon;
  var virtualizationService = window.BeagleVirtualizationService;
  var platformService = window.BeaglePlatformService;
  var apiClient = window.BeagleUiApiClient;
  var beagleState = window.BeagleUiState;
  var vmProfileState = window.BeagleUiVmProfileState;
  var usbUi = window.BeagleUiUsbUi;
  var renderHelpers = window.BeagleUiRenderHelpers;
  var desktopOverlay = window.BeagleUiDesktopOverlay;
  var profileModal = window.BeagleUiProfileModal;
  var fleetModal = window.BeagleUiFleetModal;
  var provisioningResultModal = window.BeagleUiProvisioningResultModal;
  var provisioningCreateModal = window.BeagleUiProvisioningCreateModal;
  var browserActions = window.BeagleUiBrowserActions;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before beagle-ui.js");
  }
  if (!virtualizationService) {
    throw new Error("BeagleVirtualizationService must be loaded before beagle-ui.js");
  }
  if (!platformService) {
    throw new Error("BeaglePlatformService must be loaded before beagle-ui.js");
  }
  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before beagle-ui.js");
  }
  if (!beagleState) {
    throw new Error("BeagleUiState must be loaded before beagle-ui.js");
  }
  if (!vmProfileState) {
    throw new Error("BeagleUiVmProfileState must be loaded before beagle-ui.js");
  }
  if (!usbUi) {
    throw new Error("BeagleUiUsbUi must be loaded before beagle-ui.js");
  }
  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before beagle-ui.js");
  }
  if (!desktopOverlay) {
    throw new Error("BeagleUiDesktopOverlay must be loaded before beagle-ui.js");
  }
  if (!profileModal) {
    throw new Error("BeagleUiProfileModal must be loaded before beagle-ui.js");
  }
  if (!fleetModal) {
    throw new Error("BeagleUiFleetModal must be loaded before beagle-ui.js");
  }
  if (!provisioningResultModal) {
    throw new Error("BeagleUiProvisioningResultModal must be loaded before beagle-ui.js");
  }
  if (!provisioningCreateModal) {
    throw new Error("BeagleUiProvisioningCreateModal must be loaded before beagle-ui.js");
  }
  if (!browserActions) {
    throw new Error("BeagleUiBrowserActions must be loaded before beagle-ui.js");
  }

  function sleep(ms) {
    return new Promise(function(resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function withNoCache(url) {
    return common.withNoCache(url);
  }

  function resolveControlPlaneHealthUrl() {
    return common.resolveControlPlaneHealthUrl();
  }

  function resolveWebUiUrl() {
    return common.resolveWebUiUrl();
  }

  function normalizeBeagleApiPath(path) {
    return common.normalizeBeagleApiPath(path);
  }

  function showError(message) {
    return browserActions.showError(PRODUCT_LABEL, message);
  }

  function showToast(message) {
    return browserActions.showToast(PRODUCT_LABEL, message);
  }

  function openUrl(url) {
    return browserActions.openUrl(showError, url);
  }

  function triggerDownload(url) {
    return browserActions.triggerDownload(showError, url);
  }

  function webUiUrlWithToken(interactive) {
    var token = getApiToken(Boolean(interactive));
    var target = resolveWebUiUrl();
    if (!token) {
      return target;
    }
    try {
      var parsed = new URL(target, window.location.origin);
      parsed.hash = "beagle_token=" + encodeURIComponent(token);
      return parsed.toString();
    } catch (error) {
      return String(target || "") + "#beagle_token=" + encodeURIComponent(token);
    }
  }

  function getInstallerEligibilityKey(ctx) {
    return beagleState.getInstallerEligibilityKey(ctx);
  }

  function getVmInstallerEligibility(ctx) {
    return beagleState.getVmInstallerEligibility(ctx);
  }

  function openUsbInstaller(ctx) {
    showProfileModal(ctx || {}, { autoPrepareDownload: true });
  }

  function normalizeUiText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function createVmLabels() {
    return [
      normalizeUiText("Create VM"),
      normalizeUiText("Erstelle VM"),
      normalizeUiText(gettext("Create VM"))
    ];
  }

  function getComponentText(component) {
    if (!component) {
      return "";
    }
    if (typeof component.getText === "function") {
      return component.getText() || "";
    }
    return component.text || "";
  }

  function looksLikeCreateVmTrigger(component) {
    var normalized = normalizeUiText(getComponentText(component));
    var labels = createVmLabels();
    return component && (
      component.itemId === "createvm" ||
      component.reference === "createvm" ||
      labels.indexOf(normalized) !== -1
    );
  }

  function selectedNodeName() {
    return virtualizationService.selectedNodeName();
  }

  function apiGetProvisioningCatalog() {
    return platformService.fetchProvisioningCatalog();
  }

  function apiCreateProvisionedVm(payload) {
    return platformService.createVm(payload);
  }

  function apiUpdateProvisionedVm(vmid, payload) {
    return platformService.updateVm(vmid, payload);
  }

  function apiGetProvisioningState(vmid) {
    return platformService.fetchVmProvisioningState(vmid);
  }

  function parseListText(value) {
    return String(value || "")
      .split(/[\n,]+/)
      .map(function(item) { return String(item || "").trim(); })
      .filter(Boolean);
  }

  function buildProvisioningCredentialText(created, state) {
    return provisioningResultModal.buildProvisioningCredentialText(created, state);
  }

  function showProvisioningResultWindow(created) {
    return provisioningResultModal.showProvisioningResultWindow({
      created: created,
      apiGetProvisioningState: apiGetProvisioningState,
      copyText: copyText,
      showProfileModal: showProfileModal
    });
  }

  function showUbuntuBeagleCreateModal(ctx) {
    return provisioningCreateModal.showUbuntuBeagleCreateModal({
      ctx: ctx,
      showError: showError,
      showToast: showToast,
      ensureApiToken: ensureApiToken,
      apiGetProvisioningCatalog: apiGetProvisioningCatalog,
      apiCreateProvisionedVm: apiCreateProvisionedVm,
      apiUpdateProvisionedVm: apiUpdateProvisionedVm,
      virtualizationService: virtualizationService,
      selectedNodeName: selectedNodeName,
      parseListText: parseListText,
      showProfileModal: showProfileModal,
      showProvisioningResultWindow: showProvisioningResultWindow
    });
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = [
      "#" + OVERLAY_ID + " { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); z-index: 100000; display: flex; align-items: center; justify-content: center; padding: 24px; }",
      "#" + OVERLAY_ID + " .beagle-modal { width: min(980px, 100%); max-height: calc(100vh - 48px); overflow: auto; background: linear-gradient(180deg, #fff8ef 0%, #ffffff 100%); border: 1px solid #fed7aa; border-radius: 22px; box-shadow: 0 30px 70px rgba(15, 23, 42, 0.25); color: #111827; }",
      "#" + OVERLAY_ID + " .beagle-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding: 24px 28px 18px; background: radial-gradient(circle at top right, rgba(59,130,246,0.12), transparent 30%), radial-gradient(circle at top left, rgba(249,115,22,0.18), transparent 36%); border-bottom: 1px solid #fdba74; }",
      "#" + OVERLAY_ID + " .beagle-title { font: 700 28px/1.1 'Trebuchet MS', 'Segoe UI', sans-serif; margin: 0 0 6px; }",
      "#" + OVERLAY_ID + " .beagle-subtitle { margin: 0; color: #7c2d12; font-size: 14px; }",
      "#" + OVERLAY_ID + " .beagle-close { border: 0; background: #111827; color: #fff; border-radius: 999px; width: 36px; height: 36px; cursor: pointer; font-size: 20px; line-height: 36px; }",
      "#" + OVERLAY_ID + " .beagle-body { padding: 22px 28px 28px; display: grid; gap: 18px; }",
      "#" + OVERLAY_ID + " .beagle-banner { padding: 12px 14px; border-radius: 14px; font-weight: 600; }",
      "#" + OVERLAY_ID + " .beagle-banner.info { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }",
      "#" + OVERLAY_ID + " .beagle-banner.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }",
      "#" + OVERLAY_ID + " .beagle-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }",
      "#" + OVERLAY_ID + " .beagle-card { background: linear-gradient(180deg, #ffffff 0%, #fffaf3 100%); border: 1px solid #d6d3d1; border-radius: 18px; padding: 16px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 8px 20px rgba(15, 23, 42, 0.06); }",
      "#" + OVERLAY_ID + " .beagle-card h3 { margin: -16px -16px 14px; padding: 12px 16px; border-bottom: 1px solid #fed7aa; border-radius: 18px 18px 0 0; background: linear-gradient(90deg, #fff1dc 0%, #fff7ed 52%, #eef6ff 100%); font: 700 15px/1.2 'Trebuchet MS', 'Segoe UI', sans-serif; color: #7c2d12; }",
      "#" + OVERLAY_ID + " .beagle-kv { display: grid; gap: 8px; }",
      "#" + OVERLAY_ID + " .beagle-kv-row { display: grid; gap: 6px; padding: 10px 12px; border: 1px solid #e7e5e4; border-left: 4px solid #f97316; border-radius: 12px; background: #ffffff; }",
      "#" + OVERLAY_ID + " .beagle-kv-row:nth-child(even) { background: #f8fbff; border-left-color: #0ea5e9; }",
      "#" + OVERLAY_ID + " .beagle-kv-row strong { color: #9a3412; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }",
      "#" + OVERLAY_ID + " .beagle-kv-row span { word-break: break-word; color: #111827; font-weight: 600; line-height: 1.45; }",
      "#" + OVERLAY_ID + " .beagle-actions { display: flex; flex-wrap: wrap; gap: 10px; }",
      "#" + OVERLAY_ID + " .beagle-btn { border: 0; border-radius: 999px; padding: 10px 16px; font-weight: 700; cursor: pointer; }",
      "#" + OVERLAY_ID + " .beagle-btn.primary { background: linear-gradient(135deg, #f97316, #0ea5e9); color: #fff; }",
      "#" + OVERLAY_ID + " .beagle-btn.secondary { background: #fff; color: #111827; border: 1px solid #d1d5db; }",
      "#" + OVERLAY_ID + " .beagle-btn.muted { background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }",
      "#" + OVERLAY_ID + " .beagle-code { width: 100%; min-height: 180px; resize: vertical; border-radius: 14px; border: 1px solid #d1d5db; padding: 12px; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #0f172a; color: #e2e8f0; }",
      "#" + OVERLAY_ID + " .beagle-notes { margin: 0; padding-left: 18px; }",
      "#" + OVERLAY_ID + " .beagle-muted { color: #6b7280; }",
      "#" + OVERLAY_ID + " .beagle-table-wrap { overflow: auto; border-radius: 16px; border: 1px solid #e5e7eb; background: rgba(255,255,255,0.92); }",
      "#" + OVERLAY_ID + " .beagle-table { width: 100%; border-collapse: collapse; min-width: 880px; }",
      "#" + OVERLAY_ID + " .beagle-table th, #" + OVERLAY_ID + " .beagle-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; vertical-align: top; }",
      "#" + OVERLAY_ID + " .beagle-table th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #9a3412; background: #fff7ed; position: sticky; top: 0; }",
      "#" + OVERLAY_ID + " .beagle-badge { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 700; }",
      "#" + OVERLAY_ID + " .beagle-badge.healthy { background: #ecfdf5; color: #047857; }",
      "#" + OVERLAY_ID + " .beagle-badge.degraded { background: #fffbeb; color: #b45309; }",
      "#" + OVERLAY_ID + " .beagle-badge.drifted { background: #fef2f2; color: #b91c1c; }",
      "#" + OVERLAY_ID + " .beagle-badge.stale { background: #eef2ff; color: #4338ca; }",
      "#" + OVERLAY_ID + " .beagle-badge.pending, #" + OVERLAY_ID + " .beagle-badge.unmanaged { background: #eff6ff; color: #1d4ed8; }",
      "#" + OVERLAY_ID + " .beagle-inline-actions { display: flex; flex-wrap: wrap; gap: 8px; }",
      "#" + OVERLAY_ID + " .beagle-mini-btn { border: 1px solid #d1d5db; background: #fff; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }",
      "#" + OVERLAY_ID + " .beagle-select-cell { width: 36px; }",
      "#" + OVERLAY_ID + " .beagle-row-select { width: 16px; height: 16px; accent-color: #ea580c; }",
      "#" + FLEET_LAUNCHER_ID + " { position: fixed; right: 22px; bottom: 22px; z-index: 99999; border: 0; border-radius: 999px; padding: 12px 18px; font: 700 14px/1 'Trebuchet MS', 'Segoe UI', sans-serif; color: #fff; background: linear-gradient(135deg, #f97316, #0ea5e9); box-shadow: 0 18px 40px rgba(15, 23, 42, 0.28); cursor: pointer; }",

      /* ── Desktop Overlay ── */
      "#" + OVERLAY_ID + ".beagle-desktop-mode { padding: 0; background: none; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-scene { position: absolute; inset: 0; overflow: hidden; font-family: 'SF Pro Display', 'Segoe UI', -apple-system, sans-serif; color: #fff; background: #0a0612; }",

      /* cyberpunk background */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg { position: absolute; inset: 0; background: linear-gradient(180deg, #0c0024 0%, #120835 25%, #1a0a2e 50%, #0d0620 75%, #060212 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at 20% 20%, rgba(255,0,180,0.15) 0%, transparent 50%), radial-gradient(ellipse at 80% 30%, rgba(0,255,255,0.12) 0%, transparent 45%), radial-gradient(ellipse at 50% 80%, rgba(255,0,100,0.1) 0%, transparent 50%), radial-gradient(ellipse at 70% 60%, rgba(120,0,255,0.08) 0%, transparent 40%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg::after { content: ''; position: absolute; inset: 0; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,0,180,0.03) 2px, rgba(255,0,180,0.03) 4px); pointer-events: none; }",

      /* neon city silhouette */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city { position: absolute; bottom: 0; left: 0; right: 0; height: 55%; background: linear-gradient(180deg, transparent 0%, rgba(10,2,20,0.6) 40%, rgba(10,2,20,0.95) 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city::before { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 100%; background: repeating-linear-gradient(90deg, transparent 0px, transparent 40px, rgba(255,0,180,0.04) 40px, rgba(255,0,180,0.04) 42px, transparent 42px, transparent 120px, rgba(0,255,255,0.03) 120px, rgba(0,255,255,0.03) 121px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city-blocks { position: absolute; bottom: 8%; left: 0; right: 0; height: 40%; display: flex; align-items: flex-end; justify-content: center; gap: 3px; padding: 0 5%; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-building { flex: 0 0 auto; background: linear-gradient(180deg, rgba(20,5,40,0.95), rgba(10,2,20,0.98)); border-radius: 2px 2px 0 0; position: relative; box-shadow: 0 0 8px rgba(255,0,180,0.15), inset 0 0 20px rgba(0,0,0,0.5); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-building::after { content: ''; position: absolute; inset: 4px; background: repeating-linear-gradient(0deg, transparent 0px, transparent 6px, rgba(255,200,50,0.08) 6px, rgba(255,200,50,0.08) 8px); mask-image: repeating-linear-gradient(90deg, transparent 0px, transparent 3px, black 3px, black 5px, transparent 5px, transparent 8px); -webkit-mask-image: repeating-linear-gradient(90deg, transparent 0px, transparent 3px, black 3px, black 5px, transparent 5px, transparent 8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-neon-line { position: absolute; height: 2px; border-radius: 1px; filter: blur(1px); }",

      /* wet floor reflection */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-floor { position: absolute; bottom: 0; left: 0; right: 0; height: 8%; background: linear-gradient(180deg, rgba(10,2,20,0.3) 0%, rgba(5,1,15,0.8) 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-floor::before { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,0,180,0.06), rgba(0,255,255,0.04), transparent); }",

      /* top bar */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar { position: absolute; top: 0; left: 0; right: 0; height: 32px; background: rgba(0,0,0,0.75); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; font-size: 13px; z-index: 10; border-bottom: 1px solid rgba(255,255,255,0.06); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-left { font-weight: 600; cursor: default; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-center { position: absolute; left: 50%; transform: translateX(-50%); font-weight: 500; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-right { display: flex; gap: 8px; align-items: center; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-right svg { width: 16px; height: 16px; fill: #fff; opacity: 0.8; }",

      /* left dock */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 12px; z-index: 10; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon { width: 44px; height: 44px; border-radius: 50%; border: none; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease; box-shadow: 0 2px 8px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon:hover { transform: scale(1.15); box-shadow: 0 4px 16px rgba(0,0,0,0.4); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon svg { width: 22px; height: 22px; fill: currentColor; }",

      /* main window */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-window { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -52%); width: min(700px, 80vw); background: rgba(255,255,255,0.95); border-radius: 12px; box-shadow: 0 25px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.1); z-index: 10; color: #222; overflow: hidden; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-titlebar { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: linear-gradient(180deg, #e8e8e8, #d4d4d4); border-bottom: 1px solid #bbb; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dots { display: flex; gap: 7px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot { width: 12px; height: 12px; border-radius: 50%; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.close { background: #ff5f57; border: 1px solid #e0443e; cursor: pointer; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.minimize { background: #ffbd2e; border: 1px solid #dea123; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.maximize { background: #28c940; border: 1px solid #1aab29; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-title { font-size: 13px; font-weight: 600; color: #333; }",

      /* window body */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-body { display: grid; grid-template-columns: 200px 1fr; min-height: 280px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-sidebar { padding: 20px 16px; background: #f5f5f5; border-right: 1px solid #e0e0e0; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-sidebar h3 { margin: 0 0 14px; font-size: 16px; font-weight: 700; color: #111; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-app-item { display: block; width: 100%; text-align: left; padding: 8px 12px; border: none; background: none; border-radius: 6px; font-size: 14px; color: #333; cursor: pointer; margin-bottom: 2px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-app-item:hover { background: rgba(0,0,0,0.06); }",

      /* window content */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-content { padding: 24px; display: flex; flex-direction: column; align-items: flex-start; gap: 12px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-welcome-title { margin: 0; font-size: 20px; font-weight: 700; color: #111; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-welcome-sub { margin: 0; font-size: 13px; color: #888; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-preview { width: 100%; max-width: 360px; aspect-ratio: 16/9; border-radius: 10px; overflow: hidden; background: linear-gradient(135deg, #0c0024, #1a0a2e, #120835); box-shadow: 0 8px 24px rgba(0,0,0,0.2); position: relative; margin: 6px 0; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-preview::after { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at 30% 40%, rgba(255,0,180,0.2), transparent 60%), radial-gradient(ellipse at 70% 30%, rgba(0,255,255,0.15), transparent 50%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-label { position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%); font-family: 'Impact', 'Arial Black', sans-serif; font-size: 22px; color: #fff; text-shadow: 0 0 10px rgba(255,0,180,0.6), 0 2px 4px rgba(0,0,0,0.5); letter-spacing: 2px; z-index: 1; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-btn-wallpaper { display: inline-block; padding: 10px 28px; border: none; border-radius: 999px; background: #00e5ff; color: #003; font-weight: 700; font-size: 14px; cursor: pointer; box-shadow: 0 4px 14px rgba(0,229,255,0.3); transition: transform 0.15s ease; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-btn-wallpaper:hover { transform: translateY(-1px); }",

      /* bottom branding */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-branding { position: absolute; bottom: 6%; left: 50%; transform: translateX(-50%); text-align: center; z-index: 5; pointer-events: none; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-title { font-family: 'Impact', 'Arial Black', sans-serif; font-size: clamp(48px, 8vw, 100px); line-height: 1; color: #fff; text-shadow: 0 0 20px rgba(255,0,180,0.4), 0 4px 8px rgba(0,0,0,0.4); letter-spacing: 4px; margin: 0; white-space: nowrap; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-title span { color: #ff1493; text-shadow: 0 0 30px rgba(255,20,147,0.6), 0 0 60px rgba(255,20,147,0.3); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-tagline { font-family: 'Courier New', monospace; font-size: clamp(11px, 1.5vw, 16px); color: #00e5ff; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 8px; text-shadow: 0 0 12px rgba(0,229,255,0.5); }",

      /* badge */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-badge { position: absolute; bottom: 16px; right: 20px; display: flex; align-items: center; gap: 8px; z-index: 10; font-size: 12px; color: rgba(255,255,255,0.6); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-badge-logo { width: 40px; height: 40px; border-radius: 8px; background: rgba(255,255,255,0.1); }",

      /* close overlay button */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-close-overlay { position: absolute; top: 40px; right: 16px; z-index: 20; border: none; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; width: 32px; height: 32px; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-close-overlay:hover { background: rgba(0,0,0,0.7); }",

      /* details link */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-details-link { position: absolute; top: 40px; left: 80px; z-index: 20; border: none; background: rgba(0,0,0,0.5); color: #00e5ff; border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer; backdrop-filter: blur(8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-details-link:hover { background: rgba(0,0,0,0.7); }"
    ].join("\n");
    document.head.appendChild(style);
  }

  function removeOverlay() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing) {
      existing.remove();
    }
  }

  function copyText(text, successMessage) {
    return profileModal.copyText(showError, showToast, text, successMessage);
  }

  function getApiToken(interactive) {
    return apiClient.getApiToken(interactive);
  }

  function ensureApiToken() {
    var token = getApiToken(true);
    if (token) {
      return token;
    }
    showError("Beagle API Token ist fuer diese Browser-Sitzung nicht gesetzt.");
    return "";
  }

  function downloadProtectedFile(path, filename) {
    return apiClient.downloadProtectedFile(path, filename);
  }

  function apiGetInstallerPrep(vmid) {
    return platformService.fetchInstallerPreparation(vmid);
  }

  function apiStartInstallerPrep(vmid) {
    return platformService.prepareInstallerTarget(vmid);
  }

  function apiCreateSunshineAccess(vmid) {
    return platformService.createSunshineAccess(vmid);
  }

  function installerPrepBannerClass(state) {
    return usbUi.installerPrepBannerClass(state);
  }

  function formatInstallerPrepValue(value, fallback) {
    return usbUi.formatInstallerPrepValue(value, fallback);
  }

  function installerTargetState(profile, state) {
    return usbUi.installerTargetState(profile, state);
  }

  function shouldReuseInstallerPrepState(state) {
    return usbUi.shouldReuseInstallerPrepState(state);
  }

  function syncInstallerButtons(overlay, state) {
    return usbUi.syncInstallerButtons(overlay, state);
  }

  function applyInstallerPrepState(overlay, state) {
    return usbUi.applyInstallerPrepState(overlay, state);
  }

  function formatActionState(ok) {
    return profileModal.formatActionState(ok);
  }

  function renderProvisioningBadge(state) {
    return provisioningResultModal.renderProvisioningBadge(state);
  }

  function renderFleetModal(payload) {
    return fleetModal.renderFleetModal({
      overlayId: OVERLAY_ID,
      payload: payload,
      removeOverlay: removeOverlay,
      showFleetModal: showFleetModal,
      showUbuntuBeagleCreateModal: showUbuntuBeagleCreateModal,
      selectedNodeName: selectedNodeName,
      resolveControlPlaneHealthUrl: resolveControlPlaneHealthUrl,
      openUrl: openUrl,
      copyText: copyText,
      platformService: platformService,
      apiGetProvisioningState: apiGetProvisioningState,
      showProfileModal: showProfileModal,
      showError: showError,
      showToast: showToast,
      buildProvisioningCredentialText: buildProvisioningCredentialText,
      renderProvisioningBadge: renderProvisioningBadge,
      formatActionState: formatActionState,
      downloadProtectedFile: downloadProtectedFile
    });
  }

  function showFleetModal() {
    ensureStyles();
    removeOverlay();
    if (!ensureApiToken()) {
      return;
    }
    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = '<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Fleet wird geladen</h2><p class="beagle-subtitle">Inventar, Policies und Endpoint-Zustand werden vom Manager geladen.</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Beagle Control Plane wird abgefragt.</div></div></div>';
    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);
    Promise.all([
      platformService.fetchHealth(),
      platformService.fetchInventory(),
      platformService.fetchPolicies(),
      apiGetProvisioningCatalog()
    ]).then(function(results) {
      removeOverlay();
      renderFleetModal({
        health: results[0] || {},
        vms: results[1] || [],
        policies: results[2] || [],
        catalog: results[3] || {}
      });
    }).catch(function(error) {
      removeOverlay();
      showError('Beagle Fleet konnte nicht geladen werden: ' + error.message);
    });
  }

  function resolveVmProfile(ctx) {
    return vmProfileState.resolveVmProfile(ctx);
  }

  function kvRow(label, value) {
    return renderHelpers.kvRow(label, value);
  }

  function escapeHtml(text) {
    return renderHelpers.escapeHtml(text);
  }

  function renderDesktopOverlay(profile) {
    return desktopOverlay.renderDesktopOverlay({
      overlayId: OVERLAY_ID,
      profile: profile,
      removeOverlay: removeOverlay,
      showProfileModal: renderProfileModal
    });
  }

  function renderProfileModal(profile, options) {
    return profileModal.renderProfileModal({
      overlayId: OVERLAY_ID,
      profile: profile,
      options: options,
      removeOverlay: removeOverlay,
      withNoCache: withNoCache,
      webUiUrlWithToken: webUiUrlWithToken,
      openUrl: openUrl,
      showError: showError,
      showToast: showToast,
      showProfileModal: showProfileModal,
      showUbuntuBeagleCreateModal: showUbuntuBeagleCreateModal,
      apiCreateSunshineAccess: apiCreateSunshineAccess,
      platformService: platformService,
      apiGetInstallerPrep: apiGetInstallerPrep,
      apiStartInstallerPrep: apiStartInstallerPrep,
      downloadProtectedFile: downloadProtectedFile,
      normalizeBeagleApiPath: normalizeBeagleApiPath,
      triggerDownload: triggerDownload,
      sleep: sleep,
      syncInstallerButtons: syncInstallerButtons,
      applyInstallerPrepState: applyInstallerPrepState,
      installerTargetState: installerTargetState,
      shouldReuseInstallerPrepState: shouldReuseInstallerPrepState
    });
  }

  function showProfileModal(ctx, options) {
    ensureStyles();
    removeOverlay();

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = '<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Profil wird geladen</h2><p class="beagle-subtitle">VM ' + String(ctx.vmid) + ' auf Node ' + escapeHtml(ctx.node || '') + '</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Proxmox-Konfiguration, Guest-Agent-Daten und Beagle-Metadaten werden aufgeloest.</div></div></div>';
    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);

    resolveVmProfile(ctx).then(function(profile) {
      removeOverlay();
      if (options && options.showDetails) {
        renderProfileModal(profile, options);
      } else {
        renderDesktopOverlay(profile);
      }
    }).catch(function(error) {
      removeOverlay();
      showError('Beagle Profil konnte nicht geladen werden: ' + error.message);
    });
  }

  function ensureConsoleButtonIntegration(button) {
    if (!button || !button.vmid || button.consoleType !== "kvm" || button.__beagleIntegrated) {
      return;
    }

    var menu = button.getMenu ? button.getMenu() : button.menu;
    if (menu && !menu.down("#beagleOsProfileMenuItem")) {
      menu.add({
        itemId: "beagleOsProfileMenuItem",
        text: PRODUCT_LABEL + " Profil",
        iconCls: "fa fa-desktop",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid });
        }
      });
    }

    if (menu) {
      getVmInstallerEligibility({ node: button.nodename, vmid: button.vmid }).then(function(result) {
        var existingInstallerItem = menu.down("#beagleOsInstallerMenuItem");
        if (result && result.eligible) {
          if (!existingInstallerItem) {
            menu.add({
              itemId: "beagleOsInstallerMenuItem",
              text: PRODUCT_LABEL + " Installer",
              iconCls: "fa fa-usb",
              handler: function() {
                openUsbInstaller({ node: button.nodename, vmid: button.vmid });
              }
            });
          }
          return;
        }
        if (existingInstallerItem) {
          menu.remove(existingInstallerItem);
        }
      });
    }

    var toolbar = button.up && button.up("toolbar");
    if (toolbar && !toolbar.down("#beagleOsButton")) {
      var index = toolbar.items.indexOf(button);
      toolbar.insert(index + 1, {
        xtype: "button",
        itemId: "beagleOsButton",
        text: PRODUCT_LABEL,
        iconCls: "fa fa-desktop",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid });
        },
        tooltip: "Zeigt das aufgeloeste Beagle-Profil fuer diese VM und bietet Download-, Export- und Health-Aktionen."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsDetailsButton")) {
      var detailsIndex = toolbar.items.indexOf(button);
      toolbar.insert(detailsIndex + 2, {
        xtype: "button",
        itemId: "beagleOsDetailsButton",
        text: PRODUCT_LABEL + " Details",
        iconCls: "fa fa-info-circle",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid }, { showDetails: true });
        },
        tooltip: "Zeigt das technische Beagle-Profil mit allen Details fuer diese VM."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsWebUIButton")) {
      var webIndex = toolbar.items.indexOf(button);
      toolbar.insert(webIndex + 3, {
        xtype: "button",
        itemId: "beagleOsWebUIButton",
        text: "Beagle Web UI",
        iconCls: "fa fa-globe",
        handler: function() {
          openUrl(webUiUrlWithToken(true));
        },
        tooltip: "Oeffnet die zentrale Beagle Web UI auf diesem Host."
      });
    }

    button.__beagleIntegrated = true;
  }

  function ensureFleetLauncher() {
    ensureStyles();
    if (document.getElementById(FLEET_LAUNCHER_ID)) {
      return;
    }
    var button = document.createElement('button');
    button.id = FLEET_LAUNCHER_ID;
    button.type = 'button';
    button.textContent = 'Beagle Fleet';
    button.addEventListener('click', function() {
      showFleetModal();
    });
    document.body.appendChild(button);
  }

  function findCreateVmToolbarAnchor() {
    var labels = createVmLabels();
    var textNodes = Array.prototype.slice.call(document.querySelectorAll(".x-toolbar .x-btn-inner"));
    for (var index = 0; index < textNodes.length; index += 1) {
      var textNode = textNodes[index];
      var normalized = normalizeUiText(textNode.textContent || textNode.innerText || "");
      if (labels.indexOf(normalized) === -1) {
        continue;
      }
      var button = textNode.closest(".x-btn");
      if (button && button.id !== CREATE_VM_DOM_BUTTON_ID) {
        return button;
      }
    }
    return null;
  }

  function toolbarHasBeagleCreateVmButton(toolbar) {
    if (!toolbar) {
      return false;
    }
    var textNodes = Array.prototype.slice.call(toolbar.querySelectorAll(".x-btn-inner"));
    return textNodes.some(function(node) {
      return normalizeUiText(node.textContent || node.innerText || "") === normalizeUiText("Erstelle Beagle OS VM");
    });
  }

  function ensureCreateVmDomFallback() {
    var anchor = findCreateVmToolbarAnchor();
    var existing = document.getElementById(CREATE_VM_DOM_BUTTON_ID);
    if (!anchor) {
      if (existing) {
        existing.remove();
      }
      return;
    }

    var toolbar = anchor.parentElement;
    if (!toolbar) {
      return;
    }

    if (toolbarHasBeagleCreateVmButton(toolbar) && (!existing || existing.parentElement === toolbar)) {
      if (existing && existing.parentElement !== toolbar) {
        existing.remove();
      }
      return;
    }

    if (!existing) {
      existing = anchor.cloneNode(true);
      existing.id = CREATE_VM_DOM_BUTTON_ID;
      existing.setAttribute("data-beagle-create-vm-dom", "1");
      existing.removeAttribute("aria-describedby");
      existing.removeAttribute("data-componentid");
      existing.style.width = "auto";
      var inner = existing.querySelector(".x-btn-inner");
      if (inner) {
        inner.textContent = "Erstelle Beagle OS VM";
      } else {
        existing.textContent = "Erstelle Beagle OS VM";
      }
      existing.title = "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine.";
      existing.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
        showUbuntuBeagleCreateModal({ node: selectedNodeName() || "" });
      });
    }

    if (existing.parentElement !== toolbar || existing.nextSibling !== anchor) {
      toolbar.insertBefore(existing, anchor);
    }
  }

  function ensureCreateVmIntegration(component) {
    if (!component || component.__beagleUbuntuCreateIntegrated) {
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("menu")) {
      var menu = component.up("menu");
      if (!menu.down("#beagleUbuntuCreateVmMenuItem")) {
        menu.insert(menu.items.indexOf(component), {
          itemId: "beagleUbuntuCreateVmMenuItem",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            showUbuntuBeagleCreateModal({ node: menu.nodename || selectedNodeName() || "" });
          }
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("toolbar")) {
      var toolbar = component.up && component.up("toolbar");
      if (toolbar && !toolbar.down("#beagleUbuntuCreateVmButton")) {
        toolbar.insert(toolbar.items.indexOf(component), {
          xtype: "button",
          itemId: "beagleUbuntuCreateVmButton",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            showUbuntuBeagleCreateModal({ node: selectedNodeName() || "" });
          },
          tooltip: "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine."
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
    }
  }

  function integrate() {
    if (!(window.Ext && Ext.ComponentQuery)) {
      return;
    }

    Ext.ComponentQuery.query("pveConsoleButton").forEach(ensureConsoleButtonIntegration);
    Ext.ComponentQuery.query("#createvm").forEach(ensureCreateVmIntegration);
    Ext.ComponentQuery.query("button").forEach(ensureCreateVmIntegration);
    Ext.ComponentQuery.query("menuitem").forEach(ensureCreateVmIntegration);
    ensureFleetLauncher();
    ensureCreateVmDomFallback();
  }

  function boot() {
    ensureStyles();
    integrate();
    window.setInterval(integrate, 1000);
  }

  if (window.Ext && Ext.onReady) {
    Ext.onReady(boot);
  } else {
    boot();
  }
})();

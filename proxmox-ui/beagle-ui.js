(function() {
  "use strict";

  var PRODUCT_LABEL = "Beagle OS";
  var OVERLAY_ID = "beagle-os-overlay";
  var CREATE_VM_DOM_BUTTON_ID = "beagle-os-create-vm-dom-button";
  var common = window.BeagleUiCommon;
  var virtualizationService = window.BeagleVirtualizationService;
  var platformService = window.BeaglePlatformService;
  var apiClient = window.BeagleUiApiClient;
  var beagleState = window.BeagleUiState;
  var fleetState = window.BeagleUiFleetState;
  var vmProfileState = window.BeagleUiVmProfileState;
  var provisioningFlow = window.BeagleUiProvisioningFlow;
  var usbUi = window.BeagleUiUsbUi;
  var renderHelpers = window.BeagleUiRenderHelpers;
  var modalShell = window.BeagleUiModalShell;
  var desktopOverlay = window.BeagleUiDesktopOverlay;
  var profileModal = window.BeagleUiProfileModal;
  var fleetModal = window.BeagleUiFleetModal;
  var provisioningResultModal = window.BeagleUiProvisioningResultModal;
  var extJsIntegration = window.BeagleUiExtJsIntegration;
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
  if (!fleetState) {
    throw new Error("BeagleUiFleetState must be loaded before beagle-ui.js");
  }
  if (!vmProfileState) {
    throw new Error("BeagleUiVmProfileState must be loaded before beagle-ui.js");
  }
  if (!provisioningFlow) {
    throw new Error("BeagleUiProvisioningFlow must be loaded before beagle-ui.js");
  }
  if (!usbUi) {
    throw new Error("BeagleUiUsbUi must be loaded before beagle-ui.js");
  }
  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before beagle-ui.js");
  }
  if (!modalShell) {
    throw new Error("BeagleUiModalShell must be loaded before beagle-ui.js");
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
  if (!extJsIntegration) {
    throw new Error("BeagleUiExtJsIntegration must be loaded before beagle-ui.js");
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

  function getVmInstallerEligibility(ctx) {
    return beagleState.getVmInstallerEligibility(ctx);
  }

  function openUsbInstaller(ctx) {
    showProfileModal(ctx || {}, { autoPrepareDownload: true });
  }

  function selectedNodeName() {
    return virtualizationService.selectedNodeName();
  }

  function buildProvisioningCredentialText(created, state) {
    return provisioningFlow.buildProvisioningCredentialText(created, state);
  }

  function showProvisioningResultWindow(created) {
    return provisioningFlow.showProvisioningResultWindow({
      created: created,
      copyText: copyText,
      showProfileModal: showProfileModal
    });
  }

  function showUbuntuBeagleCreateModal(ctx) {
    return provisioningFlow.showUbuntuBeagleCreateModal({
      ctx: ctx,
      showError: showError,
      showToast: showToast,
      ensureApiToken: ensureApiToken,
      showProfileModal: showProfileModal,
      copyText: copyText
    });
  }

  function ensureStyles() {
    return modalShell.ensureStyles();
  }

  function removeOverlay() {
    return modalShell.removeOverlay();
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
      apiGetProvisioningState: provisioningFlow.fetchProvisioningState,
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
    if (!ensureApiToken()) {
      return;
    }
    modalShell.showLoadingOverlay({
      title: "Beagle Fleet wird geladen",
      subtitle: "Inventar, Policies und Endpoint-Zustand werden vom Manager geladen.",
      message: "Beagle Control Plane wird abgefragt."
    });
    fleetState.loadFleetPayload().then(function(payload) {
      removeOverlay();
      renderFleetModal(payload);
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
      apiCreateSunshineAccess: platformService.createSunshineAccess,
      platformService: platformService,
      apiGetInstallerPrep: platformService.fetchInstallerPreparation,
      apiStartInstallerPrep: platformService.prepareInstallerTarget,
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
    modalShell.showLoadingOverlay({
      title: "Beagle Profil wird geladen",
      subtitle: "VM " + String(ctx.vmid) + " auf Node " + escapeHtml(ctx.node || ""),
      message: "Proxmox-Konfiguration, Guest-Agent-Daten und Beagle-Metadaten werden aufgeloest."
    });

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

  function boot() {
    extJsIntegration.boot({
      createVmDomButtonId: CREATE_VM_DOM_BUTTON_ID,
      ensureStyles: ensureStyles,
      fleetLauncherId: modalShell.fleetLauncherId,
      getVmInstallerEligibility: getVmInstallerEligibility,
      openUrl: openUrl,
      openUsbInstaller: openUsbInstaller,
      productLabel: PRODUCT_LABEL,
      selectedNodeName: selectedNodeName,
      showFleetModal: showFleetModal,
      showProfileModal: showProfileModal,
      showUbuntuBeagleCreateModal: showUbuntuBeagleCreateModal,
      webUiUrlWithToken: webUiUrlWithToken
    });
  }

  if (window.Ext && Ext.onReady) {
    Ext.onReady(boot);
  } else {
    boot();
  }
})();

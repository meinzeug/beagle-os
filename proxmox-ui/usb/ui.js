(function() {
  "use strict";

  function installerPrepBannerClass(state) {
    return String(state && state.status || "").toLowerCase() === "error" ? "warn" : "info";
  }

  function formatInstallerPrepValue(value, fallback) {
    var text = String(value == null ? "" : value);
    return text || String(fallback || "");
  }

  function installerTargetState(profile, state) {
    if (profile && profile.installerTargetEligible === false) {
      return {
        label: "Ziel ungeeignet",
        bannerClass: "warn",
        message: profile.installerTargetMessage || "Diese VM wird nicht als Streaming-Ziel angeboten.",
        ready: false,
        unsupported: true
      };
    }
    if (String(state && state.status || "").toLowerCase() === "ready") {
      return {
        label: "USB Installer bereit",
        bannerClass: "info",
        message: state && state.message || "Der USB-Installer kann direkt heruntergeladen werden.",
        ready: true,
        unsupported: false
      };
    }
    return {
      label: "Sunshine wird vorbereitet",
      bannerClass: "info",
      message: state && state.message || "Die VM wird fuer den Stream vorbereitet.",
      ready: false,
      unsupported: false
    };
  }

  function shouldReuseInstallerPrepState(state) {
    var status = String(state && state.status || "").toLowerCase();
    if (!state) {
      return false;
    }
    if (state.ready) {
      return true;
    }
    return Boolean(status) && ["idle", "error", "failed"].indexOf(status) === -1;
  }

  function syncInstallerButtons(overlay, state) {
    var profile = overlay && overlay.__beagleProfile || {};
    var resolved = installerTargetState(profile, state);
    var statusNodes = overlay.querySelectorAll("[data-beagle-download-state]");
    var messageNodes = overlay.querySelectorAll("[data-beagle-download-message]");
    var stateBanners = overlay.querySelectorAll("[data-beagle-download-banner]");
    var usbButton = overlay.querySelector('[data-beagle-action="download"]');
    var isoButton = overlay.querySelector('[data-beagle-action="download-iso"]');
    statusNodes.forEach(function(statusNode) { statusNode.textContent = resolved.label; });
    messageNodes.forEach(function(messageNode) { messageNode.textContent = resolved.message; });
    stateBanners.forEach(function(stateBanner) { stateBanner.className = "beagle-banner " + resolved.bannerClass; });
    if (usbButton) {
      usbButton.disabled = resolved.unsupported;
      usbButton.hidden = resolved.unsupported;
    }
    if (isoButton) {
      isoButton.disabled = false;
    }
  }

  function applyInstallerPrepState(overlay, state) {
    var payload = state || {};
    var resolved = installerTargetState(overlay && overlay.__beagleProfile || {}, payload);
    var statusNode = overlay.querySelector("[data-beagle-installer-status]");
    var phaseNode = overlay.querySelector("[data-beagle-installer-phase]");
    var progressNode = overlay.querySelector("[data-beagle-installer-progress]");
    var messageNode = overlay.querySelector("[data-beagle-installer-message]");
    var binaryNode = overlay.querySelector("[data-beagle-installer-binary]");
    var serviceNode = overlay.querySelector("[data-beagle-installer-service]");
    var processNode = overlay.querySelector("[data-beagle-installer-process]");
    if (statusNode) {
      statusNode.textContent = formatInstallerPrepValue(payload.status, "idle");
    }
    if (phaseNode) {
      phaseNode.textContent = formatInstallerPrepValue(payload.phase, "inspect");
    }
    if (progressNode) {
      progressNode.textContent = formatInstallerPrepValue(payload.progress, "0") + "%";
    }
    if (messageNode) {
      messageNode.textContent = formatInstallerPrepValue(payload.message, "");
    }
    if (binaryNode) {
      binaryNode.textContent = payload.sunshine_status && payload.sunshine_status.binary ? "ok" : "missing";
    }
    if (serviceNode) {
      serviceNode.textContent = payload.sunshine_status && payload.sunshine_status.service ? "active" : "inactive";
    }
    if (processNode) {
      processNode.textContent = payload.sunshine_status && payload.sunshine_status.process ? "running" : "stopped";
    }
    syncInstallerButtons(overlay, payload);
  }

  window.BeagleUiUsbUi = {
    installerPrepBannerClass: installerPrepBannerClass,
    formatInstallerPrepValue: formatInstallerPrepValue,
    installerTargetState: installerTargetState,
    shouldReuseInstallerPrepState: shouldReuseInstallerPrepState,
    syncInstallerButtons: syncInstallerButtons,
    applyInstallerPrepState: applyInstallerPrepState
  };
})();

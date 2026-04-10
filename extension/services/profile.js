(function() {
  "use strict";

  var common = window.BeagleExtensionCommon;
  var virtualizationService = window.BeagleExtensionVirtualizationService;
  var platformService = window.BeagleExtensionPlatformService;
  var profileMapper = window.BeagleBrowserVmProfileMapper;
  var profileHelpers = window.BeagleBrowserVmProfileHelpers;

  if (!common) {
    throw new Error("BeagleExtensionCommon must be loaded before BeagleExtensionProfileService");
  }
  if (!virtualizationService) {
    throw new Error("BeagleExtensionVirtualizationService must be loaded before BeagleExtensionProfileService");
  }
  if (!platformService) {
    throw new Error("BeagleExtensionPlatformService must be loaded before BeagleExtensionProfileService");
  }
  if (!profileMapper) {
    throw new Error("BeagleBrowserVmProfileMapper must be loaded before BeagleExtensionProfileService");
  }
  if (!profileHelpers) {
    throw new Error("BeagleBrowserVmProfileHelpers must be loaded before BeagleExtensionProfileService");
  }

  function installerTargetState(profile, state) {
    if (profile && profile.installerTargetEligible === false) {
      return {
        label: "Ziel ungeeignet",
        message: profile.installerTargetMessage || "Diese VM wird nicht als Streaming-Ziel angeboten.",
        unsupported: true
      };
    }
    if (String(state && state.status || "").toLowerCase() === "ready") {
      return {
        label: "USB Installer bereit",
        message: state && state.message || "Das VM-spezifische USB-Installer-Skript kann direkt geladen werden.",
        unsupported: false
      };
    }
    return {
      label: "Sunshine wird vorbereitet",
      message: state && state.message || "Die VM wird fuer Sunshine und den Internet-Stream vorbereitet.",
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

  async function resolveVmProfile(ctx) {
    var results = await Promise.all([
      virtualizationService.getVmConfig(ctx),
      virtualizationService.listVms().catch(function() { return []; }),
      virtualizationService.getVmGuestInterfaces(ctx).catch(function() { return []; }),
      platformService.resolveUsbInstallerUrl(ctx),
      platformService.resolveInstallerIsoUrl(ctx),
      platformService.resolveControlPlaneHealthUrl(),
      platformService.fetchPublicVmState(ctx.vmid),
      platformService.fetchInstallerPreparation(ctx.vmid).catch(function() { return null; })
    ]);
    var config = results[0] || {};
    var resources = Array.isArray(results[1]) ? results[1] : [];
    var guestInterfaces = Array.isArray(results[2]) ? results[2] : [];
    var installerUrl = results[3] || "";
    var installerIsoUrl = results[4] || "";
    var controlPlaneHealthUrl = results[5] || "";
    var endpointPayload = results[6] || null;
    var installerPrep = results[7] || null;
    var profile = profileMapper.buildExtensionProfile({
      ctx: ctx,
      config: config,
      resources: resources,
      guestInterfaces: guestInterfaces,
      endpointPayload: endpointPayload,
      installerPrepOverride: installerPrep,
      host: window.location.hostname,
      installerUrl: installerUrl,
      installerWindowsUrl: "/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/installer.ps1",
      installerIsoUrl: installerIsoUrl,
      controlPlaneHealthUrl: controlPlaneHealthUrl,
      managerUrl: common.managerUrlFromHealthUrl(controlPlaneHealthUrl)
    });
    profile.notes = profileHelpers.buildNotes(profile, { includeNoEndpointSummaryNote: true });
    profile.endpointEnv = profileHelpers.buildEndpointEnv(profile);
    return profile;
  }

  window.BeagleExtensionProfileService = {
    buildEndpointEnv: profileHelpers.buildEndpointEnv,
    buildNotes: profileHelpers.buildNotes,
    formatActionState: profileHelpers.formatActionState,
    installerTargetState: installerTargetState,
    resolveVmProfile: resolveVmProfile,
    shouldReuseInstallerPrepState: shouldReuseInstallerPrepState
  };
})();

(function() {
  "use strict";

  var common = window.BeagleUiCommon;
  var virtualizationService = window.BeagleVirtualizationService;
  var platformService = window.BeaglePlatformService;
  var profileModal = window.BeagleUiProfileModal;
  var profileMapper = window.BeagleBrowserVmProfileMapper;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before BeagleUiVmProfileState");
  }
  if (!virtualizationService) {
    throw new Error("BeagleVirtualizationService must be loaded before BeagleUiVmProfileState");
  }
  if (!platformService) {
    throw new Error("BeaglePlatformService must be loaded before BeagleUiVmProfileState");
  }
  if (!profileModal) {
    throw new Error("BeagleUiProfileModal must be loaded before BeagleUiVmProfileState");
  }
  if (!profileMapper) {
    throw new Error("BeagleBrowserVmProfileMapper must be loaded before BeagleUiVmProfileState");
  }

  function resolveVmProfile(ctx) {
    return Promise.all([
      virtualizationService.getVmConfig(ctx),
      virtualizationService.listVms().catch(function() { return []; }),
      virtualizationService.getVmGuestInterfaces(ctx).catch(function() { return []; }),
      platformService.fetchVmCredentials(ctx.vmid).catch(function() { return null; }),
      platformService.fetchPublicVmState(ctx.vmid),
      platformService.fetchVmUsbState(ctx.vmid).catch(function() { return null; })
    ]).then(function(results) {
      var config = results[0] || {};
      var resources = Array.isArray(results[1]) ? results[1] : [];
      var guestInterfaces = Array.isArray(results[2]) ? results[2] : [];
      var credentials = results[3] || null;
      var endpointPayload = results[4] || null;
      var usbPayload = results[5] || null;
      var controlPlaneHealthUrl = common.resolveControlPlaneHealthUrl();
      var profile = profileMapper.buildUiProfile({
        ctx: ctx,
        config: config,
        resources: resources,
        guestInterfaces: guestInterfaces,
        credentials: credentials,
        endpointPayload: endpointPayload,
        usbPayload: usbPayload,
        host: window.location.hostname,
        installerUrl: common.resolveUsbInstallerUrl(ctx),
        liveUsbUrl: "/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/live-usb.sh",
        installerWindowsUrl: "/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/installer.ps1",
        installerIsoUrl: common.resolveInstallerIsoUrl(ctx),
        controlPlaneHealthUrl: controlPlaneHealthUrl,
        managerUrl: common.managerUrlFromHealthUrl(controlPlaneHealthUrl)
      });
      profile.notes = profileModal.buildNotes(profile);
      if (!profile.endpointSummary) {
        profile.notes.push("Endpoint hat noch keinen Check-in an die Beagle Control Plane geliefert.");
      }
      profile.endpointEnv = profileModal.buildEndpointEnv(profile);
      return profile;
    });
  }

  window.BeagleUiVmProfileState = {
    resolveVmProfile: resolveVmProfile
  };
})();

(function() {
  "use strict";

  var platformService = window.BeaglePlatformService;

  if (!platformService) {
    throw new Error("BeaglePlatformService must be loaded before BeagleUiState");
  }

  var installerEligibilityCache = {};

  function getInstallerEligibilityKey(ctx) {
    return String(ctx && ctx.node || "") + ":" + String(ctx && ctx.vmid || "");
  }

  function getVmInstallerEligibility(ctx) {
    var key = getInstallerEligibilityKey(ctx);
    if (installerEligibilityCache[key]) {
      return installerEligibilityCache[key];
    }
    installerEligibilityCache[key] = platformService.fetchInstallerTargetEligibility(ctx).catch(function() {
      return { eligible: false, message: "" };
    });
    return installerEligibilityCache[key];
  }

  window.BeagleUiState = {
    getInstallerEligibilityKey: getInstallerEligibilityKey,
    getVmInstallerEligibility: getVmInstallerEligibility
  };
})();

(function() {
  "use strict";

  var apiClient = window.BeagleUiApiClient;

  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before BeagleUiUsbApi");
  }

  function unwrapInstallerPrep(payload) {
    return payload && payload.installer_prep ? payload.installer_prep : payload;
  }

  function apiGetInstallerPrep(vmid) {
    return apiClient.apiGetBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/installer-prep").then(unwrapInstallerPrep);
  }

  function apiStartInstallerPrep(vmid) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/installer-prep", {}).then(unwrapInstallerPrep);
  }

  function apiGetVmCredentials(vmid) {
    return apiClient.apiGetBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/credentials").then(function(payload) {
      return payload && payload.credentials ? payload.credentials : payload;
    });
  }

  function apiCreateSunshineAccess(vmid) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/sunshine-access", {}).then(function(payload) {
      return payload && payload.sunshine_access ? payload.sunshine_access : payload;
    });
  }

  window.BeagleUiUsbApi = {
    apiGetInstallerPrep: apiGetInstallerPrep,
    apiStartInstallerPrep: apiStartInstallerPrep,
    apiGetVmCredentials: apiGetVmCredentials,
    apiCreateSunshineAccess: apiCreateSunshineAccess
  };
})();

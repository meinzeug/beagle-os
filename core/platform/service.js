(function() {
  "use strict";

  var common = window.BeagleUiCommon;
  var apiClient = window.BeagleUiApiClient;
  var provisioningApi = window.BeagleUiProvisioningApi;
  var usbApi = window.BeagleUiUsbApi;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before BeaglePlatformService");
  }
  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before BeaglePlatformService");
  }
  if (!provisioningApi) {
    throw new Error("BeagleUiProvisioningApi must be loaded before BeaglePlatformService");
  }
  if (!usbApi) {
    throw new Error("BeagleUiUsbApi must be loaded before BeaglePlatformService");
  }

  function fetchHealth() {
    return apiClient.apiGetBeagleJson("/api/v1/health");
  }

  function fetchInventory() {
    return apiClient.apiGetBeagleJson("/api/v1/vms").then(function(payload) {
      return payload && payload.vms ? payload.vms : [];
    });
  }

  function fetchPolicies() {
    return apiClient.apiGetBeagleJson("/api/v1/policies").then(function(payload) {
      return payload && payload.policies ? payload.policies : [];
    });
  }

  function fetchProvisioningCatalog() {
    return provisioningApi.apiGetProvisioningCatalog();
  }

  function createVm(payload) {
    return provisioningApi.apiCreateProvisionedVm(payload);
  }

  function updateVm(vmid, payload) {
    return provisioningApi.apiUpdateProvisionedVm(vmid, payload);
  }

  function fetchVmProvisioningState(vmid) {
    return provisioningApi.apiGetProvisioningState(vmid);
  }

  function fetchPublicVmState(vmid) {
    return fetch(common.resolveBeagleApiUrl("/api/v1/public/vms/" + encodeURIComponent(String(vmid)) + "/state"), {
      credentials: "same-origin"
    }).then(function(response) {
      if (!response.ok) {
        return null;
      }
      return response.json();
    }).catch(function() {
      return null;
    });
  }

  function fetchInstallerTargetEligibility(ctx) {
    return fetchPublicVmState(ctx && ctx.vmid).then(function(payload) {
      var profile = payload && payload.profile ? payload.profile : {};
      var roleText = String(profile && profile.beagle_role || "").trim().toLowerCase();
      var fallbackEligible = Boolean(profile && profile.stream_host) && ["endpoint", "thinclient", "client"].indexOf(roleText) === -1;
      return {
        eligible: profile && typeof profile.installer_target_eligible === "boolean" ? profile.installer_target_eligible : fallbackEligible,
        message: profile && profile.installer_target_message ? profile.installer_target_message : (fallbackEligible ? "" : "Diese VM wird nicht als Streaming-Ziel angeboten.")
      };
    }).catch(function() {
      return { eligible: false, message: "" };
    });
  }

  function fetchInstallerPreparation(vmid) {
    return usbApi.apiGetInstallerPrep(vmid);
  }

  function prepareInstallerTarget(vmid) {
    return usbApi.apiStartInstallerPrep(vmid);
  }

  function fetchVmCredentials(vmid) {
    return usbApi.apiGetVmCredentials(vmid);
  }

  function createBeagle Stream ServerAccess(vmid) {
    return usbApi.apiCreateBeagle Stream ServerAccess(vmid);
  }

  function fetchVmUsbState(vmid) {
    return apiClient.apiGetBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/usb");
  }

  function refreshVmUsb(vmid) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/usb/refresh", {});
  }

  function attachUsb(vmid, busid) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/usb/attach", {
      busid: String(busid || "")
    });
  }

  function detachUsb(vmid, busid, port) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/usb/detach", {
      busid: String(busid || ""),
      port: String(port || "")
    });
  }

  function queueVmAction(vmid, actionName) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/vms/" + encodeURIComponent(String(vmid)) + "/actions", {
      action: actionName
    });
  }

  function queueBulkAction(vmids, actionName) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/actions/bulk", {
      vmids: vmids || [],
      action: actionName
    });
  }

  function createPolicy(payload) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/policies", payload);
  }

  function deletePolicy(policyName) {
    return apiClient.apiDeleteBeagle("/beagle-api/api/v1/policies/" + encodeURIComponent(String(policyName || "")));
  }

  window.BeaglePlatformService = {
    fetchHealth: fetchHealth,
    fetchInventory: fetchInventory,
    fetchPolicies: fetchPolicies,
    fetchProvisioningCatalog: fetchProvisioningCatalog,
    createVm: createVm,
    updateVm: updateVm,
    fetchVmProvisioningState: fetchVmProvisioningState,
    fetchPublicVmState: fetchPublicVmState,
    fetchInstallerTargetEligibility: fetchInstallerTargetEligibility,
    fetchInstallerPreparation: fetchInstallerPreparation,
    prepareInstallerTarget: prepareInstallerTarget,
    fetchVmCredentials: fetchVmCredentials,
    createBeagle Stream ServerAccess: createBeagle Stream ServerAccess,
    fetchVmUsbState: fetchVmUsbState,
    refreshVmUsb: refreshVmUsb,
    attachUsb: attachUsb,
    detachUsb: detachUsb,
    queueVmAction: queueVmAction,
    queueBulkAction: queueBulkAction,
    createPolicy: createPolicy,
    deletePolicy: deletePolicy
  };
})();

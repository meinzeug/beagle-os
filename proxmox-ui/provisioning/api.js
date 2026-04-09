(function() {
  "use strict";

  var apiClient = window.BeagleUiApiClient;

  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before BeagleUiProvisioningApi");
  }

  function apiGetProvisioningCatalog() {
    return apiClient.apiGetBeagleJson("/beagle-api/api/v1/provisioning/catalog").then(function(payload) {
      return payload && payload.catalog ? payload.catalog : payload;
    });
  }

  function apiCreateProvisionedVm(payload) {
    return apiClient.apiPostBeagleJson("/beagle-api/api/v1/provisioning/vms", payload).then(function(response) {
      return response && response.provisioned_vm ? response.provisioned_vm : response;
    });
  }

  function apiUpdateProvisionedVm(vmid, payload) {
    return apiClient.apiPutBeagleJson("/beagle-api/api/v1/provisioning/vms/" + encodeURIComponent(String(vmid)), payload).then(function(response) {
      return response && response.provisioned_vm ? response.provisioned_vm : response;
    });
  }

  function apiGetProvisioningState(vmid) {
    return apiClient.apiGetBeagleJson("/beagle-api/api/v1/provisioning/vms/" + encodeURIComponent(String(vmid))).then(function(response) {
      return response && response.provisioning ? response.provisioning : response;
    });
  }

  window.BeagleUiProvisioningApi = {
    apiGetProvisioningCatalog: apiGetProvisioningCatalog,
    apiCreateProvisionedVm: apiCreateProvisionedVm,
    apiUpdateProvisionedVm: apiUpdateProvisionedVm,
    apiGetProvisioningState: apiGetProvisioningState
  };
})();

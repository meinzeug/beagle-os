(function() {
  "use strict";

  var platformService = window.BeaglePlatformService;
  var provisioningApi = window.BeagleUiProvisioningApi;

  if (!platformService) {
    throw new Error("BeaglePlatformService must be loaded before BeagleUiFleetState");
  }
  if (!provisioningApi) {
    throw new Error("BeagleUiProvisioningApi must be loaded before BeagleUiFleetState");
  }

  function loadFleetPayload() {
    return Promise.all([
      platformService.fetchHealth(),
      platformService.fetchInventory(),
      platformService.fetchPolicies(),
      provisioningApi.apiGetProvisioningCatalog()
    ]).then(function(results) {
      return {
        health: results[0] || {},
        vms: results[1] || [],
        policies: results[2] || [],
        catalog: results[3] || {}
      };
    });
  }

  window.BeagleUiFleetState = {
    loadFleetPayload: loadFleetPayload
  };
})();

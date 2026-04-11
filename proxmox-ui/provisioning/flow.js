(function() {
  "use strict";

  var provisioningApi = window.BeagleUiProvisioningApi;
  var virtualizationService = window.BeagleVirtualizationService;
  var provisioningResultModal = window.BeagleUiProvisioningResultModal;
  var provisioningCreateModal = window.BeagleUiProvisioningCreateModal;

  if (!provisioningApi) {
    throw new Error("BeagleUiProvisioningApi must be loaded before BeagleUiProvisioningFlow");
  }
  if (!virtualizationService) {
    throw new Error("BeagleVirtualizationService must be loaded before BeagleUiProvisioningFlow");
  }
  if (!provisioningResultModal) {
    throw new Error("BeagleUiProvisioningResultModal must be loaded before BeagleUiProvisioningFlow");
  }
  if (!provisioningCreateModal) {
    throw new Error("BeagleUiProvisioningCreateModal must be loaded before BeagleUiProvisioningFlow");
  }

  function parseListText(value) {
    return String(value || "")
      .split(/[\n,]+/)
      .map(function(item) { return String(item || "").trim(); })
      .filter(Boolean);
  }

  function fetchProvisioningCatalog() {
    return provisioningApi.apiGetProvisioningCatalog();
  }

  function fetchProvisioningState(vmid) {
    return provisioningApi.apiGetProvisioningState(vmid);
  }

  function buildProvisioningCredentialText(created, state) {
    return provisioningResultModal.buildProvisioningCredentialText(created, state);
  }

  function showProvisioningResultWindow(options) {
    return provisioningResultModal.showProvisioningResultWindow({
      created: options.created,
      apiGetProvisioningState: fetchProvisioningState,
      copyText: options.copyText,
      showProfileModal: options.showProfileModal
    });
  }

  function showUbuntuBeagleCreateModal(options) {
    return provisioningCreateModal.showUbuntuBeagleCreateModal({
      ctx: options.ctx,
      showError: options.showError,
      showToast: options.showToast,
      ensureApiToken: options.ensureApiToken,
      apiGetProvisioningCatalog: fetchProvisioningCatalog,
      apiCreateProvisionedVm: provisioningApi.apiCreateProvisionedVm,
      apiUpdateProvisionedVm: provisioningApi.apiUpdateProvisionedVm,
      virtualizationService: virtualizationService,
      selectedNodeName: virtualizationService.selectedNodeName,
      parseListText: parseListText,
      showProfileModal: options.showProfileModal,
      showProvisioningResultWindow: function(created) {
        return showProvisioningResultWindow({
          created: created,
          copyText: options.copyText,
          showProfileModal: options.showProfileModal
        });
      }
    });
  }

  window.BeagleUiProvisioningFlow = {
    buildProvisioningCredentialText: buildProvisioningCredentialText,
    fetchProvisioningCatalog: fetchProvisioningCatalog,
    fetchProvisioningState: fetchProvisioningState,
    showProvisioningResultWindow: showProvisioningResultWindow,
    showUbuntuBeagleCreateModal: showUbuntuBeagleCreateModal
  };
})();

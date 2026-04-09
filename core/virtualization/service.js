(function() {
  "use strict";

  var registry = window.BeagleProviderRegistry;

  if (!registry) {
    throw new Error("BeagleProviderRegistry must be loaded before BeagleVirtualizationService");
  }

  function provider() {
    return registry.getProvider("virtualization");
  }

  function callProviderMethod(methodName, args) {
    var target = provider();
    if (!target || typeof target[methodName] !== "function") {
      throw new Error("Virtualization provider is missing method: " + methodName);
    }
    return Promise.resolve(target[methodName].apply(target, args || []));
  }

  function listHosts() {
    return callProviderMethod("listHosts");
  }

  function listNodes() {
    return callProviderMethod("listNodes");
  }

  function listVms() {
    return callProviderMethod("listVms");
  }

  function getVmState(ctx) {
    return callProviderMethod("getVmState", [ctx]);
  }

  function getVmConfig(ctx) {
    return callProviderMethod("getVmConfig", [ctx]);
  }

  function getVmGuestInterfaces(ctx) {
    return callProviderMethod("getVmGuestInterfaces", [ctx]);
  }

  function selectedNodeName() {
    var target = provider();
    if (!target || typeof target.selectedNodeName !== "function") {
      return "";
    }
    return String(target.selectedNodeName() || "");
  }

  window.BeagleVirtualizationService = {
    listHosts: listHosts,
    listNodes: listNodes,
    listVms: listVms,
    getVmState: getVmState,
    getVmConfig: getVmConfig,
    getVmGuestInterfaces: getVmGuestInterfaces,
    selectedNodeName: selectedNodeName
  };
})();

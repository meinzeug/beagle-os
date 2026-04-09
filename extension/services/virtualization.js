(function() {
  "use strict";

  var registry = window.BeagleExtensionProviderRegistry;

  if (!registry) {
    throw new Error("BeagleExtensionProviderRegistry must be loaded before BeagleExtensionVirtualizationService");
  }

  function provider() {
    return registry.getProvider("virtualization");
  }

  function callProviderMethod(methodName, args, fallbackValue) {
    var target = provider();
    if (!target || typeof target[methodName] !== "function") {
      if (arguments.length >= 3) {
        return Promise.resolve(fallbackValue);
      }
      throw new Error("Virtualization provider is missing method: " + String(methodName));
    }
    return Promise.resolve(target[methodName].apply(target, args || []));
  }

  function isVmView() {
    var target = provider();
    if (!target || typeof target.isVmView !== "function") {
      return false;
    }
    return Boolean(target.isVmView());
  }

  function parseVmContext() {
    return callProviderMethod("parseVmContext");
  }

  function listHosts() {
    return callProviderMethod("listHosts", [], []);
  }

  function listNodes() {
    return callProviderMethod("listNodes", [], []);
  }

  function listVms() {
    return callProviderMethod("listVms", [], []);
  }

  function getVmState(ctx) {
    return callProviderMethod("getVmState", [ctx], {});
  }

  function getVmConfig(ctx) {
    return callProviderMethod("getVmConfig", [ctx], {});
  }

  function getVmGuestInterfaces(ctx) {
    return callProviderMethod("getVmGuestInterfaces", [ctx], []);
  }

  window.BeagleExtensionVirtualizationService = {
    getVmConfig: getVmConfig,
    getVmGuestInterfaces: getVmGuestInterfaces,
    getVmState: getVmState,
    isVmView: isVmView,
    listHosts: listHosts,
    listNodes: listNodes,
    listVms: listVms,
    parseVmContext: parseVmContext
  };
})();

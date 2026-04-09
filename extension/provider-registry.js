(function() {
  "use strict";

  var providers = {};

  function registerProvider(kind, provider) {
    if (!kind) {
      throw new Error("Provider kind is required");
    }
    if (!provider || typeof provider !== "object") {
      throw new Error("Provider implementation is required for " + String(kind));
    }
    providers[String(kind)] = provider;
    return provider;
  }

  function hasProvider(kind) {
    return Boolean(providers[String(kind)]);
  }

  function getProvider(kind) {
    var provider = providers[String(kind)];
    if (!provider) {
      throw new Error("Provider not registered: " + String(kind));
    }
    return provider;
  }

  function listProviders() {
    return Object.keys(providers);
  }

  window.BeagleExtensionProviderRegistry = {
    getProvider: getProvider,
    hasProvider: hasProvider,
    listProviders: listProviders,
    registerProvider: registerProvider
  };
})();

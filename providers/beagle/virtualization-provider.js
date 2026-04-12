(function() {
  "use strict";

  var registry = window.BeagleProviderRegistry;
  var apiClient = window.BeagleUiApiClient;

  if (!registry) {
    throw new Error("BeagleProviderRegistry must be loaded before the Beagle virtualization provider");
  }
  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before the Beagle virtualization provider");
  }

  function inventoryVms() {
    return apiClient.apiGetBeagleJson("/api/v1/vms").then(function(payload) {
      return Array.isArray(payload && payload.vms) ? payload.vms : [];
    });
  }

  function inventoryNodes() {
    return apiClient.apiGetBeagleJson("/api/v1/virtualization/nodes").then(function(payload) {
      return Array.isArray(payload && payload.nodes) ? payload.nodes : [];
    });
  }

  function inventoryHosts() {
    return apiClient.apiGetBeagleJson("/api/v1/virtualization/hosts").then(function(payload) {
      return Array.isArray(payload && payload.hosts) ? payload.hosts : [];
    });
  }

  function normalizeVmRecord(item) {
    return {
      vmid: Number(item && item.vmid || 0),
      node: String(item && item.node || ""),
      name: String(item && item.name || ""),
      status: String(item && item.status || "unknown"),
      tags: String(item && item.tags || ""),
      type: "qemu"
    };
  }

  function listNodes() {
    return inventoryNodes().then(function(nodes) {
      return (Array.isArray(nodes) ? nodes : []).map(function(item) {
        return {
          id: String(item && item.id || item && item.name || ""),
          name: String(item && item.name || ""),
          label: String(item && item.label || item && item.name || ""),
          status: String(item && item.status || "unknown")
        };
      });
    });
  }

  function listHosts() {
    return inventoryHosts().then(function(hosts) {
      return (Array.isArray(hosts) ? hosts : []).map(function(node) {
        return {
          id: String(node && node.id || node && node.name || ""),
          name: String(node && node.name || ""),
          label: String(node && node.label || node && node.name || ""),
          status: String(node && node.status || "unknown")
        };
      });
    });
  }

  function listVms() {
    return inventoryVms().then(function(vms) {
      return (Array.isArray(vms) ? vms : []).map(normalizeVmRecord);
    });
  }

  function getVmState(ctx) {
    return listVms().then(function(vms) {
      return vms.find(function(item) {
        return Number(item && item.vmid) === Number(ctx && ctx.vmid);
      }) || {};
    });
  }

  function getVmConfig(ctx) {
    return apiClient.apiGetBeagleJson("/api/v1/virtualization/vms/" + encodeURIComponent(String(ctx && ctx.vmid || "")) + "/config").then(function(payload) {
      var config = payload && payload.config ? payload.config : {};
      return {
        vmid: Number(config && config.vmid || ctx && ctx.vmid || 0),
        node: String(config && config.node || ctx && ctx.node || ""),
        name: String(config && config.name || ("vm-" + String(ctx && ctx.vmid || ""))),
        description: String(config && config.description || ""),
        tags: String(config && config.tags || "")
      };
    });
  }

  function getVmGuestInterfaces(ctx) {
    return apiClient.apiGetBeagleJson("/api/v1/virtualization/vms/" + encodeURIComponent(String(ctx && ctx.vmid || "")) + "/interfaces").then(function(payload) {
      return Array.isArray(payload && payload.interfaces) ? payload.interfaces : [];
    });
  }

  function selectedNodeName() {
    return "";
  }

  registry.registerProvider("virtualization", {
    providerId: "beagle",
    listHosts: listHosts,
    listNodes: listNodes,
    listVms: listVms,
    getVmState: getVmState,
    getVmConfig: getVmConfig,
    getVmGuestInterfaces: getVmGuestInterfaces,
    selectedNodeName: selectedNodeName
  });
})();

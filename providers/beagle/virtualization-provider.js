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
    return inventoryVms().then(function(vms) {
      var seen = {};
      var nodes = [];
      (Array.isArray(vms) ? vms : []).forEach(function(item) {
        var nodeName = String(item && item.node || "");
        if (!nodeName || seen[nodeName]) {
          return;
        }
        seen[nodeName] = true;
        nodes.push({
          id: nodeName,
          name: nodeName,
          label: nodeName,
          status: "online"
        });
      });
      return nodes;
    });
  }

  function listHosts() {
    return listNodes().then(function(nodes) {
      return nodes.map(function(node) {
        return {
          id: node.id,
          name: node.name,
          label: node.label,
          status: node.status
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
    return getVmState(ctx).then(function(state) {
      return {
        vmid: Number(ctx && ctx.vmid || 0),
        node: String(ctx && ctx.node || state.node || ""),
        name: String(state.name || ("vm-" + String(ctx && ctx.vmid || ""))),
        description: "",
        tags: String(state.tags || "")
      };
    });
  }

  function getVmGuestInterfaces(ctx) {
    void ctx;
    return Promise.resolve([]);
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

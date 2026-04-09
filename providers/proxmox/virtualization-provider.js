(function() {
  "use strict";

  var registry = window.BeagleProviderRegistry;
  var apiClient = window.BeagleUiApiClient;

  if (!registry) {
    throw new Error("BeagleProviderRegistry must be loaded before the Proxmox virtualization provider");
  }
  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before the Proxmox virtualization provider");
  }

  function selectedNodeFromHash() {
    try {
      var decodedHash = window.decodeURIComponent(String(window.location.hash || ""));
      var match = decodedHash.match(/node\/([^:\/]+)/);
      return match ? String(match[1] || "") : "";
    } catch (error) {
      return "";
    }
  }

  function resourceStoreNodes() {
    if (!(window.PVE && PVE.data && PVE.data.ResourceStore && typeof PVE.data.ResourceStore.getNodes === "function")) {
      return [];
    }
    return PVE.data.ResourceStore.getNodes() || [];
  }

  function normalizeNodeRecord(node) {
    var name = String(node && (node.node || node.name || node.id) || "");
    return {
      id: name,
      name: name,
      label: name ? (node && node.status ? (name + " (" + String(node.status || "") + ")") : name) : "",
      status: String(node && node.status || "")
    };
  }

  function listNodes() {
    var nodes = resourceStoreNodes();
    if (nodes.length) {
      return Promise.resolve(nodes.map(normalizeNodeRecord).filter(function(node) {
        return Boolean(node.id);
      }));
    }
    return apiClient.apiGetJson("/api2/json/nodes").then(function(payload) {
      var list = Array.isArray(payload) ? payload : [];
      return list.map(normalizeNodeRecord).filter(function(node) {
        return Boolean(node.id);
      });
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
    return apiClient.apiGetJson("/api2/json/cluster/resources?type=vm").then(function(payload) {
      return Array.isArray(payload) ? payload : [];
    });
  }

  function getVmState(ctx) {
    return listVms().then(function(vms) {
      return vms.find(function(item) {
        return item && item.type === "qemu" && Number(item.vmid) === Number(ctx && ctx.vmid);
      }) || {};
    });
  }

  function getVmConfig(ctx) {
    return apiClient.apiGetJson("/api2/json/nodes/" + encodeURIComponent(String(ctx && ctx.node || "")) + "/qemu/" + encodeURIComponent(String(ctx && ctx.vmid || "")) + "/config");
  }

  function getVmGuestInterfaces(ctx) {
    return apiClient.apiGetJson("/api2/json/nodes/" + encodeURIComponent(String(ctx && ctx.node || "")) + "/qemu/" + encodeURIComponent(String(ctx && ctx.vmid || "")) + "/agent/network-get-interfaces").then(function(payload) {
      return Array.isArray(payload) ? payload : [];
    });
  }

  function selectedNodeName() {
    var node = selectedNodeFromHash();
    if (node) {
      return node;
    }
    var nodes = resourceStoreNodes();
    if (nodes.length === 1 && nodes[0] && nodes[0].node) {
      return String(nodes[0].node);
    }
    return "";
  }

  registry.registerProvider("virtualization", {
    providerId: "proxmox",
    listHosts: listHosts,
    listNodes: listNodes,
    listVms: listVms,
    getVmState: getVmState,
    getVmConfig: getVmConfig,
    getVmGuestInterfaces: getVmGuestInterfaces,
    selectedNodeName: selectedNodeName
  });
})();

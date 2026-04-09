(function() {
  "use strict";

  var registry = window.BeagleExtensionProviderRegistry;
  var common = window.BeagleExtensionCommon;

  if (!registry) {
    throw new Error("BeagleExtensionProviderRegistry must be loaded before the Proxmox extension provider");
  }
  if (!common) {
    throw new Error("BeagleExtensionCommon must be loaded before the Proxmox extension provider");
  }

  function apiGetJson(path) {
    return fetch(path, { credentials: "same-origin" })
      .then(function(response) {
        if (!response.ok) {
          throw new Error("API request failed: " + response.status + " " + response.statusText);
        }
        return response.json();
      })
      .then(function(payload) {
        return payload && payload.data != null ? payload.data : payload;
      });
  }

  function listHosts() {
    return listNodes();
  }

  function listNodes() {
    return apiGetJson("/api2/json/nodes").catch(function() {
      return [];
    });
  }

  function listVms() {
    return apiGetJson("/api2/json/cluster/resources?type=vm").catch(function() {
      return [];
    });
  }

  function isVmView() {
    return /qemu\/(\d+)/i.test(common.decodeHash());
  }

  async function parseVmContext() {
    var hash = common.decodeHash();
    var vmidMatch = hash.match(/qemu\/(\d+)/i);
    var nodeMatch = hash.match(/[?&]node=([a-zA-Z0-9._-]+)/i);
    var vmid = vmidMatch ? Number(vmidMatch[1]) : null;
    var node = nodeMatch ? nodeMatch[1] : null;
    var guessed = null;
    var resources = null;
    var vm = null;

    if (!vmid) {
      return null;
    }

    if (!node) {
      resources = await listVms().catch(function() {
        return [];
      });
      vm = (Array.isArray(resources) ? resources : []).find(function(item) {
        return item && item.type === "qemu" && Number(item.vmid) === vmid;
      });
      if (vm && vm.node) {
        node = vm.node;
      }
    }

    if (!node) {
      guessed = hash.match(/node[:=]([a-zA-Z0-9._-]+)/i);
      if (guessed) {
        node = guessed[1];
      }
    }

    if (!node) {
      return null;
    }
    return { node: node, vmid: vmid };
  }

  async function getVmState(ctx) {
    var resources = await listVms().catch(function() {
      return [];
    });
    return (Array.isArray(resources) ? resources : []).find(function(item) {
      return item && item.type === "qemu" && Number(item.vmid) === Number(ctx && ctx.vmid);
    }) || {};
  }

  function getVmConfig(ctx) {
    return apiGetJson(
      "/api2/json/nodes/" +
        encodeURIComponent(String(ctx && ctx.node || "")) +
        "/qemu/" +
        encodeURIComponent(String(ctx && ctx.vmid || "")) +
        "/config"
    );
  }

  function getVmGuestInterfaces(ctx) {
    return apiGetJson(
      "/api2/json/nodes/" +
        encodeURIComponent(String(ctx && ctx.node || "")) +
        "/qemu/" +
        encodeURIComponent(String(ctx && ctx.vmid || "")) +
        "/agent/network-get-interfaces"
    ).catch(function() {
      return [];
    });
  }

  registry.registerProvider("virtualization", {
    getVmConfig: getVmConfig,
    getVmGuestInterfaces: getVmGuestInterfaces,
    getVmState: getVmState,
    isVmView: isVmView,
    listHosts: listHosts,
    listNodes: listNodes,
    listVms: listVms,
    parseVmContext: parseVmContext,
    providerId: "proxmox"
  });
})();

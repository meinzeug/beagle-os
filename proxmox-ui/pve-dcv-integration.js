(function() {
  "use strict";

  var DEFAULTS = {
    urlTemplate: "https://{ip}:8443/",
    fallbackUrl: "",
    metadataKeys: ["dcv-url", "dcv-host", "dcv-ip"],
    usbInstallerUrl: "https://github.com/meinzeug/pve-dcv-integration/releases/latest/download/pve-thin-client-usb-installer-latest.sh"
  };
  var MARKER = "data-pve-dcv-integration";
  var CONSOLE_LABEL = "Konsole";
  var DCV_LABEL = "DCV";
  var USB_LABEL = "USB Installer";

  function decodeHash() {
    try {
      return decodeURIComponent(window.location.hash || "");
    } catch (_error) {
      return window.location.hash || "";
    }
  }

  function isVmView() {
    return /qemu\/(\d+)/i.test(decodeHash());
  }

  function getConfig() {
    var runtimeConfig = window.PVEDCVIntegrationConfig || {};
    return {
      urlTemplate: runtimeConfig.urlTemplate || DEFAULTS.urlTemplate,
      fallbackUrl: runtimeConfig.fallbackUrl || DEFAULTS.fallbackUrl,
      metadataKeys: Array.isArray(runtimeConfig.metadataKeys) ? runtimeConfig.metadataKeys : DEFAULTS.metadataKeys,
      usbInstallerUrl: runtimeConfig.usbInstallerUrl || DEFAULTS.usbInstallerUrl
    };
  }

  function parseVmContext() {
    var hash = decodeHash();
    var vmidMatch = hash.match(/qemu\/(\d+)/i);
    var nodeMatch = hash.match(/[?&]node=([a-zA-Z0-9._-]+)/i);
    var vmid = vmidMatch ? Number(vmidMatch[1]) : null;
    var node = nodeMatch ? nodeMatch[1] : null;

    if (!vmid) {
      return Promise.resolve(null);
    }

    if (node) {
      return Promise.resolve({ node: node, vmid: vmid });
    }

    return fetch("/api2/json/cluster/resources?type=vm", { credentials: "same-origin" })
      .then(function(res) {
        return res.ok ? res.json() : { data: [] };
      })
      .then(function(payload) {
        var vm = (payload.data || []).find(function(item) {
          return item.vmid === vmid && item.type === "qemu";
        });
        node = vm && vm.node ? vm.node : null;
        if (!node) {
          var guessed = hash.match(/node[:=]([a-zA-Z0-9._-]+)/i);
          node = guessed ? guessed[1] : null;
        }
        return node ? { node: node, vmid: vmid } : null;
      })
      .catch(function() {
        var guessed = hash.match(/node[:=]([a-zA-Z0-9._-]+)/i);
        node = guessed ? guessed[1] : null;
        return node ? { node: node, vmid: vmid } : null;
      });
  }

  function firstUsefulIp(ifaces) {
    for (var i = 0; i < (ifaces || []).length; i += 1) {
      var iface = ifaces[i];
      var addresses = iface["ip-addresses"] || [];
      for (var j = 0; j < addresses.length; j += 1) {
        var addr = addresses[j];
        var ip = addr["ip-address"] || "";
        if (addr["ip-address-type"] !== "ipv4") continue;
        if (!ip || ip.indexOf("127.") === 0 || ip.indexOf("169.254.") === 0) continue;
        return ip;
      }
    }
    return null;
  }

  function parseDescriptionMeta(description, metadataKeys) {
    var text = String(description || "");
    var result = { dcvUrl: null, dcvHost: null, dcvIp: null };
    var keys = Array.from(new Set(DEFAULTS.metadataKeys.concat(metadataKeys || [])));

    keys.forEach(function(key) {
      var match = text.match(new RegExp(key + "\\s*:\\s*([^\\n\\r]+)", "i"));
      if (!match) return;
      var value = String(match[1] || "").trim();
      if (key === "dcv-url" && /^https?:\/\//i.test(value)) result.dcvUrl = value;
      if (key === "dcv-host" && !result.dcvHost) result.dcvHost = value;
      if (key === "dcv-ip" && !result.dcvIp && /^\d{1,3}(\.\d{1,3}){3}$/.test(value)) result.dcvIp = value;
    });

    return result;
  }

  function fillTemplate(template, values) {
    return template
      .replaceAll("{ip}", values.ip || "")
      .replaceAll("{node}", values.node || "")
      .replaceAll("{vmid}", String(values.vmid || ""))
      .replaceAll("{host}", values.host || "");
  }

  function buildLaunchUrl(ctx) {
    var config = getConfig();
    var host = window.location.hostname;
    var ip = null;
    var dcvUrl = null;
    var dcvHost = null;
    var dcvIp = null;

    function loadConfig() {
      return fetch("/api2/json/nodes/" + encodeURIComponent(ctx.node) + "/qemu/" + ctx.vmid + "/config", {
        credentials: "same-origin"
      })
        .then(function(res) {
          return res.ok ? res.json() : { data: {} };
        })
        .then(function(payload) {
          var meta = parseDescriptionMeta(payload.data && payload.data.description, config.metadataKeys);
          dcvUrl = meta.dcvUrl;
          dcvHost = meta.dcvHost;
          dcvIp = meta.dcvIp;
        });
    }

    function loadAgent() {
      return fetch("/api2/json/nodes/" + encodeURIComponent(ctx.node) + "/qemu/" + ctx.vmid + "/agent/network-get-interfaces", {
        credentials: "same-origin"
      })
        .then(function(res) {
          if (!res.ok) return null;
          return res.json();
        })
        .then(function(payload) {
          if (payload && payload.data && payload.data.result) {
            ip = firstUsefulIp(payload.data.result);
          }
        })
        .catch(function() {
          return null;
        });
    }

    return loadAgent()
      .then(loadConfig)
      .then(function() {
        if (dcvUrl) return dcvUrl;
        if (!ip && dcvIp) ip = dcvIp;
        if (!ip && dcvHost) ip = dcvHost;
        if (ip) {
          return fillTemplate(config.urlTemplate, {
            ip: ip,
            node: ctx.node,
            vmid: ctx.vmid,
            host: host
          });
        }
        return config.fallbackUrl || null;
      });
  }

  function openDcv() {
    parseVmContext().then(function(ctx) {
      if (!ctx) {
        window.alert("DCV: Keine VM-Ansicht erkannt.");
        return;
      }

      buildLaunchUrl(ctx).then(function(url) {
        if (!url) {
          window.alert("DCV URL konnte nicht ermittelt werden. Pruefe Guest Agent oder VM-Beschreibung.");
          return;
        }
        window.open(url, "_blank", "noopener,noreferrer");
      });
    });
  }

  function openUsbInstaller() {
    window.open(getConfig().usbInstallerUrl, "_blank", "noopener,noreferrer");
  }

  function findToolbar() {
    var all = Array.from(document.querySelectorAll("button, a, div, span"));
    for (var i = 0; i < all.length; i += 1) {
      var node = all[i];
      var text = String(node.textContent || "").trim();
      if (text === CONSOLE_LABEL || text.indexOf(CONSOLE_LABEL) !== -1) {
        return node.closest(".x-toolbar") || node.closest(".x-box-inner") || node.parentElement;
      }
    }
    return null;
  }

  function createToolbarButton(label, handler) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute(MARKER, label);
    button.className = "x-btn-text";
    button.style.marginLeft = "6px";
    button.style.padding = "4px 10px";
    button.style.border = "1px solid #b5b8c8";
    button.style.background = "#f5f5f5";
    button.style.borderRadius = "3px";
    button.style.cursor = "pointer";
    button.addEventListener("click", function(event) {
      event.preventDefault();
      event.stopPropagation();
      handler();
    });
    return button;
  }

  function ensureToolbarButtons() {
    if (!isVmView()) return;
    var toolbar = findToolbar();
    if (!toolbar) return;

    if (!toolbar.querySelector("[" + MARKER + "='" + USB_LABEL + "']")) {
      toolbar.appendChild(createToolbarButton(USB_LABEL, openUsbInstaller));
    }
  }

  function getVisibleMenu() {
    var menus = Array.from(document.querySelectorAll(".x-menu"));
    for (var i = 0; i < menus.length; i += 1) {
      if (menus[i].offsetParent !== null) return menus[i];
    }
    return null;
  }

  function createMenuItem() {
    var item = document.createElement("a");
    item.href = "#";
    item.textContent = DCV_LABEL;
    item.className = "x-menu-item";
    item.setAttribute(MARKER, DCV_LABEL);
    item.style.display = "block";
    item.style.padding = "4px 24px";
    item.addEventListener("click", function(event) {
      event.preventDefault();
      event.stopPropagation();
      openDcv();
    });
    return item;
  }

  function ensureConsoleMenuEntry() {
    if (!isVmView()) return;
    var menu = getVisibleMenu();
    if (!menu) return;
    var text = menu.textContent || "";
    if (text.indexOf("noVNC") === -1 && text.indexOf("SPICE") === -1) return;
    if (!menu.querySelector("[" + MARKER + "='" + DCV_LABEL + "']")) {
      menu.appendChild(createMenuItem());
    }
  }

  function refresh() {
    ensureToolbarButtons();
    ensureConsoleMenuEntry();
  }

  function boot() {
    refresh();
    window.addEventListener("hashchange", refresh);
    document.addEventListener("click", function() {
      window.setTimeout(refresh, 25);
    }, true);
    var observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.setInterval(refresh, 1000);
  }

  boot();
})();

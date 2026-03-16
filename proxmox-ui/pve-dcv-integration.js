(function() {
  "use strict";

  function defaultUsbInstallerUrl() {
    return "https://{host}:8443/pve-dcv-downloads/pve-thin-client-usb-installer-vm-{vmid}.sh";
  }

  function defaultDownloadsStatusUrl() {
    return "https://" + window.location.hostname + ":8443/pve-dcv-downloads/pve-dcv-downloads-status.json";
  }

  var DEFAULTS = {
    urlTemplate: "https://{ip}:8443/",
    fallbackUrl: "",
    metadataKeys: ["dcv-url", "dcv-host", "dcv-ip", "dcv-user", "dcv-password", "dcv-auth-token", "dcv-session", "dcv-auto-submit"],
    usbInstallerUrl: null
  };

  function getConfig() {
    var runtimeConfig = window.PVEDCVIntegrationConfig || {};
    return {
      urlTemplate: runtimeConfig.urlTemplate || DEFAULTS.urlTemplate,
      fallbackUrl: runtimeConfig.fallbackUrl || DEFAULTS.fallbackUrl,
      metadataKeys: Array.isArray(runtimeConfig.metadataKeys) ? runtimeConfig.metadataKeys : DEFAULTS.metadataKeys,
      usbInstallerUrl: runtimeConfig.usbInstallerUrl || defaultUsbInstallerUrl(),
      downloadsStatusUrl: runtimeConfig.downloadsStatusUrl || defaultDownloadsStatusUrl()
    };
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
    var text = String(description || "").replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n");
    var result = {
      dcvUrl: null,
      dcvHost: null,
      dcvIp: null,
      dcvUser: null,
      dcvPassword: null,
      dcvAuthToken: null,
      dcvSession: null,
      dcvAutoSubmit: true
    };
    var keys = Array.from(new Set(DEFAULTS.metadataKeys.concat(metadataKeys || [])));

    keys.forEach(function(key) {
      var match = text.match(new RegExp(key + "\\s*:\\s*([^\\n\\r]+)", "i"));
      if (!match) return;
      var value = String(match[1] || "").trim();
      if (key === "dcv-url" && /^https?:\/\//i.test(value)) result.dcvUrl = value;
      if (key === "dcv-host" && !result.dcvHost) result.dcvHost = value;
      if (key === "dcv-ip" && !result.dcvIp && /^\d{1,3}(\.\d{1,3}){3}$/.test(value)) result.dcvIp = value;
      if (key === "dcv-user" && !result.dcvUser) result.dcvUser = value;
      if (key === "dcv-password" && !result.dcvPassword) result.dcvPassword = value;
      if (key === "dcv-auth-token" && !result.dcvAuthToken) result.dcvAuthToken = value;
      if (key === "dcv-session" && !result.dcvSession) result.dcvSession = value;
      if (key === "dcv-auto-submit") result.dcvAutoSubmit = !/^(0|false|no)$/i.test(value);
    });

    return result;
  }

  function applyDcvLaunchMetadata(rawUrl, meta) {
    var url;

    try {
      url = new URL(rawUrl, window.location.origin);
    } catch (error) {
      return rawUrl;
    }

    if (meta.dcvAuthToken && !url.searchParams.get("authToken")) {
      url.searchParams.set("authToken", meta.dcvAuthToken);
    }

    if (meta.dcvSession && !url.hash) {
      url.hash = meta.dcvSession;
    }

    if (!meta.dcvAuthToken) {
      if (meta.dcvUser) url.searchParams.set("pveDcvUser", meta.dcvUser);
      if (meta.dcvPassword) url.searchParams.set("pveDcvPassword", meta.dcvPassword);
      url.searchParams.set("pveDcvAutoSubmit", meta.dcvAutoSubmit ? "1" : "0");
    }

    return url.toString();
  }

  function fillTemplate(template, values) {
    return template
      .replaceAll("{ip}", values.ip || "")
      .replaceAll("{node}", values.node || "")
      .replaceAll("{vmid}", String(values.vmid || ""))
      .replaceAll("{host}", values.host || "");
  }

  function resolveUsbInstallerUrl(ctx) {
    var config = getConfig();
    var template = config.usbInstallerUrl || defaultUsbInstallerUrl();
    return fillTemplate(template, {
      ip: "",
      node: ctx && ctx.node,
      vmid: ctx && ctx.vmid,
      host: window.location.hostname
    });
  }

  function resolveLaunchState(ctx) {
    var config = getConfig();
    var host = window.location.hostname;
    var ip = null;
    var meta = {
      dcvUrl: null,
      dcvHost: null,
      dcvIp: null,
      dcvUser: null,
      dcvPassword: null,
      dcvAuthToken: null,
      dcvSession: null,
      dcvAutoSubmit: true
    };

    function loadConfig() {
      return fetch("/api2/json/nodes/" + encodeURIComponent(ctx.node) + "/qemu/" + ctx.vmid + "/config", {
        credentials: "same-origin"
      })
        .then(function(res) {
          return res.ok ? res.json() : { data: {} };
        })
        .then(function(payload) {
          meta = parseDescriptionMeta(payload.data && payload.data.description, config.metadataKeys);
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
        var baseUrl = meta.dcvUrl;
        var source = "metadata:dcv-url";
        if (!ip && meta.dcvIp) ip = meta.dcvIp;
        if (!ip && meta.dcvHost) ip = meta.dcvHost;
        if (!baseUrl && ip) {
          source = meta.dcvIp ? "metadata:dcv-ip" : (meta.dcvHost ? "metadata:dcv-host" : "agent-or-template");
          baseUrl = fillTemplate(config.urlTemplate, {
            ip: ip,
            node: ctx.node,
            vmid: ctx.vmid,
            host: host
          });
        }
        if (!baseUrl && config.fallbackUrl) {
          source = "fallback-url";
          baseUrl = config.fallbackUrl;
        }
        return {
          launchUrl: baseUrl ? applyDcvLaunchMetadata(baseUrl, meta) : null,
          baseUrl: baseUrl,
          ip: ip,
          source: baseUrl ? source : "unresolved",
          meta: meta
        };
      });
  }

  function buildLaunchUrl(ctx) {
    return resolveLaunchState(ctx).then(function(state) {
      return state.launchUrl;
    });
  }

  function showError(message) {
    if (window.Ext && Ext.Msg && Ext.Msg.alert) {
      Ext.Msg.alert("PVE DCV Integration", message);
    } else {
      window.alert(message);
    }
  }

  function openDcvForContext(ctx) {
    buildLaunchUrl(ctx).then(function(url) {
      if (!url) {
        showError("DCV URL konnte nicht ermittelt werden. Pruefe Guest Agent oder VM-Beschreibung.");
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
    });
  }

  function openDownloadsStatus() {
    window.open(getConfig().downloadsStatusUrl, "_blank", "noopener,noreferrer");
  }

  function copyText(text, successMessage) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function() {
        if (window.Ext && Ext.toast) {
          Ext.toast(successMessage);
        }
      });
    }

    var input = document.createElement("textarea");
    input.value = text;
    document.body.appendChild(input);
    input.select();
    try {
      document.execCommand("copy");
      if (window.Ext && Ext.toast) {
        Ext.toast(successMessage);
      }
      return Promise.resolve();
    } catch (error) {
      return Promise.reject(error);
    } finally {
      document.body.removeChild(input);
    }
  }

  function copyDcvUrlForContext(ctx) {
    resolveLaunchState(ctx).then(function(state) {
      if (!state.launchUrl) {
        showError("DCV URL konnte nicht ermittelt werden. Pruefe Guest Agent oder VM-Beschreibung.");
        return;
      }
      copyText(state.launchUrl, "DCV URL in die Zwischenablage kopiert.").catch(function() {
        showError("DCV URL konnte nicht in die Zwischenablage kopiert werden.");
      });
    });
  }

  function showDcvInfoForContext(ctx) {
    resolveLaunchState(ctx).then(function(state) {
      var lines = [
        "VM: " + ctx.vmid + " auf " + ctx.node,
        "Quelle: " + state.source,
        "IP/Host: " + (state.ip || state.meta.dcvHost || "n/a"),
        "Session: " + (state.meta.dcvSession || "n/a"),
        "Auth-Token: " + (state.meta.dcvAuthToken ? "ja" : "nein"),
        "Auto-Submit: " + (state.meta.dcvAutoSubmit ? "ja" : "nein"),
        "Download-Status: " + getConfig().downloadsStatusUrl,
        "Launch-URL: " + (state.launchUrl || "nicht aufloesbar")
      ];
      if (window.Ext && Ext.Msg && Ext.Msg.show) {
        Ext.Msg.show({
          title: "PVE DCV Info",
          message: "<pre style=\"white-space:pre-wrap;line-height:1.4\">" + Ext.String.htmlEncode(lines.join("\n")) + "</pre>",
          buttons: Ext.Msg.OK
        });
      } else {
        window.alert(lines.join("\n"));
      }
    });
  }

  function openUsbInstaller(ctx) {
    var url = resolveUsbInstallerUrl(ctx || {});
    if (!url) {
      showError("USB Installer URL konnte nicht ermittelt werden.");
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function ensureConsoleButtonIntegration(button) {
    if (!button || !button.vmid || button.consoleType !== "kvm" || button.__pveDcvIntegrated) {
      return;
    }

    var menu = button.getMenu ? button.getMenu() : button.menu;
    if (menu && !menu.down("#pveDcvMenuItem")) {
      menu.add({
        itemId: "pveDcvMenuItem",
        text: "DCV",
        iconCls: "fa fa-desktop",
        handler: function() {
          openDcvForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      menu.add({
        itemId: "pveDcvCopyMenuItem",
        text: "Copy DCV URL",
        iconCls: "fa fa-clipboard",
        handler: function() {
          copyDcvUrlForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      menu.add({
        itemId: "pveDcvInfoMenuItem",
        text: "DCV Info",
        iconCls: "fa fa-info-circle",
        handler: function() {
          showDcvInfoForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      menu.add({
        itemId: "pveDcvDownloadsMenuItem",
        text: "DCV Downloads",
        iconCls: "fa fa-download",
        handler: openDownloadsStatus
      });
      menu.add({
        itemId: "pveUsbInstallerMenuItem",
        text: "USB Installer",
        iconCls: "fa fa-download",
        handler: function() {
          openUsbInstaller({ node: button.nodename, vmid: button.vmid });
        }
      });
    }

    var toolbar = button.up && button.up("toolbar");
    if (toolbar && !toolbar.down("#pveDcvLaunchButton")) {
      var index = toolbar.items.indexOf(button);
      toolbar.insert(index + 1, {
        xtype: "button",
        itemId: "pveDcvLaunchButton",
        text: "DCV",
        iconCls: "fa fa-desktop",
        handler: function() {
          openDcvForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      toolbar.insert(index + 2, {
        xtype: "button",
        itemId: "pveDcvCopyButton",
        text: "Copy DCV URL",
        iconCls: "fa fa-clipboard",
        handler: function() {
          copyDcvUrlForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      toolbar.insert(index + 3, {
        xtype: "button",
        itemId: "pveDcvInfoButton",
        text: "DCV Info",
        iconCls: "fa fa-info-circle",
        handler: function() {
          showDcvInfoForContext({ node: button.nodename, vmid: button.vmid });
        }
      });
      toolbar.insert(index + 4, {
        xtype: "button",
        itemId: "pveUsbInstallerButton",
        text: "USB Installer",
        iconCls: "fa fa-download",
        handler: function() {
          openUsbInstaller({ node: button.nodename, vmid: button.vmid });
        }
      });
      toolbar.insert(index + 5, {
        xtype: "button",
        itemId: "pveDownloadsStatusButton",
        text: "Downloads Status",
        iconCls: "fa fa-list-alt",
        handler: openDownloadsStatus
      });
    }

    button.__pveDcvIntegrated = true;
  }

  function integrate() {
    if (!(window.Ext && Ext.ComponentQuery)) {
      return;
    }

    Ext.ComponentQuery.query("pveConsoleButton").forEach(ensureConsoleButtonIntegration);
  }

  function boot() {
    integrate();
    window.setInterval(integrate, 1000);
  }

  if (window.Ext && Ext.onReady) {
    Ext.onReady(boot);
  } else {
    boot();
  }
})();

(function() {
  "use strict";

  var common = window.BeagleExtensionCommon;

  if (!common) {
    throw new Error("BeagleExtensionCommon must be loaded before BeagleExtensionPlatformService");
  }

  var beagleUiConfigPromise = null;

  function unwrapInstallerPrep(payload) {
    return payload && payload.installer_prep ? payload.installer_prep : payload;
  }

  function getBeagleUiConfig() {
    if (!beagleUiConfigPromise) {
      beagleUiConfigPromise = fetch("/pve2/js/beagle-ui-config.js", { credentials: "same-origin" })
        .then(function(response) {
          return response.ok ? response.text() : "";
        })
        .then(function(text) {
          var apiTokenMatch = text.match(/apiToken:\s*["']([^"']*)["']/);
          var webUiUrlMatch = text.match(/webUiUrl:\s*["']([^"']*)["']/);
          return {
            apiToken: apiTokenMatch ? apiTokenMatch[1] : "",
            webUiUrl: webUiUrlMatch ? webUiUrlMatch[1] : ""
          };
        })
        .catch(function() {
          return { apiToken: "", webUiUrl: "" };
        });
    }
    return beagleUiConfigPromise;
  }

  async function getApiToken(interactive) {
    var stored = common.readStoredApiToken();
    var config = null;
    var configured = "";

    if (stored) {
      return stored;
    }
    config = await getBeagleUiConfig();
    configured = String(config.apiToken || "").trim();
    if (configured) {
      return configured;
    }
    if (!interactive) {
      return "";
    }
    return common.promptForApiToken();
  }

  async function buildBeagleApiHeaders(extraHeaders, interactive) {
    var headers = Object.assign({}, extraHeaders || {});
    var token = await getApiToken(interactive !== false);
    if (token) {
      headers.Authorization = "Bearer " + token;
    }
    return headers;
  }

  async function resolveUsbInstallerUrl(ctx) {
    var options = await common.getStoredOptions();
    return common.fillTemplate(options.usbInstallerUrl || common.defaultUsbInstallerUrl(), {
      host: window.location.hostname,
      node: ctx && ctx.node || "",
      vmid: ctx && ctx.vmid || ""
    });
  }

  async function resolveInstallerIsoUrl(ctx) {
    var options = await common.getStoredOptions();
    return common.fillTemplate(options.installerIsoUrl || common.defaultInstallerIsoUrl(), {
      host: window.location.hostname,
      node: ctx && ctx.node || "",
      vmid: ctx && ctx.vmid || ""
    });
  }

  async function resolveControlPlaneHealthUrl() {
    var options = await common.getStoredOptions();
    return common.fillTemplate(options.controlPlaneHealthUrl || common.defaultControlPlaneHealthUrl(), {
      host: window.location.hostname
    });
  }

  async function resolveWebUiUrl() {
    var options = await common.getStoredOptions();
    return common.fillTemplate(options.webUiUrl || common.defaultWebUiUrl(), {
      host: window.location.hostname
    });
  }

  async function resolveBeagleApiUrl(path) {
    var healthUrl = await resolveControlPlaneHealthUrl();
    return common.joinBaseAndPath(common.managerUrlFromHealthUrl(healthUrl), path);
  }

  async function apiGetBeagleJson(path) {
    var url = await resolveBeagleApiUrl(path);
    var response = await fetch(url, {
      credentials: "include",
      headers: await buildBeagleApiHeaders()
    });
    if (!response.ok) {
      throw new Error("Beagle API request failed: " + response.status + " " + response.statusText);
    }
    return response.json();
  }

  function fetchPublicVmState(vmid) {
    return resolveBeagleApiUrl("/api/v1/public/vms/" + encodeURIComponent(String(vmid || "")) + "/state")
      .then(function(url) {
        return fetch(url, { credentials: "same-origin" });
      })
      .then(function(response) {
        return response.ok ? response.json() : null;
      })
      .catch(function() {
        return null;
      });
  }

  function fetchInstallerTargetEligibility(ctx) {
    return fetchPublicVmState(ctx && ctx.vmid)
      .then(function(payload) {
        var profile = payload && payload.profile ? payload.profile : {};
        var roleText = String(profile.beagle_role || "").trim().toLowerCase();
        var fallbackEligible = Boolean(profile.stream_host) && ["endpoint", "thinclient", "client"].indexOf(roleText) === -1;
        return {
          eligible: typeof profile.installer_target_eligible === "boolean" ? profile.installer_target_eligible : fallbackEligible,
          message: profile.installer_target_message || (fallbackEligible ? "" : "Diese VM wird nicht als Streaming-Ziel angeboten.")
        };
      })
      .catch(function() {
        return { eligible: false, message: "" };
      });
  }

  async function fetchInstallerPreparation(vmid) {
    return unwrapInstallerPrep(await apiGetBeagleJson("/api/v1/vms/" + encodeURIComponent(String(vmid || "")) + "/installer-prep"));
  }

  async function prepareInstallerTarget(vmid) {
    var url = await resolveBeagleApiUrl("/api/v1/vms/" + encodeURIComponent(String(vmid || "")) + "/installer-prep");
    var response = await fetch(url, {
      credentials: "include",
      headers: await buildBeagleApiHeaders(),
      method: "POST"
    });
    if (!response.ok) {
      throw new Error("Beagle API request failed: " + response.status + " " + response.statusText);
    }
    return unwrapInstallerPrep(await response.json());
  }

  async function createSunshineAccess(vmid) {
    var url = await resolveBeagleApiUrl("/api/v1/vms/" + encodeURIComponent(String(vmid || "")) + "/sunshine-access");
    var response = await fetch(url, {
      credentials: "include",
      headers: await buildBeagleApiHeaders(),
      method: "POST"
    });
    var payload = null;
    if (!response.ok) {
      throw new Error("Beagle API request failed: " + response.status + " " + response.statusText);
    }
    payload = await response.json();
    return payload && payload.sunshine_access ? payload.sunshine_access : payload;
  }

  async function webUiUrlWithToken(interactive) {
    var config = await getBeagleUiConfig();
    var token = await getApiToken(Boolean(interactive));
    var target = config.webUiUrl || await resolveWebUiUrl();

    if (!token) {
      return target;
    }
    return common.appendHashToken(target, token);
  }

  async function downloadUrl(url) {
    var absoluteUrl = null;
    var response = null;
    var blob = null;
    var objectUrl = null;
    var anchor = null;
    var vmid = null;
    var suffix = null;

    if (!url) {
      throw new Error("Download-URL konnte nicht ermittelt werden.");
    }
    absoluteUrl = common.withNoCache(url);
    if (/\/beagle-api\/|\/api\/v1\/vms\/.+\/installer\.(?:sh|ps1)(?:\?|$)/.test(absoluteUrl)) {
      response = await fetch(absoluteUrl, {
        credentials: "include",
        headers: await buildBeagleApiHeaders()
      });
      if (!response.ok) {
        throw new Error("Beagle API request failed: " + response.status + " " + response.statusText);
      }
      blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      anchor = document.createElement("a");
      anchor.href = objectUrl;
      vmid = String(url).match(/\/vms\/(\d+)\//);
      suffix = /installer\.ps1(?:\?|$)/.test(absoluteUrl) ? ".ps1" : ".sh";
      anchor.download = "pve-thin-client-usb-installer-vm-" + String(vmid && vmid[1] || "download") + suffix;
      anchor.rel = "noopener noreferrer";
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(function() {
        URL.revokeObjectURL(objectUrl);
      }, 1000);
      return;
    }

    anchor = document.createElement("a");
    anchor.href = absoluteUrl;
    anchor.rel = "noopener noreferrer";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  window.BeagleExtensionPlatformService = {
    apiGetBeagleJson: apiGetBeagleJson,
    buildBeagleApiHeaders: buildBeagleApiHeaders,
    createSunshineAccess: createSunshineAccess,
    downloadUrl: downloadUrl,
    fetchInstallerPreparation: fetchInstallerPreparation,
    fetchInstallerTargetEligibility: fetchInstallerTargetEligibility,
    fetchPublicVmState: fetchPublicVmState,
    getApiToken: getApiToken,
    getBeagleUiConfig: getBeagleUiConfig,
    prepareInstallerTarget: prepareInstallerTarget,
    resolveBeagleApiUrl: resolveBeagleApiUrl,
    resolveControlPlaneHealthUrl: resolveControlPlaneHealthUrl,
    resolveInstallerIsoUrl: resolveInstallerIsoUrl,
    resolveUsbInstallerUrl: resolveUsbInstallerUrl,
    resolveWebUiUrl: resolveWebUiUrl,
    webUiUrlWithToken: webUiUrlWithToken
  };
})();

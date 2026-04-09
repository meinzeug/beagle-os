(function() {
  "use strict";

  var API_TOKEN_STORAGE_KEY = "beagle.proxmoxUi.apiToken";
  var apiTokenStorage = null;

  try {
    apiTokenStorage = window.sessionStorage;
  } catch (error) {
    apiTokenStorage = null;
  }

  function defaultUsbInstallerUrl() {
    return "https://{host}:8443/beagle-api/api/v1/vms/{vmid}/installer.sh";
  }

  function defaultInstallerIsoUrl() {
    return "https://{host}:8443/beagle-downloads/beagle-os-installer-amd64.iso";
  }

  function defaultControlPlaneHealthUrl() {
    return "https://{host}:8443/beagle-api/api/v1/health";
  }

  function defaultWebUiUrl() {
    return "https://{host}";
  }

  function getConfig() {
    var runtimeConfig = window.BeagleIntegrationConfig || {};
    return {
      usbInstallerUrl: runtimeConfig.usbInstallerUrl || defaultUsbInstallerUrl(),
      installerIsoUrl: runtimeConfig.installerIsoUrl || defaultInstallerIsoUrl(),
      controlPlaneHealthUrl: runtimeConfig.controlPlaneHealthUrl || defaultControlPlaneHealthUrl(),
      webUiUrl: runtimeConfig.webUiUrl || defaultWebUiUrl(),
      apiToken: runtimeConfig.apiToken || ""
    };
  }

  function readStoredApiToken() {
    if (!apiTokenStorage) {
      return "";
    }
    try {
      return String(apiTokenStorage.getItem(API_TOKEN_STORAGE_KEY) || "").trim();
    } catch (error) {
      return "";
    }
  }

  function writeStoredApiToken(token) {
    if (!apiTokenStorage) {
      return;
    }
    try {
      apiTokenStorage.setItem(API_TOKEN_STORAGE_KEY, String(token || "").trim());
    } catch (error) {
      /* ignore storage failures */
    }
  }

  function clearStoredApiToken() {
    if (!apiTokenStorage) {
      return;
    }
    try {
      apiTokenStorage.removeItem(API_TOKEN_STORAGE_KEY);
    } catch (error) {
      /* ignore storage failures */
    }
  }

  function configuredApiToken() {
    return String(getConfig().apiToken || "").trim();
  }

  function promptForApiToken() {
    var initialValue = readStoredApiToken() || configuredApiToken();
    var token = window.prompt("Beagle API Token fuer diese Browser-Sitzung eingeben. Leerer Wert loescht den Session-Token.", initialValue);
    if (token == null) {
      return "";
    }
    token = String(token || "").trim();
    if (!token) {
      clearStoredApiToken();
      return "";
    }
    writeStoredApiToken(token);
    return token;
  }

  function fillTemplate(template, values) {
    return String(template || "")
      .replaceAll("{node}", values.node || "")
      .replaceAll("{vmid}", String(values.vmid || ""))
      .replaceAll("{host}", values.host || "");
  }

  function resolveUsbInstallerUrl(ctx) {
    return fillTemplate(getConfig().usbInstallerUrl, {
      node: ctx && ctx.node,
      vmid: ctx && ctx.vmid,
      host: window.location.hostname
    });
  }

  function resolveInstallerIsoUrl(ctx) {
    return fillTemplate(getConfig().installerIsoUrl, {
      node: ctx && ctx.node,
      vmid: ctx && ctx.vmid,
      host: window.location.hostname
    });
  }

  function withNoCache(url) {
    if (!url) {
      return url;
    }
    try {
      var parsed = new URL(url, window.location.origin);
      parsed.searchParams.set("_beagle_ts", String(Date.now()));
      return parsed.toString();
    } catch (error) {
      var separator = String(url).indexOf("?") === -1 ? "?" : "&";
      return String(url) + separator + "_beagle_ts=" + Date.now();
    }
  }

  function resolveControlPlaneHealthUrl() {
    return fillTemplate(getConfig().controlPlaneHealthUrl, {
      host: window.location.hostname
    });
  }

  function resolveWebUiUrl() {
    return fillTemplate(getConfig().webUiUrl, {
      host: window.location.hostname
    });
  }

  function managerUrlFromHealthUrl(healthUrl) {
    return String(healthUrl || "").replace(/\/api\/v1\/health\/?$/, "");
  }

  function normalizeBeagleApiPath(path) {
    var value = String(path || "").trim() || "/";
    if (value.indexOf("/beagle-api/") === 0) {
      return value.slice("/beagle-api".length);
    }
    return value;
  }

  function resolveBeagleApiUrl(path) {
    var base = managerUrlFromHealthUrl(resolveControlPlaneHealthUrl());
    var normalizedPath = normalizeBeagleApiPath(path);
    if (!base) {
      return normalizedPath;
    }
    if (normalizedPath.indexOf("/") !== 0) {
      normalizedPath = "/" + normalizedPath;
    }
    return String(base).replace(/\/$/, "") + normalizedPath;
  }

  window.BeagleUiCommon = {
    getConfig: getConfig,
    readStoredApiToken: readStoredApiToken,
    writeStoredApiToken: writeStoredApiToken,
    clearStoredApiToken: clearStoredApiToken,
    configuredApiToken: configuredApiToken,
    promptForApiToken: promptForApiToken,
    fillTemplate: fillTemplate,
    resolveUsbInstallerUrl: resolveUsbInstallerUrl,
    resolveInstallerIsoUrl: resolveInstallerIsoUrl,
    withNoCache: withNoCache,
    resolveControlPlaneHealthUrl: resolveControlPlaneHealthUrl,
    resolveWebUiUrl: resolveWebUiUrl,
    managerUrlFromHealthUrl: managerUrlFromHealthUrl,
    normalizeBeagleApiPath: normalizeBeagleApiPath,
    resolveBeagleApiUrl: resolveBeagleApiUrl
  };
})();

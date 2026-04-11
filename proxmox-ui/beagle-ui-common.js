(function() {
  "use strict";

  var API_TOKEN_STORAGE_KEY = "beagle.proxmoxUi.apiToken";
  var browserCommon = window.BeagleBrowserCommon;
  var apiTokenStore = null;

  if (!browserCommon) {
    throw new Error("BeagleBrowserCommon must be loaded before BeagleUiCommon");
  }
  apiTokenStore = browserCommon.createSessionTokenStore(API_TOKEN_STORAGE_KEY);

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
    return apiTokenStore.read();
  }

  function writeStoredApiToken(token) {
    apiTokenStore.write(token);
  }

  function clearStoredApiToken() {
    apiTokenStore.clear();
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
    return browserCommon.fillTemplate(template, values);
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
    return browserCommon.withNoCache(url);
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
    return browserCommon.managerUrlFromHealthUrl(healthUrl);
  }

  function normalizeBeagleApiPath(path) {
    return browserCommon.normalizeBeagleApiPath(path);
  }

  function resolveBeagleApiUrl(path) {
    return browserCommon.joinBaseAndPath(managerUrlFromHealthUrl(resolveControlPlaneHealthUrl()), path);
  }

  function appendHashToken(url, token) {
    return browserCommon.appendHashToken(url, token, "beagle_token");
  }

  window.BeagleUiCommon = {
    appendHashToken: appendHashToken,
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

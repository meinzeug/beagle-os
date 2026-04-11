(function() {
  "use strict";

  var API_TOKEN_STORAGE_KEY = "beagle.proxmoxUi.apiToken";
  var browserCommon = window.BeagleBrowserCommon;

  if (!browserCommon) {
    throw new Error("BeagleBrowserCommon must be loaded before BeagleExtensionCommon");
  }

  function defaultUsbInstallerUrl() {
    return "https://{host}:8443/beagle-api/api/v1/vms/{vmid}/installer.sh";
  }

  function defaultPublicUsbInstallerUrl() {
    return "https://{host}:8443/beagle-api/api/v1/public/vms/{vmid}/installer.sh";
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

  function buildDefaultOptions(overrides) {
    return Object.assign(
      {
        usbInstallerUrl: defaultUsbInstallerUrl(),
        installerIsoUrl: defaultInstallerIsoUrl(),
        controlPlaneHealthUrl: defaultControlPlaneHealthUrl(),
        webUiUrl: defaultWebUiUrl()
      },
      overrides || {}
    );
  }

  function getStoredOptions(overrides) {
    var defaults = buildDefaultOptions(overrides);
    return new Promise(function(resolve) {
      chrome.storage.sync.get(defaults, function(data) {
        resolve(Object.assign({}, defaults, data || {}));
      });
    });
  }

  function saveOptions(values) {
    return new Promise(function(resolve) {
      chrome.storage.sync.set(values || {}, resolve);
    });
  }

  function fillTemplate(template, values) {
    return browserCommon.fillTemplate(template, values);
  }

  function withNoCache(url) {
    return browserCommon.withNoCache(url);
  }

  function sleep(ms) {
    return new Promise(function(resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function decodeHash() {
    try {
      return decodeURIComponent(window.location.hash || "");
    } catch (_error) {
      return window.location.hash || "";
    }
  }

  function managerUrlFromHealthUrl(healthUrl) {
    return browserCommon.managerUrlFromHealthUrl(healthUrl);
  }

  function normalizeBeagleApiPath(path) {
    return browserCommon.normalizeBeagleApiPath(path);
  }

  function joinBaseAndPath(base, path) {
    return browserCommon.joinBaseAndPath(base, path);
  }

  function tokenStore() {
    return browserCommon.createSessionTokenStore(API_TOKEN_STORAGE_KEY);
  }

  function readStoredApiToken() {
    return tokenStore().read();
  }

  function writeStoredApiToken(token) {
    tokenStore().write(token);
  }

  function clearStoredApiToken() {
    tokenStore().clear();
  }

  function appendHashToken(url, token) {
    return browserCommon.appendHashToken(url, token, "beagle_token");
  }

  function promptForApiToken(initialValue) {
    var token = window.prompt(
      "Beagle API Token fuer diese Browser-Sitzung eingeben. Leerer Wert loescht den Session-Token.",
      initialValue || ""
    );
    if (token == null) {
      return "";
    }
    var trimmed = String(token || "").trim();
    if (!trimmed) {
      clearStoredApiToken();
      return "";
    }
    writeStoredApiToken(trimmed);
    return trimmed;
  }

  window.BeagleExtensionCommon = {
    API_TOKEN_STORAGE_KEY: API_TOKEN_STORAGE_KEY,
    buildDefaultOptions: buildDefaultOptions,
    clearStoredApiToken: clearStoredApiToken,
    decodeHash: decodeHash,
    defaultControlPlaneHealthUrl: defaultControlPlaneHealthUrl,
    defaultInstallerIsoUrl: defaultInstallerIsoUrl,
    defaultPublicUsbInstallerUrl: defaultPublicUsbInstallerUrl,
    defaultUsbInstallerUrl: defaultUsbInstallerUrl,
    defaultWebUiUrl: defaultWebUiUrl,
    fillTemplate: fillTemplate,
    getStoredOptions: getStoredOptions,
    joinBaseAndPath: joinBaseAndPath,
    managerUrlFromHealthUrl: managerUrlFromHealthUrl,
    normalizeBeagleApiPath: normalizeBeagleApiPath,
    appendHashToken: appendHashToken,
    promptForApiToken: promptForApiToken,
    readStoredApiToken: readStoredApiToken,
    saveOptions: saveOptions,
    sleep: sleep,
    withNoCache: withNoCache,
    writeStoredApiToken: writeStoredApiToken
  };
})();

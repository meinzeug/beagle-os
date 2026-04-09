(function() {
  "use strict";

  var API_TOKEN_STORAGE_KEY = "beagle.proxmoxUi.apiToken";

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
    return String(template || "")
      .replaceAll("{node}", values && values.node || "")
      .replaceAll("{vmid}", String(values && values.vmid || ""))
      .replaceAll("{host}", values && values.host || "");
  }

  function withNoCache(url) {
    if (!url) {
      return url;
    }
    try {
      var parsed = new URL(url, window.location.origin);
      parsed.searchParams.set("_beagle_ts", String(Date.now()));
      return parsed.toString();
    } catch (_error) {
      var separator = String(url).indexOf("?") >= 0 ? "&" : "?";
      return String(url) + separator + "_beagle_ts=" + String(Date.now());
    }
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
    return String(healthUrl || "").replace(/\/api\/v1\/health\/?$/, "");
  }

  function normalizeBeagleApiPath(path) {
    var value = String(path || "").trim() || "/";
    return value.indexOf("/beagle-api/") === 0 ? value.slice("/beagle-api".length) : value;
  }

  function tokenStorage() {
    try {
      return window.sessionStorage;
    } catch (_error) {
      return null;
    }
  }

  function readStoredApiToken() {
    var storage = tokenStorage();
    if (!storage) {
      return "";
    }
    try {
      return String(storage.getItem(API_TOKEN_STORAGE_KEY) || "").trim();
    } catch (_error) {
      return "";
    }
  }

  function writeStoredApiToken(token) {
    var storage = tokenStorage();
    if (!storage) {
      return;
    }
    try {
      storage.setItem(API_TOKEN_STORAGE_KEY, String(token || "").trim());
    } catch (_error) {
      // ignore storage failures
    }
  }

  function clearStoredApiToken() {
    var storage = tokenStorage();
    if (!storage) {
      return;
    }
    try {
      storage.removeItem(API_TOKEN_STORAGE_KEY);
    } catch (_error) {
      // ignore storage failures
    }
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
    managerUrlFromHealthUrl: managerUrlFromHealthUrl,
    normalizeBeagleApiPath: normalizeBeagleApiPath,
    promptForApiToken: promptForApiToken,
    readStoredApiToken: readStoredApiToken,
    saveOptions: saveOptions,
    sleep: sleep,
    withNoCache: withNoCache,
    writeStoredApiToken: writeStoredApiToken
  };
})();

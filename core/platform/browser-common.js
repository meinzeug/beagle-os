(function() {
  "use strict";

  function sessionStorageOrNull() {
    try {
      return window.sessionStorage;
    } catch (_error) {
      return null;
    }
  }

  function createSessionTokenStore(storageKey) {
    var key = String(storageKey || "").trim();

    function read() {
      var storage = sessionStorageOrNull();
      if (!storage || !key) {
        return "";
      }
      try {
        return String(storage.getItem(key) || "").trim();
      } catch (_error) {
        return "";
      }
    }

    function write(token) {
      var storage = sessionStorageOrNull();
      if (!storage || !key) {
        return;
      }
      try {
        storage.setItem(key, String(token || "").trim());
      } catch (_error) {
        /* ignore storage failures */
      }
    }

    function clear() {
      var storage = sessionStorageOrNull();
      if (!storage || !key) {
        return;
      }
      try {
        storage.removeItem(key);
      } catch (_error) {
        /* ignore storage failures */
      }
    }

    return {
      read: read,
      write: write,
      clear: clear
    };
  }

  function fillTemplate(template, values) {
    var data = values || {};
    return String(template || "")
      .replaceAll("{node}", data.node || "")
      .replaceAll("{vmid}", String(data.vmid || ""))
      .replaceAll("{host}", data.host || "");
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

  function managerUrlFromHealthUrl(healthUrl) {
    return String(healthUrl || "").replace(/\/api\/v1\/health\/?$/, "");
  }

  function normalizeBeagleApiPath(path) {
    var value = String(path || "").trim() || "/";
    return value.indexOf("/beagle-api/") === 0 ? value.slice("/beagle-api".length) : value;
  }

  function joinBaseAndPath(base, path) {
    var baseText = String(base || "").trim();
    var normalizedPath = normalizeBeagleApiPath(path);
    if (!baseText) {
      return normalizedPath;
    }
    if (normalizedPath.charAt(0) !== "/") {
      normalizedPath = "/" + normalizedPath;
    }
    return baseText.replace(/\/$/, "") + normalizedPath;
  }

  function appendHashToken(url, token, hashKey) {
    var cleanToken = String(token || "").trim();
    var target = String(url || "").trim();
    var key = String(hashKey || "beagle_token").trim() || "beagle_token";
    if (!cleanToken) {
      return target;
    }
    try {
      var parsed = new URL(target, window.location.origin);
      parsed.hash = key + "=" + encodeURIComponent(cleanToken);
      return parsed.toString();
    } catch (_error) {
      return target + "#" + key + "=" + encodeURIComponent(cleanToken);
    }
  }

  window.BeagleBrowserCommon = {
    appendHashToken: appendHashToken,
    createSessionTokenStore: createSessionTokenStore,
    fillTemplate: fillTemplate,
    joinBaseAndPath: joinBaseAndPath,
    managerUrlFromHealthUrl: managerUrlFromHealthUrl,
    normalizeBeagleApiPath: normalizeBeagleApiPath,
    withNoCache: withNoCache
  };
})();

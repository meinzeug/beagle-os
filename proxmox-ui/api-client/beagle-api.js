(function() {
  "use strict";

  var common = window.BeagleUiCommon;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before BeagleUiApiClient");
  }

  function apiGetJson(path) {
    return fetch(path, { credentials: "same-origin" }).then(function(response) {
      if (!response.ok) {
        throw new Error("API request failed: " + response.status + " " + response.statusText);
      }
      return response.json();
    }).then(function(payload) {
      return payload && payload.data ? payload.data : payload;
    });
  }

  function getApiToken(interactive) {
    var token = common.readStoredApiToken() || common.configuredApiToken();
    if (token || !interactive) {
      return token;
    }
    return common.promptForApiToken();
  }

  function buildBeagleRequestHeaders(extraHeaders, interactive) {
    var headers = Object.assign({}, extraHeaders || {});
    var token = getApiToken(Boolean(interactive));
    if (token) {
      headers.Authorization = "Bearer " + token;
    }
    return headers;
  }

  function apiBeagleJson(path, options) {
    return fetch(common.resolveBeagleApiUrl(path), Object.assign({ credentials: "same-origin" }, options || {})).then(function(response) {
      if (!response.ok) {
        throw new Error("Beagle API request failed: " + response.status + " " + response.statusText);
      }
      return response.json();
    });
  }

  function apiGetBeagleJson(path) {
    return apiBeagleJson(path, { headers: buildBeagleRequestHeaders({}, true) });
  }

  function apiPostBeagleJson(path, payload) {
    return apiBeagleJson(path, {
      method: "POST",
      headers: buildBeagleRequestHeaders({ "Content-Type": "application/json" }, true),
      body: JSON.stringify(payload || {})
    });
  }

  function apiPutBeagleJson(path, payload) {
    return apiBeagleJson(path, {
      method: "PUT",
      headers: buildBeagleRequestHeaders({ "Content-Type": "application/json" }, true),
      body: JSON.stringify(payload || {})
    });
  }

  function apiDeleteBeagle(path) {
    return apiBeagleJson(path, {
      method: "DELETE",
      headers: buildBeagleRequestHeaders({}, true)
    });
  }

  function downloadProtectedFile(path, filename) {
    return fetch(common.resolveBeagleApiUrl(path), {
      credentials: "same-origin",
      headers: buildBeagleRequestHeaders({}, true)
    }).then(function(response) {
      if (!response.ok) {
        throw new Error("Download failed: " + response.status + " " + response.statusText);
      }
      return response.blob();
    }).then(function(blob) {
      var objectUrl = URL.createObjectURL(blob);
      var anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename || "beagle-artifact.bin";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(function() {
        URL.revokeObjectURL(objectUrl);
      }, 1000);
    });
  }

  window.BeagleUiApiClient = {
    apiGetJson: apiGetJson,
    getApiToken: getApiToken,
    buildBeagleRequestHeaders: buildBeagleRequestHeaders,
    apiBeagleJson: apiBeagleJson,
    apiGetBeagleJson: apiGetBeagleJson,
    apiPostBeagleJson: apiPostBeagleJson,
    apiPutBeagleJson: apiPutBeagleJson,
    apiDeleteBeagle: apiDeleteBeagle,
    downloadProtectedFile: downloadProtectedFile
  };
})();

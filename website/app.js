(function () {
  "use strict";

  function setText(id, value) {
    var element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    });
  }

  function fetchControlPlaneStatus() {
    return fetchJson("/beagle-api/healthz")
      .then(function (payload) {
        if (!payload || !payload.ok) {
          throw new Error("healthz unavailable");
        }

        setText("health-state", "Operational");
        setText("health-meta", "Control plane version " + String(payload.version || "unknown"));

        return fetchJson("/beagle-api/api/v1/health")
          .then(function (details) {
            setText(
              "health-meta",
              "Endpoints: " +
                String(details && details.endpoint_count ? details.endpoint_count : 0) +
                " | Policies: " +
                String(details && details.policy_count ? details.policy_count : 0)
            );
          })
          .catch(function () {
            return null;
          });
      })
      .catch(function () {
        setText("health-state", "Offline");
        setText("health-meta", "Control plane unavailable");
      });
  }

  fetchJson("/beagle-downloads/beagle-downloads-status.json")
    .then(function (payload) {
      var version = payload && payload.version ? "v" + payload.version : "Unavailable";
      var generated = payload && payload.generated_at ? payload.generated_at : "Host metadata online";
      setText("release-version", version);
      setText("release-updated", generated);
    })
    .catch(function () {
      setText("release-version", "Unavailable");
      setText("release-updated", "Host metadata unavailable");
    });

  fetchControlPlaneStatus();
})();

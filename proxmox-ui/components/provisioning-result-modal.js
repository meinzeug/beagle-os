(function() {
  "use strict";

  var renderHelpers = window.BeagleUiRenderHelpers;

  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before BeagleUiProvisioningResultModal");
  }

  function provisioningStatusLabel(state) {
    var status = String(state && state.status || "unknown").toLowerCase();
    switch (status) {
      case "creating":
        return "Proxmox legt die VM an";
      case "created":
        return "VM angelegt, wartet auf Start";
      case "installing":
        return "Ubuntu Autoinstall laeuft";
      case "completed":
        return "Provisionierung abgeschlossen";
      case "failed":
        return "Provisionierung fehlgeschlagen";
      default:
        return status || "unknown";
    }
  }

  function provisioningStatusBadgeClass(state) {
    var status = String(state && state.status || "pending").toLowerCase();
    if (status === "completed") {
      return "healthy";
    }
    if (status === "failed") {
      return "drifted";
    }
    if (status === "created") {
      return "degraded";
    }
    return "pending";
  }

  function renderProvisioningBadge(state) {
    return '<span class="beagle-badge ' + provisioningStatusBadgeClass(state) + '">' + renderHelpers.escapeHtml(provisioningStatusLabel(state)) + '</span>';
  }

  function buildProvisioningCredentialText(created, state) {
    var credentials = state && state.credentials ? state.credentials : {};
    var publicStream = created && created.public_stream ? created.public_stream : state && state.public_stream ? state.public_stream : {};
    return [
      "VMID: " + String(created && created.vmid || ""),
      "Node: " + String(created && created.node || ""),
      "VM Name: " + String(created && created.name || ""),
      "Hostname: " + String(created && created.hostname || ""),
      "Guest User: " + String(credentials.guest_user || created && created.guest_user || ""),
      "Guest Passwort: " + String(credentials.guest_password || created && created.guest_password || ""),
      "Sunshine User: " + String(credentials.sunshine_user || created && created.sunshine_user || ""),
      "Sunshine Passwort: " + String(credentials.sunshine_password || created && created.sunshine_password || ""),
      "Stream Host: " + String(publicStream.host || ""),
      "Moonlight Port: " + String(publicStream.moonlight_port || "")
    ].join("\n");
  }

  function renderProvisioningResultHtml(created, state) {
    var currentState = state || created && created.provisioning || {};
    var credentials = currentState && currentState.credentials ? currentState.credentials : {};
    var publicStream = created && created.public_stream ? created.public_stream : currentState && currentState.public_stream ? currentState.public_stream : {};
    var badgeClass = provisioningStatusBadgeClass(currentState);
    var escapeHtml = renderHelpers.escapeHtml;
    var kvRow = renderHelpers.kvRow;
    return '' +
      '<div class="beagle-body" style="padding:0; gap:16px;">' +
      '  <div class="beagle-banner ' + (badgeClass === "drifted" ? "warn" : "info") + '">' +
      '    <strong>' + escapeHtml(provisioningStatusLabel(currentState)) + '</strong><br>' +
      '    <span>' + escapeHtml(String(currentState && currentState.message || "Die Provisionierung wird vom Beagle Control Plane verwaltet.")) + '</span>' +
      '  </div>' +
      '  <div class="beagle-grid">' +
      '    <section class="beagle-card"><h3>VM</h3><div class="beagle-kv">' +
            kvRow('VMID', escapeHtml(String(created && created.vmid || ""))) +
            kvRow('Node', escapeHtml(String(created && created.node || ""))) +
            kvRow('VM Name', escapeHtml(String(created && created.name || ""))) +
            kvRow('Hostname', escapeHtml(String(created && created.hostname || ""))) +
            kvRow('OS Profil', escapeHtml(String(created && created.os_profile || ""))) +
      '    </div></section>' +
      '    <section class="beagle-card"><h3>Provisioning</h3><div class="beagle-kv">' +
            kvRow('Status', '<span class="beagle-badge ' + badgeClass + '">' + escapeHtml(provisioningStatusLabel(currentState)) + '</span>') +
            kvRow('Phase', escapeHtml(String(currentState && currentState.phase || ""))) +
            kvRow('Angelegt', escapeHtml(String(currentState && currentState.created_at || ""))) +
            kvRow('Aktualisiert', escapeHtml(String(currentState && currentState.updated_at || ""))) +
            kvRow('Abgeschlossen', escapeHtml(String(currentState && currentState.completed_at || ""))) +
      '    </div></section>' +
      '    <section class="beagle-card"><h3>Zugang</h3><div class="beagle-kv">' +
            kvRow('Ubuntu User', escapeHtml(String(credentials.guest_user || created && created.guest_user || ""))) +
            kvRow('Ubuntu Passwort', escapeHtml(String(credentials.guest_password || created && created.guest_password || ""))) +
            kvRow('Sunshine User', escapeHtml(String(credentials.sunshine_user || created && created.sunshine_user || ""))) +
            kvRow('Sunshine Passwort', escapeHtml(String(credentials.sunshine_password || created && created.sunshine_password || ""))) +
      '    </div></section>' +
      '    <section class="beagle-card"><h3>Streaming</h3><div class="beagle-kv">' +
            kvRow('Desktop', 'XFCE') +
            kvRow('Streaming', 'Sunshine') +
            kvRow('Host', escapeHtml(String(publicStream.host || ""))) +
            kvRow('Moonlight Port', escapeHtml(String(publicStream.moonlight_port || ""))) +
            kvRow('Sunshine API', escapeHtml(String(publicStream.sunshine_api_url || ""))) +
      '    </div></section>' +
      '  </div>' +
      (currentState && currentState.error ? ('<div class="beagle-banner warn">' + escapeHtml(String(currentState.error || "")) + '</div>') : '') +
      '</div>';
  }

  function showProvisioningResultWindow(options) {
    var created = options.created;
    var apiGetProvisioningState = options.apiGetProvisioningState;
    var copyText = options.copyText;
    var showProfileModal = options.showProfileModal;
    var latestState = created && created.provisioning ? created.provisioning : {};
    var windowRef = Ext.create("Ext.window.Window", {
      title: "Beagle VM Provisioning",
      modal: true,
      width: 860,
      maxHeight: 760,
      layout: "fit",
      scrollable: true,
      bodyPadding: 18,
      items: [
        {
          xtype: "component",
          itemId: "beagleProvisioningResult",
          html: renderProvisioningResultHtml(created, latestState)
        }
      ],
      buttons: [
        {
          text: "Credentials kopieren",
          handler: function() {
            copyText(buildProvisioningCredentialText(created, latestState), "Provisioning-Credentials kopiert.");
          }
        },
        {
          text: "VM Profil",
          ui: "primary",
          handler: function() {
            showProfileModal({ node: String(created && created.node || ""), vmid: Number(created && created.vmid || 0) });
          }
        },
        {
          text: "Schliessen",
          handler: function() {
            windowRef.close();
          }
        }
      ],
      listeners: {
        show: function() {
          if (!(created && created.vmid)) {
            return;
          }
          windowRef.__beagleProvisioningTimer = window.setInterval(function() {
            apiGetProvisioningState(created.vmid).then(function(state) {
              latestState = state || latestState;
              windowRef.down("#beagleProvisioningResult").update(renderProvisioningResultHtml(created, latestState));
              if (String(latestState && latestState.status || "").toLowerCase() === "completed") {
                window.clearInterval(windowRef.__beagleProvisioningTimer);
                windowRef.__beagleProvisioningTimer = null;
              }
            }).catch(function() {
              /* ignore transient provisioning poll errors */
            });
          }, 5000);
        },
        destroy: function() {
          if (windowRef.__beagleProvisioningTimer) {
            window.clearInterval(windowRef.__beagleProvisioningTimer);
            windowRef.__beagleProvisioningTimer = null;
          }
        }
      }
    });
    windowRef.show();
  }

  window.BeagleUiProvisioningResultModal = {
    provisioningStatusLabel: provisioningStatusLabel,
    provisioningStatusBadgeClass: provisioningStatusBadgeClass,
    renderProvisioningBadge: renderProvisioningBadge,
    buildProvisioningCredentialText: buildProvisioningCredentialText,
    renderProvisioningResultHtml: renderProvisioningResultHtml,
    showProvisioningResultWindow: showProvisioningResultWindow
  };
})();

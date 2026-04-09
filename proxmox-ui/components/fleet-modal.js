(function() {
  "use strict";

  var renderHelpers = window.BeagleUiRenderHelpers;

  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before BeagleUiFleetModal");
  }

  function createPolicyFromInventoryItem(item) {
    var target = item && item.assigned_target ? item.assigned_target : null;
    if (!target || !target.vmid) {
      throw new Error("Kein zugewiesenes Ziel fuer diese VM vorhanden.");
    }
    return {
      name: "vm-" + String(item.vmid) + "-managed",
      enabled: true,
      priority: 700,
      selector: {
        vmid: Number(item.vmid),
        node: item.node || "",
        role: "endpoint"
      },
      profile: {
        beagle_role: "endpoint",
        expected_profile_name: item.expected_profile_name || ("vm-" + String(target.vmid)),
        network_mode: item.network_mode || "dhcp",
        moonlight_app: item.moonlight_app || "Desktop",
        assigned_target: {
          vmid: Number(target.vmid),
          node: target.node || ""
        }
      }
    };
  }

  function selectedFleetVmids(overlay) {
    return Array.prototype.slice.call(overlay.querySelectorAll(".beagle-row-select[data-vmid]:checked")).map(function(element) {
      return Number(element.getAttribute("data-vmid"));
    }).filter(function(value) {
      return Number.isFinite(value) && value > 0;
    });
  }

  function selectedFleetItems(overlay, vms) {
    var selected = new Set(selectedFleetVmids(overlay));
    return vms.filter(function(item) {
      return selected.has(Number(item.vmid));
    });
  }

  function renderStatusBadge(status) {
    var value = String(status || "unknown").toLowerCase();
    return '<span class="beagle-badge ' + renderHelpers.escapeHtml(value) + '">' + renderHelpers.escapeHtml(value) + '</span>';
  }

  function renderFleetModal(options) {
    var overlayId = options.overlayId;
    var payload = options.payload;
    var removeOverlay = options.removeOverlay;
    var showFleetModal = options.showFleetModal;
    var showUbuntuBeagleCreateModal = options.showUbuntuBeagleCreateModal;
    var selectedNodeName = options.selectedNodeName;
    var resolveControlPlaneHealthUrl = options.resolveControlPlaneHealthUrl;
    var openUrl = options.openUrl;
    var copyText = options.copyText;
    var platformService = options.platformService;
    var apiGetProvisioningState = options.apiGetProvisioningState;
    var showProfileModal = options.showProfileModal;
    var showError = options.showError;
    var showToast = options.showToast;
    var buildProvisioningCredentialText = options.buildProvisioningCredentialText;
    var renderProvisioningBadge = options.renderProvisioningBadge;
    var overlay = document.createElement("div");
    var vms = payload && Array.isArray(payload.vms) ? payload.vms : [];
    var policies = payload && Array.isArray(payload.policies) ? payload.policies : [];
    var health = payload && payload.health ? payload.health : {};
    var catalog = payload && payload.catalog ? payload.catalog : {};
    var defaults = catalog && catalog.defaults ? catalog.defaults : {};
    var requests = Array.isArray(catalog && catalog.recent_requests) ? catalog.recent_requests : [];
    var osProfiles = Array.isArray(catalog && catalog.os_profiles) ? catalog.os_profiles : [];
    var desktopProfiles = Array.isArray(catalog && catalog.desktop_profiles) ? catalog.desktop_profiles : [];
    var softwarePresetCatalog = Array.isArray(catalog && catalog.software_presets) ? catalog.software_presets : [];
    var nodes = Array.isArray(catalog && catalog.nodes) ? catalog.nodes : [];
    var imageStorages = catalog && catalog.storages && Array.isArray(catalog.storages.images) ? catalog.storages.images : [];
    var isoStorages = catalog && catalog.storages && Array.isArray(catalog.storages.iso) ? catalog.storages.iso : [];
    var endpointCounts = health.endpoint_status_counts || {};
    var vmRows = vms.map(function(item) {
      var lastAction = item.last_action || {};
      var provisioning = item.provisioning || null;
      var bundleDownloadPath = lastAction.stored_artifact_download_path || "";
      var policyName = item.applied_policy && item.applied_policy.name || "";
      return '' +
        '<tr>' +
        '  <td class="beagle-select-cell"><input class="beagle-row-select" type="checkbox" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '"></td>' +
        '  <td><strong>' + renderHelpers.escapeHtml(item.name || ("vm-" + item.vmid)) + '</strong><br><span class="beagle-muted">#' + renderHelpers.escapeHtml(String(item.vmid || "")) + ' / ' + renderHelpers.escapeHtml(item.node || "") + '</span></td>' +
        '  <td>' + renderStatusBadge(item.compliance && item.compliance.status || "unknown") + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(item.assignment_source || "unassigned") + '</span></td>' +
        '  <td>' + (provisioning ? renderProvisioningBadge(provisioning) + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(provisioning.phase || "")) + '</span><br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(provisioning.hostname || "")) + '</span>' : '<span class="beagle-muted">kein Provisioning-State</span>') + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(item.assigned_target ? (item.assigned_target.name + " (#" + item.assigned_target.vmid + ")") : "") + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(item.stream_host || "") + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(policyName || "keine") + '<br><span class="beagle-muted">Bundles: ' + renderHelpers.escapeHtml(String(item.support_bundle_count || 0)) + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(item.endpoint && item.endpoint.reported_at || "") + '<br><span class="beagle-muted">Age: ' + renderHelpers.escapeHtml(String(item.endpoint && item.endpoint.report_age_seconds || 0)) + 's</span><br><span class="beagle-muted">' + renderHelpers.escapeHtml(lastAction.action || "") + " " + renderHelpers.escapeHtml(options.formatActionState(lastAction.ok)) + '</span></td>' +
        '  <td><div class="beagle-inline-actions">' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="profile" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '" data-node="' + renderHelpers.escapeHtml(item.node || "") + '">Profil</button>' +
        (String(item.beagle_role || "").toLowerCase() === "desktop" ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="edit-desktop" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '" data-node="' + renderHelpers.escapeHtml(item.node || "") + '">Bearbeiten</button>' : '') +
        (provisioning ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="copy-credentials" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '">Credentials</button>' : '') +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="healthcheck" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '">Check</button>' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="support-bundle" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '">Bundle</button>' +
        (bundleDownloadPath ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="download-bundle" data-bundle-path="' + renderHelpers.escapeHtml(bundleDownloadPath) + '" data-bundle-name="vm-' + renderHelpers.escapeHtml(String(item.vmid || "")) + '-support.tar.gz">Download</button>' : '') +
        (policyName ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="delete-policy" data-policy-name="' + renderHelpers.escapeHtml(policyName) + '">Policy loeschen</button>' : (item.assigned_target ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="create-policy" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '">Zu Policy</button>' : '')) +
        '  </div></td>' +
        '</tr>';
    }).join("");
    var policyRows = policies.map(function(policy) {
      var selector = policy.selector || {};
      var profile = policy.profile || {};
      return '' +
        '<tr>' +
        '  <td><strong>' + renderHelpers.escapeHtml(policy.name || "") + '</strong></td>' +
        '  <td>' + renderHelpers.escapeHtml(String(policy.priority || 0)) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(selector.vmid ? ("VM " + selector.vmid) : "") + ' ' + renderHelpers.escapeHtml(selector.node || "") + ' ' + renderHelpers.escapeHtml(selector.role || "") + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(profile.expected_profile_name || "") + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(profile.network_mode || "") + '</span></td>' +
        '  <td><button type="button" class="beagle-mini-btn" data-beagle-fleet-action="delete-policy" data-policy-name="' + renderHelpers.escapeHtml(policy.name || "") + '">Loeschen</button></td>' +
        '</tr>';
    }).join("");
    var requestRows = requests.slice(0, 10).map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + renderHelpers.escapeHtml(String(item.name || ("vm-" + item.vmid))) + '</strong><br><span class="beagle-muted">#' + renderHelpers.escapeHtml(String(item.vmid || "")) + ' / ' + renderHelpers.escapeHtml(String(item.node || "")) + '</span></td>' +
        '  <td>' + renderProvisioningBadge(item) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.phase || "")) + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(item.message || "")) + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.created_at || "")) + '<br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(item.completed_at || item.updated_at || "")) + '</span></td>' +
        '  <td><div class="beagle-inline-actions">' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="request-profile" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '" data-node="' + renderHelpers.escapeHtml(String(item.node || "")) + '">Profil</button>' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="copy-credentials" data-vmid="' + renderHelpers.escapeHtml(String(item.vmid || "")) + '">Credentials</button>' +
        '  </div></td>' +
        '</tr>';
    }).join("");
    var osProfileRows = osProfiles.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + renderHelpers.escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.release || "")) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.desktop || "")) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.streaming || "")) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(Array.isArray(item.features) ? item.features.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");
    var desktopProfileRows = desktopProfiles.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + renderHelpers.escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.session || "")) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(Array.isArray(item.packages) ? item.packages.join(", ") : "") + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(Array.isArray(item.features) ? item.features.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");
    var softwarePresetRows = softwarePresetCatalog.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + renderHelpers.escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + renderHelpers.escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + renderHelpers.escapeHtml(String(item.description || "")) + '</td>' +
        '  <td>' + renderHelpers.escapeHtml(Array.isArray(item.packages) ? item.packages.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");

    overlay.id = overlayId;
    overlay.innerHTML = '' +
      '<div class="beagle-modal" role="dialog" aria-modal="true" aria-label="Beagle Fleet">' +
      '  <div class="beagle-header">' +
      '    <div><h2 class="beagle-title">Beagle Fleet</h2><p class="beagle-subtitle">Zentrale Provisioning-, Runtime- und Diagnose-Sicht fuer Proxmox.</p></div>' +
      '    <button type="button" class="beagle-close" aria-label="Schliessen">×</button>' +
      '  </div>' +
      '  <div class="beagle-body">' +
      '    <div class="beagle-actions">' +
      '      <button type="button" class="beagle-btn primary" data-beagle-fleet-action="create-vm">Neue Beagle VM</button>' +
      '      <button type="button" class="beagle-btn primary" data-beagle-fleet-action="refresh">Aktualisieren</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-fleet-action="bulk-healthcheck">Bulk Check</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-fleet-action="bulk-support-bundle">Bulk Bundle</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-fleet-action="bulk-create-policy">Bulk Policy</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-fleet-action="open-health">Health</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-fleet-action="copy-policies">Policies JSON</button>' +
      '    </div>' +
      '    <div class="beagle-grid">' +
      '      <section class="beagle-card"><h3>Fleet</h3><div class="beagle-kv">' +
                renderHelpers.kvRow("Endpoints", renderHelpers.escapeHtml(String(health.endpoint_count || 0))) +
                renderHelpers.kvRow("Policies", renderHelpers.escapeHtml(String(health.policy_count || 0))) +
                renderHelpers.kvRow("Healthy", renderHelpers.escapeHtml(String(endpointCounts.healthy || 0))) +
                renderHelpers.kvRow("Pending", renderHelpers.escapeHtml(String(endpointCounts.pending || 0))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Compliance</h3><div class="beagle-kv">' +
                renderHelpers.kvRow("Stale", renderHelpers.escapeHtml(String(endpointCounts.stale || 0))) +
                renderHelpers.kvRow("Degraded", renderHelpers.escapeHtml(String(endpointCounts.degraded || 0))) +
                renderHelpers.kvRow("Drifted", renderHelpers.escapeHtml(String(endpointCounts.drifted || 0))) +
                renderHelpers.kvRow("Unmanaged", renderHelpers.escapeHtml(String(endpointCounts.unmanaged || 0))) +
                renderHelpers.kvRow("Generated", renderHelpers.escapeHtml(health.generated_at || "")) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Provisioning</h3><div class="beagle-kv">' +
                renderHelpers.kvRow("Next VMID", renderHelpers.escapeHtml(String(defaults.next_vmid || ""))) +
                renderHelpers.kvRow("Default Node", renderHelpers.escapeHtml(String(defaults.node || ""))) +
                renderHelpers.kvRow("Bridge", renderHelpers.escapeHtml(String(defaults.bridge || ""))) +
                renderHelpers.kvRow("Disk Storage", renderHelpers.escapeHtml(String(defaults.disk_storage || ""))) +
                renderHelpers.kvRow("ISO Storage", renderHelpers.escapeHtml(String(defaults.iso_storage || ""))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Katalog</h3><div class="beagle-kv">' +
                renderHelpers.kvRow("OS Profile", renderHelpers.escapeHtml(String(osProfiles.length || 0))) +
                renderHelpers.kvRow("Desktop Profile", renderHelpers.escapeHtml(String(desktopProfiles.length || 0))) +
                renderHelpers.kvRow("Software Presets", renderHelpers.escapeHtml(String(softwarePresetCatalog.length || 0))) +
                renderHelpers.kvRow("Nodes", renderHelpers.escapeHtml(String(nodes.length || 0))) +
                renderHelpers.kvRow("Image Storages", renderHelpers.escapeHtml(String(imageStorages.length || 0))) +
                renderHelpers.kvRow("ISO Storages", renderHelpers.escapeHtml(String(isoStorages.length || 0))) +
      '      </div></section>' +
      '    </div>' +
      '    <section class="beagle-card"><h3>Provisioning Requests</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th>VM</th><th>Status</th><th>Phase</th><th>Zeit</th><th>Aktionen</th></tr></thead><tbody>' + (requestRows || '<tr><td colspan="5" class="beagle-muted">Noch keine Provisioning-Anfragen vorhanden.</td></tr>') + '</tbody></table></div></section>' +
      '    <section class="beagle-card"><h3>OS Katalog</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th>Profil</th><th>Release</th><th>Desktop</th><th>Streaming</th><th>Features</th></tr></thead><tbody>' + (osProfileRows || '<tr><td colspan="5" class="beagle-muted">Kein Katalog verfuegbar.</td></tr>') + '</tbody></table></div></section>' +
      '    <section class="beagle-card"><h3>Desktop Katalog</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th>Desktop</th><th>Session</th><th>APT Pakete</th><th>Features</th></tr></thead><tbody>' + (desktopProfileRows || '<tr><td colspan="4" class="beagle-muted">Kein Desktop-Katalog verfuegbar.</td></tr>') + '</tbody></table></div></section>' +
      '    <section class="beagle-card"><h3>Software Presets</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th>Preset</th><th>Beschreibung</th><th>APT Pakete</th></tr></thead><tbody>' + (softwarePresetRows || '<tr><td colspan="3" class="beagle-muted">Keine Software-Presets verfuegbar.</td></tr>') + '</tbody></table></div></section>' +
      '    <section class="beagle-card"><h3>Endpoints</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th class="beagle-select-cell"><input class="beagle-row-select" type="checkbox" data-beagle-fleet-action="toggle-all"></th><th>VM</th><th>Status</th><th>Provisioning</th><th>Ziel</th><th>Policy</th><th>Letzter Kontakt</th><th>Aktionen</th></tr></thead><tbody>' + vmRows + '</tbody></table></div></section>' +
      '    <section class="beagle-card"><h3>Policies</h3><div class="beagle-table-wrap"><table class="beagle-table"><thead><tr><th>Name</th><th>Prioritaet</th><th>Selektor</th><th>Profil</th><th>Aktion</th></tr></thead><tbody>' + policyRows + '</tbody></table></div></section>' +
      '  </div>' +
      '</div>';

    overlay.addEventListener("click", function(event) {
      var target;
      var item;
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
        return;
      }
      target = event.target instanceof HTMLElement ? event.target.closest("[data-beagle-fleet-action]") : null;
      if (!target) {
        return;
      }
      switch (target.getAttribute("data-beagle-fleet-action")) {
        case "create-vm":
          removeOverlay();
          showUbuntuBeagleCreateModal({ node: String(defaults.node || selectedNodeName() || "") });
          break;
        case "refresh":
          showFleetModal();
          break;
        case "toggle-all":
          Array.prototype.slice.call(overlay.querySelectorAll(".beagle-row-select[data-vmid]")).forEach(function(checkbox) {
            checkbox.checked = target.checked;
          });
          break;
        case "open-health":
          openUrl(resolveControlPlaneHealthUrl());
          break;
        case "copy-policies":
          copyText(JSON.stringify(policies, null, 2), "Beagle Policies kopiert.");
          break;
        case "bulk-healthcheck":
        case "bulk-support-bundle":
          platformService.queueBulkAction(selectedFleetVmids(overlay), target.getAttribute("data-beagle-fleet-action") === "bulk-healthcheck" ? "healthcheck" : "support-bundle").then(function(result) {
            showToast("Beagle Bulk-Aktion gequeued: " + String(result.queued_count || 0));
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case "bulk-create-policy":
          Promise.all(selectedFleetItems(overlay, vms).map(function(candidate) {
            return platformService.createPolicy(createPolicyFromInventoryItem(candidate));
          })).then(function(result) {
            showToast("Beagle Policies erzeugt: " + String(result.length || 0));
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case "profile":
          showProfileModal({ vmid: Number(target.getAttribute("data-vmid")), node: target.getAttribute("data-node") });
          break;
        case "edit-desktop":
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute("data-vmid")); });
          removeOverlay();
          showUbuntuBeagleCreateModal({ profile: item || { vmid: Number(target.getAttribute("data-vmid")), node: target.getAttribute("data-node") }, node: target.getAttribute("data-node") });
          break;
        case "request-profile":
          showProfileModal({ vmid: Number(target.getAttribute("data-vmid")), node: target.getAttribute("data-node") });
          break;
        case "copy-credentials":
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute("data-vmid")); }) ||
            requests.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute("data-vmid")); });
          apiGetProvisioningState(target.getAttribute("data-vmid")).then(function(state) {
            copyText(buildProvisioningCredentialText(item || {}, state || {}), "Provisioning-Credentials kopiert.");
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case "healthcheck":
        case "support-bundle":
          platformService.queueVmAction(target.getAttribute("data-vmid"), target.getAttribute("data-beagle-fleet-action")).then(function() {
            showToast("Beagle Aktion wurde in die Queue gestellt.");
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case "download-bundle":
          options.downloadProtectedFile("/beagle-api" + target.getAttribute("data-bundle-path"), target.getAttribute("data-bundle-name")).catch(function(error) {
            showError(error.message);
          });
          break;
        case "create-policy":
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute("data-vmid")); });
          platformService.createPolicy(createPolicyFromInventoryItem(item)).then(function() {
            showToast("Beagle Policy wurde erzeugt.");
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case "delete-policy":
          platformService.deletePolicy(target.getAttribute("data-policy-name")).then(function() {
            showToast("Beagle Policy wurde geloescht.");
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        default:
          break;
      }
    });

    document.body.appendChild(overlay);
  }

  window.BeagleUiFleetModal = {
    renderFleetModal: renderFleetModal
  };
})();

(function() {
  "use strict";

  var PRODUCT_LABEL = "Beagle OS";
  var STYLE_ID = "beagle-os-modal-style";
  var OVERLAY_ID = "beagle-os-overlay";
  var FLEET_LAUNCHER_ID = "beagle-os-fleet-launcher";
  var CREATE_VM_DOM_BUTTON_ID = "beagle-os-create-vm-dom-button";
  var common = window.BeagleUiCommon;
  var virtualizationService = window.BeagleVirtualizationService;
  var platformService = window.BeaglePlatformService;
  var apiClient = window.BeagleUiApiClient;
  var beagleState = window.BeagleUiState;
  var usbUi = window.BeagleUiUsbUi;
  var renderHelpers = window.BeagleUiRenderHelpers;
  var desktopOverlay = window.BeagleUiDesktopOverlay;
  var browserActions = window.BeagleUiBrowserActions;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before beagle-ui.js");
  }
  if (!virtualizationService) {
    throw new Error("BeagleVirtualizationService must be loaded before beagle-ui.js");
  }
  if (!platformService) {
    throw new Error("BeaglePlatformService must be loaded before beagle-ui.js");
  }
  if (!apiClient) {
    throw new Error("BeagleUiApiClient must be loaded before beagle-ui.js");
  }
  if (!beagleState) {
    throw new Error("BeagleUiState must be loaded before beagle-ui.js");
  }
  if (!usbUi) {
    throw new Error("BeagleUiUsbUi must be loaded before beagle-ui.js");
  }
  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before beagle-ui.js");
  }
  if (!desktopOverlay) {
    throw new Error("BeagleUiDesktopOverlay must be loaded before beagle-ui.js");
  }
  if (!browserActions) {
    throw new Error("BeagleUiBrowserActions must be loaded before beagle-ui.js");
  }

  function sleep(ms) {
    return new Promise(function(resolve) {
      window.setTimeout(resolve, ms);
    });
  }

  function resolveUsbInstallerUrl(ctx) {
    return common.resolveUsbInstallerUrl(ctx);
  }

  function resolveInstallerIsoUrl(ctx) {
    return common.resolveInstallerIsoUrl(ctx);
  }

  function withNoCache(url) {
    return common.withNoCache(url);
  }

  function resolveControlPlaneHealthUrl() {
    return common.resolveControlPlaneHealthUrl();
  }

  function resolveWebUiUrl() {
    return common.resolveWebUiUrl();
  }

  function managerUrlFromHealthUrl(healthUrl) {
    return common.managerUrlFromHealthUrl(healthUrl);
  }

  function normalizeBeagleApiPath(path) {
    return common.normalizeBeagleApiPath(path);
  }

  function showError(message) {
    return browserActions.showError(PRODUCT_LABEL, message);
  }

  function showToast(message) {
    return browserActions.showToast(PRODUCT_LABEL, message);
  }

  function openUrl(url) {
    return browserActions.openUrl(showError, url);
  }

  function triggerDownload(url) {
    return browserActions.triggerDownload(showError, url);
  }

  function webUiUrlWithToken(interactive) {
    var token = getApiToken(Boolean(interactive));
    var target = resolveWebUiUrl();
    if (!token) {
      return target;
    }
    try {
      var parsed = new URL(target, window.location.origin);
      parsed.hash = "beagle_token=" + encodeURIComponent(token);
      return parsed.toString();
    } catch (error) {
      return String(target || "") + "#beagle_token=" + encodeURIComponent(token);
    }
  }

  function getInstallerEligibilityKey(ctx) {
    return beagleState.getInstallerEligibilityKey(ctx);
  }

  function getVmInstallerEligibility(ctx) {
    return beagleState.getVmInstallerEligibility(ctx);
  }

  function openUsbInstaller(ctx) {
    showProfileModal(ctx || {}, { autoPrepareDownload: true });
  }

  function normalizeUiText(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function createVmLabels() {
    return [
      normalizeUiText("Create VM"),
      normalizeUiText("Erstelle VM"),
      normalizeUiText(gettext("Create VM"))
    ];
  }

  function getComponentText(component) {
    if (!component) {
      return "";
    }
    if (typeof component.getText === "function") {
      return component.getText() || "";
    }
    return component.text || "";
  }

  function looksLikeCreateVmTrigger(component) {
    var normalized = normalizeUiText(getComponentText(component));
    var labels = createVmLabels();
    return component && (
      component.itemId === "createvm" ||
      component.reference === "createvm" ||
      labels.indexOf(normalized) !== -1
    );
  }

  function selectedNodeName() {
    return virtualizationService.selectedNodeName();
  }

  function safeHostnameCandidate(value, fallbackVmid) {
    var cleaned = String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .replace(/^-+|-+$/g, "");
    if (!cleaned) {
      cleaned = fallbackVmid ? ("beagle-" + String(fallbackVmid)) : "beagle";
    }
    cleaned = cleaned.slice(0, 63).replace(/-+$/g, "");
    return cleaned || (fallbackVmid ? ("beagle-" + String(fallbackVmid)) : "beagle");
  }

  function apiGetProvisioningCatalog() {
    return platformService.fetchProvisioningCatalog();
  }

  function apiCreateProvisionedVm(payload) {
    return platformService.createVm(payload);
  }

  function apiUpdateProvisionedVm(vmid, payload) {
    return platformService.updateVm(vmid, payload);
  }

  function apiGetProvisioningState(vmid) {
    return platformService.fetchVmProvisioningState(vmid);
  }

  function parseListText(value) {
    return String(value || "")
      .split(/[\n,]+/)
      .map(function(item) { return String(item || "").trim(); })
      .filter(Boolean);
  }

  function listToMultiline(value) {
    return Array.isArray(value) ? value.join("\n") : "";
  }

  function readCheckedValues(container, fieldName) {
    return container.query('checkboxfield[name="' + fieldName + '"]').filter(function(field) {
      return Boolean(field && field.checked);
    }).map(function(field) {
      return String(field.inputValue || field.name || "").trim();
    }).filter(Boolean);
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

  function showProvisioningResultWindow(created) {
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

  function showUbuntuBeagleCreateModal(ctx) {
    if (!(window.Ext && Ext.create)) {
      showError("Proxmox UI-Komponenten sind noch nicht bereit.");
      return;
    }
    if (!ensureApiToken()) {
      return;
    }
    if (window.Ext && Ext.Msg && Ext.Msg.wait) {
      Ext.Msg.wait("Provisioning-Katalog wird geladen ...", "Beagle OS");
    }
    Promise.all([
      apiGetProvisioningCatalog(),
      virtualizationService.listNodes().catch(function() { return []; })
    ]).then(function(results) {
      var catalog = results[0] || {};
      var providerNodes = Array.isArray(results[1]) ? results[1] : [];
      var profileValue = function(source, camelKey, snakeKey, fallback) {
        if (source && source[camelKey] !== undefined && source[camelKey] !== null && source[camelKey] !== "") {
          return source[camelKey];
        }
        if (source && source[snakeKey] !== undefined && source[snakeKey] !== null && source[snakeKey] !== "") {
          return source[snakeKey];
        }
        return fallback;
      };
      var defaults = catalog && catalog.defaults ? catalog.defaults : {};
      var profileRecord = ctx && ctx.profile ? ctx.profile : null;
      var isEdit = Boolean(profileRecord);
      var initialNode = String(ctx && ctx.node || selectedNodeName() || defaults.node || "");
      var osProfiles = Array.isArray(catalog && catalog.os_profiles) ? catalog.os_profiles : [];
      var desktopProfiles = Array.isArray(catalog && catalog.desktop_profiles) ? catalog.desktop_profiles : [];
      var softwarePresets = Array.isArray(catalog && catalog.software_presets) ? catalog.software_presets : [];
      var initialProfile = osProfiles[0] || {};
      var nextVmid = Number(defaults.next_vmid || 0) || "";
      var initialName = String(profileValue(profileRecord, "name", "name", "ubuntu-beagle-" + String(nextVmid || "vm")));
      var initialHostname = safeHostnameCandidate(String(profileValue(profileRecord, "identityHostname", "identity_hostname", initialName)), profileValue(profileRecord, "vmid", "vmid", nextVmid));
      var initialDesktop = String(profileValue(profileRecord, "desktopId", "desktop_id", defaults.desktop || (desktopProfiles[0] && desktopProfiles[0].id) || "xfce"));
      var initialLocale = String(profileValue(profileRecord, "identityLocale", "identity_locale", defaults.identity_locale || "de_DE.UTF-8"));
      var initialKeymap = String(profileValue(profileRecord, "identityKeymap", "identity_keymap", defaults.identity_keymap || "de"));
      var initialPackagePresets = Array.isArray(profileValue(profileRecord, "packagePresets", "package_presets", [])) ? profileValue(profileRecord, "packagePresets", "package_presets", []) : [];
      var initialExtraPackages = Array.isArray(profileValue(profileRecord, "extraPackages", "extra_packages", [])) ? profileValue(profileRecord, "extraPackages", "extra_packages", []) : [];
      var nodeRecords = Array.isArray(catalog && catalog.nodes) ? catalog.nodes.map(function(item) {
        return {
          value: String(item.name || ""),
          label: String(item.name || "") + (item.status ? (" (" + String(item.status || "") + ")") : "")
        };
      }) : providerNodes.map(function(item) {
        return {
          value: String(item.name || item.id || ""),
          label: String(item.label || item.name || item.id || "")
        };
      });
      var imageStorageRecords = catalog && catalog.storages && Array.isArray(catalog.storages.images) ? catalog.storages.images.map(function(item) {
        return { value: String(item.id || ""), label: String(item.id || "") };
      }) : [];
      var isoStorageRecords = catalog && catalog.storages && Array.isArray(catalog.storages.iso) ? catalog.storages.iso.map(function(item) {
        return { value: String(item.id || ""), label: String(item.id || "") };
      }) : [];
      var bridgesByNode = catalog && catalog.bridges_by_node ? catalog.bridges_by_node : {};
      var bridgeStore = Ext.create("Ext.data.Store", { fields: ["value", "label"], data: [] });
      var profileStore = Ext.create("Ext.data.Store", {
        fields: ["value", "label", "release", "desktop", "streaming"],
        data: osProfiles.map(function(item) {
          return {
            value: String(item.id || ""),
            label: String(item.label || item.id || ""),
            release: String(item.release || ""),
            desktop: String(item.desktop || ""),
            streaming: String(item.streaming || "")
          };
        })
      });
      var desktopStore = Ext.create("Ext.data.Store", {
        fields: ["value", "label", "session", "features"],
        data: desktopProfiles.map(function(item) {
          return {
            value: String(item.id || ""),
            label: String(item.label || item.id || ""),
            session: String(item.session || ""),
            features: Array.isArray(item.features) ? item.features.join(", ") : ""
          };
        })
      });
      var nodeStore = Ext.create("Ext.data.Store", { fields: ["value", "label"], data: nodeRecords });
      var imageStorageStore = Ext.create("Ext.data.Store", { fields: ["value", "label"], data: imageStorageRecords });
      var isoStorageStore = Ext.create("Ext.data.Store", { fields: ["value", "label"], data: isoStorageRecords });
      var windowRef;
      var hostnameTouched = false;
      var softwareCheckboxes = softwarePresets.map(function(item) {
        var presetId = String(item.id || "");
        return {
          xtype: "checkboxfield",
          name: "package_presets",
          boxLabel: String(item.label || presetId) + (item.description ? " - " + String(item.description || "") : ""),
          inputValue: presetId,
          checked: initialPackagePresets.indexOf(presetId) !== -1
        };
      });

      function bridgeRecordsForNode(nodeName) {
        var values = bridgesByNode[nodeName] || catalog && catalog.bridges || [];
        return (values || []).map(function(item) {
          return { value: String(item || ""), label: String(item || "") };
        });
      }

      function syncBridgeStore(nodeName) {
        var records = bridgeRecordsForNode(nodeName);
        bridgeStore.loadData(records);
        if (!records.length && defaults.bridge) {
          bridgeStore.loadData([{ value: String(defaults.bridge || ""), label: String(defaults.bridge || "") }]);
        }
        if (windowRef && windowRef.down('combo[name="bridge"]')) {
          if (!windowRef.down('combo[name="bridge"]').getValue()) {
            windowRef.down('combo[name="bridge"]').setValue(String(defaults.bridge || (records[0] && records[0].value) || ""));
          }
        }
      }

      function syncHostnameField() {
        if (!windowRef || hostnameTouched || isEdit) {
          return;
        }
        var vmidField = windowRef.down('numberfield[name="vmid"]');
        var nameField = windowRef.down('textfield[name="name"]');
        var hostnameField = windowRef.down('textfield[name="hostname"]');
        if (!hostnameField) {
          return;
        }
        windowRef.__beagleSyncingHostname = true;
        hostnameField.setValue(safeHostnameCandidate(nameField && nameField.getValue() || "", vmidField && vmidField.getValue() || nextVmid));
        windowRef.__beagleSyncingHostname = false;
      }

      function currentProfile() {
        var profileId = windowRef && windowRef.down('combo[name="os_profile"]') ? windowRef.down('combo[name="os_profile"]').getValue() : "";
        return osProfiles.find(function(item) {
          return String(item.id || "") === String(profileId || "");
        }) || initialProfile;
      }

      function currentDesktop() {
        var desktopId = windowRef && windowRef.down('combo[name="desktop"]') ? windowRef.down('combo[name="desktop"]').getValue() : "";
        return desktopProfiles.find(function(item) {
          return String(item.id || "") === String(desktopId || "");
        }) || desktopProfiles[0] || {};
      }

      function updateProfileSummary() {
        var profile = currentProfile();
        var desktop = currentDesktop();
        var summary = [
          String(profile.label || ""),
          String(profile.release || ""),
          String(desktop.label || profile.desktop || ""),
          String(profile.streaming || "")
        ].filter(Boolean).join(" | ");
        if (windowRef && windowRef.down('#beagleProvisioningProfileSummary')) {
          windowRef.down('#beagleProvisioningProfileSummary').setValue(summary || "Ubuntu Provisioning");
        }
        if (windowRef && windowRef.down('#beagleDesktopSummary')) {
          windowRef.down('#beagleDesktopSummary').setValue([
            String(desktop.label || ""),
            String(desktop.session || ""),
            String(desktop.features || "")
          ].filter(Boolean).join(" | "));
        }
      }

      if (window.Ext && Ext.Msg && Ext.Msg.hide) {
        Ext.Msg.hide();
      }

      windowRef = Ext.create("Ext.window.Window", {
        title: isEdit ? "Bearbeite Beagle Desktop VM" : "Erstelle Beagle Desktop VM",
        modal: true,
        width: 820,
        maxHeight: 860,
        layout: "fit",
        items: [
          {
            xtype: "form",
            bodyPadding: 18,
            scrollable: true,
            defaults: {
              anchor: "100%",
              labelWidth: 180
            },
            items: [
              {
                xtype: "displayfield",
                value: isEdit
                  ? "Aendert Desktop, Locale, Tastaturlayout und zusaetzliche Pakete einer bestehenden Beagle Desktop VM. Bei laufender VM wird die Aenderung direkt im Gast angewendet."
                  : "Provisioniert eine komplette Desktop-VM ueber die Beagle Control Plane: Ubuntu Autoinstall, waehlbarer Desktop, LightDM, Sunshine, QEMU Guest Agent und Beagle-Metadaten."
              },
              {
                xtype: "fieldset",
                title: "Plattform",
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "combo",
                    name: "os_profile",
                    fieldLabel: "OS",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: profileStore,
                    value: String(initialProfile.id || "")
                  },
                  {
                    xtype: "combo",
                    name: "desktop",
                    fieldLabel: "Desktop",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: desktopStore,
                    value: initialDesktop
                  },
                  {
                    xtype: "displayfield",
                    itemId: "beagleProvisioningProfileSummary",
                    fieldLabel: "Provisioning Stack",
                    value: ""
                  },
                  {
                    xtype: "displayfield",
                    itemId: "beagleDesktopSummary",
                    fieldLabel: "Desktop Profil",
                    value: ""
                  },
                  {
                    xtype: "combo",
                    name: "identity_locale",
                    fieldLabel: "Locale",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: Ext.create("Ext.data.Store", {
                      fields: ["value", "label"],
                      data: [
                        { value: "de_DE.UTF-8", label: "Deutsch (de_DE.UTF-8)" },
                        { value: "en_US.UTF-8", label: "English (en_US.UTF-8)" }
                      ]
                    }),
                    value: initialLocale
                  },
                  {
                    xtype: "combo",
                    name: "identity_keymap",
                    fieldLabel: "Tastaturlayout",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: Ext.create("Ext.data.Store", {
                      fields: ["value", "label"],
                      data: [
                        { value: "de", label: "Deutsch (de)" },
                        { value: "us", label: "US (us)" }
                      ]
                    }),
                    value: initialKeymap
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Identitaet",
                hidden: isEdit,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "combo",
                    name: "node",
                    fieldLabel: "Node",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: nodeStore,
                    value: initialNode
                  },
                  {
                    xtype: "numberfield",
                    name: "vmid",
                    fieldLabel: "VMID",
                    minValue: 1,
                    allowBlank: true,
                    value: nextVmid,
                    emptyText: "automatisch"
                  },
                  {
                    xtype: "textfield",
                    name: "name",
                    fieldLabel: "VM Name",
                    allowBlank: false,
                    value: initialName
                  },
                  {
                    xtype: "textfield",
                    name: "hostname",
                    fieldLabel: "Hostname",
                    allowBlank: false,
                    value: initialHostname
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Bestehende VM",
                hidden: !isEdit,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "displayfield",
                    fieldLabel: "Node",
                    value: String(profileValue(profileRecord, "node", "node", ""))
                  },
                  {
                    xtype: "displayfield",
                    fieldLabel: "VMID",
                    value: String(profileValue(profileRecord, "vmid", "vmid", ""))
                  },
                  {
                    xtype: "displayfield",
                    fieldLabel: "VM Name",
                    value: initialName
                  },
                  {
                    xtype: "displayfield",
                    fieldLabel: "Gast-User",
                    value: String(profileValue(profileRecord, "guestUser", "guest_user", defaults.guest_user || "beagle"))
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Gast-Zugang",
                hidden: isEdit,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "textfield",
                    name: "guest_user",
                    fieldLabel: "Ubuntu User",
                    allowBlank: false,
                    regex: /^[a-z_][a-z0-9_-]{0,31}$/,
                    value: String(defaults.guest_user || "beagle")
                  },
                  {
                    xtype: "textfield",
                    inputType: "password",
                    name: "guest_password",
                    fieldLabel: "Ubuntu Passwort",
                    allowBlank: true,
                    emptyText: "leer lassen = automatisch generieren"
                  },
                  {
                    xtype: "textfield",
                    inputType: "password",
                    name: "guest_password_confirm",
                    fieldLabel: "Passwort bestaetigen",
                    allowBlank: true,
                    emptyText: "nur bei manuellem Passwort noetig"
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Ressourcen",
                hidden: isEdit,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "numberfield",
                    name: "memory",
                    fieldLabel: "RAM (MiB)",
                    minValue: 2048,
                    value: Number(defaults.memory || 8192)
                  },
                  {
                    xtype: "numberfield",
                    name: "cores",
                    fieldLabel: "vCPU Cores",
                    minValue: 2,
                    value: Number(defaults.cores || 4)
                  },
                  {
                    xtype: "numberfield",
                    name: "disk_gb",
                    fieldLabel: "Disk (GB)",
                    minValue: 32,
                    value: Number(defaults.disk_gb || 64)
                  },
                  {
                    xtype: "combo",
                    name: "disk_storage",
                    fieldLabel: "Disk Storage",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: imageStorageStore,
                    value: String(defaults.disk_storage || "")
                  },
                  {
                    xtype: "combo",
                    name: "iso_storage",
                    fieldLabel: "ISO Storage",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: isoStorageStore,
                    value: String(defaults.iso_storage || "")
                  },
                  {
                    xtype: "combo",
                    name: "bridge",
                    fieldLabel: "Bridge",
                    allowBlank: false,
                    editable: false,
                    forceSelection: true,
                    queryMode: "local",
                    displayField: "label",
                    valueField: "value",
                    store: bridgeStore,
                    value: String(defaults.bridge || "")
                  },
                  {
                    xtype: "checkboxfield",
                    name: "start",
                    fieldLabel: "Nach Erstellung starten",
                    checked: true,
                    inputValue: "1",
                    uncheckedValue: "0"
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Software",
                collapsible: true,
                collapsed: false,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "displayfield",
                    fieldLabel: "Standard",
                    value: "Google Chrome wird immer installiert und als Default-Browser gesetzt."
                  },
                  {
                    xtype: "checkboxgroup",
                    fieldLabel: "Paket-Presets",
                    columns: 1,
                    vertical: true,
                    items: softwareCheckboxes.length ? softwareCheckboxes : [{
                      xtype: "displayfield",
                      value: "Keine Paket-Presets verfuegbar."
                    }]
                  },
                  {
                    xtype: "textarea",
                    name: "extra_packages",
                    fieldLabel: "Weitere APT-Pakete",
                    grow: true,
                    growMax: 120,
                    emptyText: "ein Paket pro Zeile oder komma-getrennt",
                    value: listToMultiline(initialExtraPackages)
                  }
                ]
              },
              {
                xtype: "fieldset",
                title: "Streaming und Zugriff",
                collapsible: true,
                collapsed: false,
                defaults: {
                  anchor: "100%",
                  labelWidth: 180
                },
                items: [
                  {
                    xtype: "displayfield",
                    fieldLabel: "Desktop",
                    value: "Sunshine Desktop Target"
                  },
                  {
                    xtype: "displayfield",
                    fieldLabel: "Streaming",
                    value: "Sunshine"
                  },
                  {
                    xtype: "textfield",
                    name: "sunshine_user",
                    fieldLabel: "Sunshine User",
                    allowBlank: true,
                    emptyText: "leer = sunshine-vm<VMID>"
                  },
                  {
                    xtype: "textfield",
                    inputType: "password",
                    name: "sunshine_password",
                    fieldLabel: "Sunshine Passwort",
                    allowBlank: true,
                    emptyText: "leer lassen = automatisch generieren"
                  }
                ]
              }
            ]
          }
        ],
        buttons: [
          {
            text: "Abbrechen",
            handler: function() {
              windowRef.close();
            }
          },
          {
            text: "Erstellen",
            ui: "primary",
            handler: function() {
              var form = windowRef.down("form").getForm();
              var values;
              var payload;
              var packagePresets;
              var extraPackages;
              if (!form.isValid()) {
                return;
              }
              values = form.getValues();
              if (!isEdit && values.guest_password && values.guest_password !== values.guest_password_confirm) {
                showError("Ubuntu-Passwort und Bestaetigung stimmen nicht ueberein.");
                return;
              }
              packagePresets = readCheckedValues(windowRef, "package_presets");
              extraPackages = parseListText(values.extra_packages);
              payload = {
                os_profile: String(values.os_profile || ""),
                desktop: String(values.desktop || ""),
                identity_locale: String(values.identity_locale || ""),
                identity_keymap: String(values.identity_keymap || ""),
                package_presets: packagePresets,
                extra_packages: extraPackages
              };
              if (!isEdit) {
                payload.node = String(values.node || "");
                payload.name = String(values.name || "").trim();
                payload.hostname = safeHostnameCandidate(values.hostname || values.name || "", values.vmid || nextVmid);
                payload.bridge = String(values.bridge || "");
                payload.guest_user = String(values.guest_user || "");
                payload.guest_password = String(values.guest_password || "");
                payload.sunshine_user = String(values.sunshine_user || "");
                payload.sunshine_password = String(values.sunshine_password || "");
                payload.disk_storage = String(values.disk_storage || "");
                payload.iso_storage = String(values.iso_storage || "");
                payload.start = values.start ? "1" : "0";
                payload.memory = Number(values.memory || defaults.memory || 8192);
                payload.cores = Number(values.cores || defaults.cores || 4);
                payload.disk_gb = Number(values.disk_gb || defaults.disk_gb || 64);
                if (String(values.vmid || "").trim()) {
                  payload.vmid = Number(values.vmid);
                }
              }
              windowRef.setLoading(isEdit ? "Beagle Desktop VM wird aktualisiert ..." : "Beagle Desktop VM wird provisioniert ...");
              (isEdit ? apiUpdateProvisionedVm(profileValue(profileRecord, "vmid", "vmid", 0), payload) : apiCreateProvisionedVm(payload)).then(function(created) {
                windowRef.setLoading(false);
                windowRef.close();
                if (isEdit) {
                  showToast("Beagle Desktop VM " + String(created && created.vmid || "") + " wurde aktualisiert.");
                  showProfileModal({ vmid: Number(created && created.vmid || profileValue(profileRecord, "vmid", "vmid", 0)), node: String(created && created.node || profileValue(profileRecord, "node", "node", "")) });
                } else {
                  showToast("Beagle Desktop VM " + String(created && created.vmid || "") + " wird jetzt provisioniert.");
                  showProvisioningResultWindow(created);
                }
              }).catch(function(error) {
                windowRef.setLoading(false);
                showError((isEdit ? "Beagle Desktop VM konnte nicht aktualisiert werden: " : "Beagle Desktop VM konnte nicht erstellt werden: ") + error.message);
              });
            }
          }
        ],
        listeners: {
          afterrender: function() {
            syncBridgeStore(initialNode);
            updateProfileSummary();
            syncHostnameField();
            if (!isEdit) {
              windowRef.down('combo[name="node"]').on("change", function(field, value) {
                syncBridgeStore(String(value || ""));
              });
            }
            windowRef.down('combo[name="os_profile"]').on("change", function() {
              updateProfileSummary();
            });
            windowRef.down('combo[name="desktop"]').on("change", function() {
              updateProfileSummary();
            });
            if (!isEdit) {
              windowRef.down('numberfield[name="vmid"]').on("change", function() {
                syncHostnameField();
              });
              windowRef.down('textfield[name="name"]').on("change", function() {
                syncHostnameField();
              });
              windowRef.down('textfield[name="hostname"]').on("change", function(field, value) {
                if (windowRef.__beagleSyncingHostname) {
                  return;
                }
                hostnameTouched = Boolean(String(value || "").trim());
              });
            }
          }
        }
      });
      windowRef.show();
    }).catch(function(error) {
      if (window.Ext && Ext.Msg && Ext.Msg.hide) {
        Ext.Msg.hide();
      }
      showError("Beagle Provisioning-Katalog konnte nicht geladen werden: " + error.message);
    });
  }

  function ensureStyles() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }

    var style = document.createElement("style");
    style.id = STYLE_ID;
    style.textContent = [
      "#" + OVERLAY_ID + " { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.55); z-index: 100000; display: flex; align-items: center; justify-content: center; padding: 24px; }",
      "#" + OVERLAY_ID + " .beagle-modal { width: min(980px, 100%); max-height: calc(100vh - 48px); overflow: auto; background: linear-gradient(180deg, #fff8ef 0%, #ffffff 100%); border: 1px solid #fed7aa; border-radius: 22px; box-shadow: 0 30px 70px rgba(15, 23, 42, 0.25); color: #111827; }",
      "#" + OVERLAY_ID + " .beagle-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; padding: 24px 28px 18px; background: radial-gradient(circle at top right, rgba(59,130,246,0.12), transparent 30%), radial-gradient(circle at top left, rgba(249,115,22,0.18), transparent 36%); border-bottom: 1px solid #fdba74; }",
      "#" + OVERLAY_ID + " .beagle-title { font: 700 28px/1.1 'Trebuchet MS', 'Segoe UI', sans-serif; margin: 0 0 6px; }",
      "#" + OVERLAY_ID + " .beagle-subtitle { margin: 0; color: #7c2d12; font-size: 14px; }",
      "#" + OVERLAY_ID + " .beagle-close { border: 0; background: #111827; color: #fff; border-radius: 999px; width: 36px; height: 36px; cursor: pointer; font-size: 20px; line-height: 36px; }",
      "#" + OVERLAY_ID + " .beagle-body { padding: 22px 28px 28px; display: grid; gap: 18px; }",
      "#" + OVERLAY_ID + " .beagle-banner { padding: 12px 14px; border-radius: 14px; font-weight: 600; }",
      "#" + OVERLAY_ID + " .beagle-banner.info { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }",
      "#" + OVERLAY_ID + " .beagle-banner.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }",
      "#" + OVERLAY_ID + " .beagle-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }",
      "#" + OVERLAY_ID + " .beagle-card { background: linear-gradient(180deg, #ffffff 0%, #fffaf3 100%); border: 1px solid #d6d3d1; border-radius: 18px; padding: 16px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.9), 0 8px 20px rgba(15, 23, 42, 0.06); }",
      "#" + OVERLAY_ID + " .beagle-card h3 { margin: -16px -16px 14px; padding: 12px 16px; border-bottom: 1px solid #fed7aa; border-radius: 18px 18px 0 0; background: linear-gradient(90deg, #fff1dc 0%, #fff7ed 52%, #eef6ff 100%); font: 700 15px/1.2 'Trebuchet MS', 'Segoe UI', sans-serif; color: #7c2d12; }",
      "#" + OVERLAY_ID + " .beagle-kv { display: grid; gap: 8px; }",
      "#" + OVERLAY_ID + " .beagle-kv-row { display: grid; gap: 6px; padding: 10px 12px; border: 1px solid #e7e5e4; border-left: 4px solid #f97316; border-radius: 12px; background: #ffffff; }",
      "#" + OVERLAY_ID + " .beagle-kv-row:nth-child(even) { background: #f8fbff; border-left-color: #0ea5e9; }",
      "#" + OVERLAY_ID + " .beagle-kv-row strong { color: #9a3412; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }",
      "#" + OVERLAY_ID + " .beagle-kv-row span { word-break: break-word; color: #111827; font-weight: 600; line-height: 1.45; }",
      "#" + OVERLAY_ID + " .beagle-actions { display: flex; flex-wrap: wrap; gap: 10px; }",
      "#" + OVERLAY_ID + " .beagle-btn { border: 0; border-radius: 999px; padding: 10px 16px; font-weight: 700; cursor: pointer; }",
      "#" + OVERLAY_ID + " .beagle-btn.primary { background: linear-gradient(135deg, #f97316, #0ea5e9); color: #fff; }",
      "#" + OVERLAY_ID + " .beagle-btn.secondary { background: #fff; color: #111827; border: 1px solid #d1d5db; }",
      "#" + OVERLAY_ID + " .beagle-btn.muted { background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }",
      "#" + OVERLAY_ID + " .beagle-code { width: 100%; min-height: 180px; resize: vertical; border-radius: 14px; border: 1px solid #d1d5db; padding: 12px; font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #0f172a; color: #e2e8f0; }",
      "#" + OVERLAY_ID + " .beagle-notes { margin: 0; padding-left: 18px; }",
      "#" + OVERLAY_ID + " .beagle-muted { color: #6b7280; }",
      "#" + OVERLAY_ID + " .beagle-table-wrap { overflow: auto; border-radius: 16px; border: 1px solid #e5e7eb; background: rgba(255,255,255,0.92); }",
      "#" + OVERLAY_ID + " .beagle-table { width: 100%; border-collapse: collapse; min-width: 880px; }",
      "#" + OVERLAY_ID + " .beagle-table th, #" + OVERLAY_ID + " .beagle-table td { padding: 12px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; vertical-align: top; }",
      "#" + OVERLAY_ID + " .beagle-table th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: #9a3412; background: #fff7ed; position: sticky; top: 0; }",
      "#" + OVERLAY_ID + " .beagle-badge { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 10px; font-size: 12px; font-weight: 700; }",
      "#" + OVERLAY_ID + " .beagle-badge.healthy { background: #ecfdf5; color: #047857; }",
      "#" + OVERLAY_ID + " .beagle-badge.degraded { background: #fffbeb; color: #b45309; }",
      "#" + OVERLAY_ID + " .beagle-badge.drifted { background: #fef2f2; color: #b91c1c; }",
      "#" + OVERLAY_ID + " .beagle-badge.stale { background: #eef2ff; color: #4338ca; }",
      "#" + OVERLAY_ID + " .beagle-badge.pending, #" + OVERLAY_ID + " .beagle-badge.unmanaged { background: #eff6ff; color: #1d4ed8; }",
      "#" + OVERLAY_ID + " .beagle-inline-actions { display: flex; flex-wrap: wrap; gap: 8px; }",
      "#" + OVERLAY_ID + " .beagle-mini-btn { border: 1px solid #d1d5db; background: #fff; border-radius: 999px; padding: 6px 10px; font-size: 12px; font-weight: 700; cursor: pointer; }",
      "#" + OVERLAY_ID + " .beagle-select-cell { width: 36px; }",
      "#" + OVERLAY_ID + " .beagle-row-select { width: 16px; height: 16px; accent-color: #ea580c; }",
      "#" + FLEET_LAUNCHER_ID + " { position: fixed; right: 22px; bottom: 22px; z-index: 99999; border: 0; border-radius: 999px; padding: 12px 18px; font: 700 14px/1 'Trebuchet MS', 'Segoe UI', sans-serif; color: #fff; background: linear-gradient(135deg, #f97316, #0ea5e9); box-shadow: 0 18px 40px rgba(15, 23, 42, 0.28); cursor: pointer; }",

      /* ── Desktop Overlay ── */
      "#" + OVERLAY_ID + ".beagle-desktop-mode { padding: 0; background: none; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-scene { position: absolute; inset: 0; overflow: hidden; font-family: 'SF Pro Display', 'Segoe UI', -apple-system, sans-serif; color: #fff; background: #0a0612; }",

      /* cyberpunk background */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg { position: absolute; inset: 0; background: linear-gradient(180deg, #0c0024 0%, #120835 25%, #1a0a2e 50%, #0d0620 75%, #060212 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg::before { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at 20% 20%, rgba(255,0,180,0.15) 0%, transparent 50%), radial-gradient(ellipse at 80% 30%, rgba(0,255,255,0.12) 0%, transparent 45%), radial-gradient(ellipse at 50% 80%, rgba(255,0,100,0.1) 0%, transparent 50%), radial-gradient(ellipse at 70% 60%, rgba(120,0,255,0.08) 0%, transparent 40%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-bg::after { content: ''; position: absolute; inset: 0; background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(255,0,180,0.03) 2px, rgba(255,0,180,0.03) 4px); pointer-events: none; }",

      /* neon city silhouette */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city { position: absolute; bottom: 0; left: 0; right: 0; height: 55%; background: linear-gradient(180deg, transparent 0%, rgba(10,2,20,0.6) 40%, rgba(10,2,20,0.95) 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city::before { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 100%; background: repeating-linear-gradient(90deg, transparent 0px, transparent 40px, rgba(255,0,180,0.04) 40px, rgba(255,0,180,0.04) 42px, transparent 42px, transparent 120px, rgba(0,255,255,0.03) 120px, rgba(0,255,255,0.03) 121px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-city-blocks { position: absolute; bottom: 8%; left: 0; right: 0; height: 40%; display: flex; align-items: flex-end; justify-content: center; gap: 3px; padding: 0 5%; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-building { flex: 0 0 auto; background: linear-gradient(180deg, rgba(20,5,40,0.95), rgba(10,2,20,0.98)); border-radius: 2px 2px 0 0; position: relative; box-shadow: 0 0 8px rgba(255,0,180,0.15), inset 0 0 20px rgba(0,0,0,0.5); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-building::after { content: ''; position: absolute; inset: 4px; background: repeating-linear-gradient(0deg, transparent 0px, transparent 6px, rgba(255,200,50,0.08) 6px, rgba(255,200,50,0.08) 8px); mask-image: repeating-linear-gradient(90deg, transparent 0px, transparent 3px, black 3px, black 5px, transparent 5px, transparent 8px); -webkit-mask-image: repeating-linear-gradient(90deg, transparent 0px, transparent 3px, black 3px, black 5px, transparent 5px, transparent 8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-neon-line { position: absolute; height: 2px; border-radius: 1px; filter: blur(1px); }",

      /* wet floor reflection */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-floor { position: absolute; bottom: 0; left: 0; right: 0; height: 8%; background: linear-gradient(180deg, rgba(10,2,20,0.3) 0%, rgba(5,1,15,0.8) 100%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-floor::before { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,0,180,0.06), rgba(0,255,255,0.04), transparent); }",

      /* top bar */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar { position: absolute; top: 0; left: 0; right: 0; height: 32px; background: rgba(0,0,0,0.75); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: space-between; padding: 0 16px; font-size: 13px; z-index: 10; border-bottom: 1px solid rgba(255,255,255,0.06); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-left { font-weight: 600; cursor: default; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-center { position: absolute; left: 50%; transform: translateX(-50%); font-weight: 500; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-right { display: flex; gap: 8px; align-items: center; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-topbar-right svg { width: 16px; height: 16px; fill: #fff; opacity: 0.8; }",

      /* left dock */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 12px; z-index: 10; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon { width: 44px; height: 44px; border-radius: 50%; border: none; cursor: pointer; transition: transform 0.15s ease, box-shadow 0.15s ease; box-shadow: 0 2px 8px rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon:hover { transform: scale(1.15); box-shadow: 0 4px 16px rgba(0,0,0,0.4); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-dock-icon svg { width: 22px; height: 22px; fill: currentColor; }",

      /* main window */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-window { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -52%); width: min(700px, 80vw); background: rgba(255,255,255,0.95); border-radius: 12px; box-shadow: 0 25px 80px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,0,0,0.1); z-index: 10; color: #222; overflow: hidden; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-titlebar { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: linear-gradient(180deg, #e8e8e8, #d4d4d4); border-bottom: 1px solid #bbb; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dots { display: flex; gap: 7px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot { width: 12px; height: 12px; border-radius: 50%; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.close { background: #ff5f57; border: 1px solid #e0443e; cursor: pointer; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.minimize { background: #ffbd2e; border: 1px solid #dea123; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-dot.maximize { background: #28c940; border: 1px solid #1aab29; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-title { font-size: 13px; font-weight: 600; color: #333; }",

      /* window body */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-body { display: grid; grid-template-columns: 200px 1fr; min-height: 280px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-sidebar { padding: 20px 16px; background: #f5f5f5; border-right: 1px solid #e0e0e0; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-sidebar h3 { margin: 0 0 14px; font-size: 16px; font-weight: 700; color: #111; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-app-item { display: block; width: 100%; text-align: left; padding: 8px 12px; border: none; background: none; border-radius: 6px; font-size: 14px; color: #333; cursor: pointer; margin-bottom: 2px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-app-item:hover { background: rgba(0,0,0,0.06); }",

      /* window content */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-win-content { padding: 24px; display: flex; flex-direction: column; align-items: flex-start; gap: 12px; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-welcome-title { margin: 0; font-size: 20px; font-weight: 700; color: #111; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-welcome-sub { margin: 0; font-size: 13px; color: #888; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-preview { width: 100%; max-width: 360px; aspect-ratio: 16/9; border-radius: 10px; overflow: hidden; background: linear-gradient(135deg, #0c0024, #1a0a2e, #120835); box-shadow: 0 8px 24px rgba(0,0,0,0.2); position: relative; margin: 6px 0; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-preview::after { content: ''; position: absolute; inset: 0; background: radial-gradient(ellipse at 30% 40%, rgba(255,0,180,0.2), transparent 60%), radial-gradient(ellipse at 70% 30%, rgba(0,255,255,0.15), transparent 50%); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-wallpaper-label { position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%); font-family: 'Impact', 'Arial Black', sans-serif; font-size: 22px; color: #fff; text-shadow: 0 0 10px rgba(255,0,180,0.6), 0 2px 4px rgba(0,0,0,0.5); letter-spacing: 2px; z-index: 1; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-btn-wallpaper { display: inline-block; padding: 10px 28px; border: none; border-radius: 999px; background: #00e5ff; color: #003; font-weight: 700; font-size: 14px; cursor: pointer; box-shadow: 0 4px 14px rgba(0,229,255,0.3); transition: transform 0.15s ease; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-btn-wallpaper:hover { transform: translateY(-1px); }",

      /* bottom branding */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-branding { position: absolute; bottom: 6%; left: 50%; transform: translateX(-50%); text-align: center; z-index: 5; pointer-events: none; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-title { font-family: 'Impact', 'Arial Black', sans-serif; font-size: clamp(48px, 8vw, 100px); line-height: 1; color: #fff; text-shadow: 0 0 20px rgba(255,0,180,0.4), 0 4px 8px rgba(0,0,0,0.4); letter-spacing: 4px; margin: 0; white-space: nowrap; }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-title span { color: #ff1493; text-shadow: 0 0 30px rgba(255,20,147,0.6), 0 0 60px rgba(255,20,147,0.3); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-brand-tagline { font-family: 'Courier New', monospace; font-size: clamp(11px, 1.5vw, 16px); color: #00e5ff; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 8px; text-shadow: 0 0 12px rgba(0,229,255,0.5); }",

      /* badge */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-badge { position: absolute; bottom: 16px; right: 20px; display: flex; align-items: center; gap: 8px; z-index: 10; font-size: 12px; color: rgba(255,255,255,0.6); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-badge-logo { width: 40px; height: 40px; border-radius: 8px; background: rgba(255,255,255,0.1); }",

      /* close overlay button */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-close-overlay { position: absolute; top: 40px; right: 16px; z-index: 20; border: none; background: rgba(0,0,0,0.5); color: #fff; border-radius: 50%; width: 32px; height: 32px; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-close-overlay:hover { background: rgba(0,0,0,0.7); }",

      /* details link */
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-details-link { position: absolute; top: 40px; left: 80px; z-index: 20; border: none; background: rgba(0,0,0,0.5); color: #00e5ff; border-radius: 999px; padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer; backdrop-filter: blur(8px); }",
      "#" + OVERLAY_ID + ".beagle-desktop-mode .bd-details-link:hover { background: rgba(0,0,0,0.7); }"
    ].join("\n");
    document.head.appendChild(style);
  }

  function removeOverlay() {
    var existing = document.getElementById(OVERLAY_ID);
    if (existing) {
      existing.remove();
    }
  }

  function copyText(text, successMessage) {
    var value = String(text || "");
    if (!value) {
      showError("Keine Daten zum Kopieren vorhanden.");
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(function() {
        showToast(successMessage || "In die Zwischenablage kopiert.");
      }).catch(function() {
        fallbackCopyText(value, successMessage);
      });
      return;
    }

    fallbackCopyText(value, successMessage);
  }

  function fallbackCopyText(text, successMessage) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {
      document.execCommand("copy");
      showToast(successMessage || "In die Zwischenablage kopiert.");
    } catch (error) {
      showError("Kopieren fehlgeschlagen.");
    } finally {
      textarea.remove();
    }
  }

  function parseDescriptionMeta(description) {
    var meta = {};
    String(description || "")
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      .split("\n")
      .forEach(function(rawLine) {
        var line = rawLine.trim();
        var index = line.indexOf(":");
        var key;
        var value;
        if (index <= 0) {
          return;
        }
        key = line.slice(0, index).trim().toLowerCase();
        value = line.slice(index + 1).trim();
        if (key && !(key in meta)) {
          meta[key] = value;
        }
      });
    return meta;
  }

  function maskSecret(value) {
    if (!value) {
      return "nicht gesetzt";
    }
    if (value.length <= 4) {
      return "****";
    }
    return value.slice(0, 2) + "***" + value.slice(-2);
  }

  function apiGetJson(path) {
    return apiClient.apiGetJson(path);
  }

  function getApiToken(interactive) {
    return apiClient.getApiToken(interactive);
  }

  function ensureApiToken() {
    var token = getApiToken(true);
    if (token) {
      return token;
    }
    showError("Beagle API Token ist fuer diese Browser-Sitzung nicht gesetzt.");
    return "";
  }

  function downloadProtectedFile(path, filename) {
    return apiClient.downloadProtectedFile(path, filename);
  }

  function apiGetInstallerPrep(vmid) {
    return platformService.fetchInstallerPreparation(vmid);
  }

  function apiStartInstallerPrep(vmid) {
    return platformService.prepareInstallerTarget(vmid);
  }

  function apiGetVmCredentials(vmid) {
    return platformService.fetchVmCredentials(vmid);
  }

  function apiCreateSunshineAccess(vmid) {
    return platformService.createSunshineAccess(vmid);
  }

  function installerPrepBannerClass(state) {
    return usbUi.installerPrepBannerClass(state);
  }

  function formatInstallerPrepValue(value, fallback) {
    return usbUi.formatInstallerPrepValue(value, fallback);
  }

  function installerTargetState(profile, state) {
    return usbUi.installerTargetState(profile, state);
  }

  function shouldReuseInstallerPrepState(state) {
    return usbUi.shouldReuseInstallerPrepState(state);
  }

  function syncInstallerButtons(overlay, state) {
    return usbUi.syncInstallerButtons(overlay, state);
  }

  function applyInstallerPrepState(overlay, state) {
    return usbUi.applyInstallerPrepState(overlay, state);
  }

  async function prepareInstallerDownload(profile, overlay, artifactKey, actionName, loadingLabel, successMessage, filenameOverride) {
    var downloadButton = overlay.querySelector('[data-beagle-action="' + actionName + '"]');
    var originalText = downloadButton ? downloadButton.textContent : "USB Installer";
    var state = null;
    var attempt;
    var status;
    var artifactUrl = profile && profile[artifactKey] ? String(profile[artifactKey]) : "";
    var filename = filenameOverride || (artifactKey === "installerWindowsUrl"
      ? ("pve-thin-client-usb-installer-vm-" + profile.vmid + ".ps1")
      : ("pve-thin-client-usb-installer-vm-" + profile.vmid + ".sh"));
    var requiresProtectedDownload = /^\/beagle-api\//.test(artifactUrl);

    if (profile && profile.installerTargetEligible === false) {
      applyInstallerPrepState(overlay, profile.installerPrep || {});
      return;
    }

    if (downloadButton) {
      downloadButton.disabled = true;
      downloadButton.textContent = loadingLabel;
    }

    try {
      state = await apiGetInstallerPrep(profile.vmid).catch(function() {
        return profile.installerPrep || null;
      });
      if (state) {
        applyInstallerPrepState(overlay, state);
      }
      status = String(state && state.status || "").toLowerCase();
      if (state && String(state && state.status || "").toLowerCase() === "ready") {
        if (requiresProtectedDownload) {
          await downloadProtectedFile(normalizeBeagleApiPath(profile[artifactKey]), filename);
        } else {
          triggerDownload(profile[artifactKey]);
        }
        showToast(successMessage);
        return;
      }
      if (!shouldReuseInstallerPrepState(state)) {
        state = await apiStartInstallerPrep(profile.vmid);
        applyInstallerPrepState(overlay, state);
      }
      for (attempt = 0; attempt < 180; attempt += 1) {
        if (String(state && state.status || "").toLowerCase() === "ready") {
          if (requiresProtectedDownload) {
            await downloadProtectedFile(normalizeBeagleApiPath(profile[artifactKey]), filename);
          } else {
            triggerDownload(profile[artifactKey]);
          }
          showToast(successMessage);
          return;
        }
        if (String(state && state.status || "").toLowerCase() === "error") {
          throw new Error(String(state && state.message || "Installer-Vorbereitung fehlgeschlagen."));
        }
        await sleep(2000);
        state = await apiGetInstallerPrep(profile.vmid);
        applyInstallerPrepState(overlay, state);
      }
      throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
    } catch (error) {
      applyInstallerPrepState(overlay, {
        status: "error",
        phase: "failed",
        progress: 100,
        message: error && error.message ? error.message : "Installer-Vorbereitung fehlgeschlagen.",
        sunshine_status: state && state.sunshine_status || null
      });
      showError("Installer konnte nicht vorbereitet werden: " + (error && error.message ? error.message : error));
    } finally {
      if (downloadButton) {
        downloadButton.disabled = false;
        downloadButton.textContent = originalText;
      }
    }
  }

  function firstGuestIpv4(interfaces) {
    var list = Array.isArray(interfaces) ? interfaces : [];
    var iface;
    var addresses;
    var i;
    var j;
    var address;
    for (i = 0; i < list.length; i += 1) {
      iface = list[i] || {};
      addresses = Array.isArray(iface["ip-addresses"]) ? iface["ip-addresses"] : [];
      for (j = 0; j < addresses.length; j += 1) {
        address = addresses[j] || {};
        if (address["ip-address-type"] !== "ipv4") {
          continue;
        }
        if (!address["ip-address"] || /^127\./.test(address["ip-address"]) || /^169\.254\./.test(address["ip-address"])) {
          continue;
        }
        return address["ip-address"];
      }
    }
    return "";
  }

  function buildEndpointEnv(profile) {
    var endpointProfileName = profile.expectedProfileName || ("vm-" + profile.vmid);
    var lines = [
      "PVE_THIN_CLIENT_MODE=\"MOONLIGHT\"",
      "PVE_THIN_CLIENT_PROFILE_NAME=\"" + endpointProfileName + "\"",
      "PVE_THIN_CLIENT_AUTOSTART=\"1\"",
      "PVE_THIN_CLIENT_PROXMOX_HOST=\"" + (profile.proxmoxHost || window.location.hostname) + "\"",
      "PVE_THIN_CLIENT_PROXMOX_PORT=\"8006\"",
      "PVE_THIN_CLIENT_PROXMOX_NODE=\"" + (profile.node || "") + "\"",
      "PVE_THIN_CLIENT_PROXMOX_VMID=\"" + String(profile.vmid || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_URL=\"" + (profile.managerUrl || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY=\"" + (profile.managerPinnedPubkey || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_HOST=\"" + (profile.streamHost || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_PORT=\"" + (profile.moonlightPort || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_APP=\"" + (profile.app || "Desktop") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION=\"" + (profile.resolution || "auto") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_FPS=\"" + (profile.fps || "60") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_BITRATE=\"" + (profile.bitrate || "20000") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC=\"" + (profile.codec || "H.264") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER=\"" + (profile.decoder || "auto") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG=\"" + (profile.audio || "stereo") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_API_URL=\"" + (profile.sunshineApiUrl || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_USERNAME=\"" + (profile.sunshineUsername || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_PASSWORD=\"" + (profile.sunshinePassword || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_PIN=\"" + (profile.sunshinePin || "") + "\""
    ];
    return lines.join("\n") + "\n";
  }

  function buildNotes(profile) {
    var notes = [];
    if (!profile.streamHost) {
      notes.push("Kein Moonlight-/Sunshine-Ziel in der VM-Metadatenbeschreibung gefunden.");
    }
    if (!profile.sunshineApiUrl) {
      notes.push("Keine Sunshine API URL gesetzt. Pairing und Healthchecks koennen nicht vorab validiert werden.");
    }
    if (!profile.sunshinePassword) {
      notes.push("Kein Sunshine-Passwort hinterlegt. Fuer direkte API-Aktionen ist dann ein vorregistriertes Zertifikat oder manuelles Pairing noetig.");
    }
    if (!profile.guestIp) {
      notes.push("Keine Guest-Agent-IPv4 erkannt. Beagle kann dann nur mit Metadaten arbeiten.");
    }
    if (!notes.length) {
      notes.push("VM-Profil ist vollstaendig genug fuer einen vorkonfigurierten Beagle-Endpoint mit Moonlight-Autostart.");
    }
    if (profile.assignedTarget) {
      notes.push("Endpoint ist auf Ziel-VM " + profile.assignedTarget.name + " (#" + profile.assignedTarget.vmid + ") zugewiesen.");
    }
    if (profile.appliedPolicy && profile.appliedPolicy.name) {
      notes.push("Manager-Policy aktiv: " + profile.appliedPolicy.name + ".");
    }
    if (profile.compliance && profile.compliance.status === "drifted") {
      notes.push("Endpoint driftet vom gewuenschten Profil ab (" + String(profile.compliance.drift_count || 0) + " Abweichungen).");
    }
    if (profile.compliance && profile.compliance.status === "degraded") {
      notes.push("Endpoint ist konfigurationsgleich, aber betrieblich degradiert (" + String(profile.compliance.alert_count || 0) + " Warnungen).");
    }
    if (Number(profile.pendingActionCount || 0) > 0) {
      notes.push("Fuer diesen Endpoint warten " + String(profile.pendingActionCount) + " Beagle-Aktion(en) auf Ausfuehrung.");
    }
    if (profile.lastAction && profile.lastAction.action) {
      notes.push("Letzte Endpoint-Aktion: " + profile.lastAction.action + " (" + formatActionState(profile.lastAction.ok) + ").");
    }
    if (profile.lastAction && profile.lastAction.stored_artifact_path) {
      notes.push("Diagnoseartefakt ist zentral auf dem Beagle-Manager gespeichert.");
    }
    if (profile.installerPrep && profile.installerPrep.status === "ready") {
      notes.push("Installer-Vorbereitung ist bereits abgeschlossen. Der USB-Installer ist sofort freigegeben.");
    }
    return notes;
  }

  function formatActionState(ok) {
    if (ok === true) {
      return "ok";
    }
    if (ok === false) {
      return "error";
    }
    return "pending";
  }

  function renderStatusBadge(status) {
    var value = String(status || "unknown").toLowerCase();
    return '<span class="beagle-badge ' + escapeHtml(value) + '">' + escapeHtml(value) + '</span>';
  }

  function renderProvisioningBadge(state) {
    return '<span class="beagle-badge ' + provisioningStatusBadgeClass(state) + '">' + escapeHtml(provisioningStatusLabel(state)) + '</span>';
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
    return Array.prototype.slice.call(overlay.querySelectorAll('.beagle-row-select[data-vmid]:checked')).map(function(element) {
      return Number(element.getAttribute('data-vmid'));
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

  function queueBulkAction(vmids, actionName) {
    if (!vmids.length) {
      throw new Error('Keine Endpoints ausgewaehlt.');
    }
    return platformService.queueBulkAction(vmids, actionName);
  }

  function renderFleetModal(payload) {
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
        '  <td class="beagle-select-cell"><input class="beagle-row-select" type="checkbox" data-vmid="' + escapeHtml(String(item.vmid || "")) + '"></td>' +
        '  <td><strong>' + escapeHtml(item.name || ("vm-" + item.vmid)) + '</strong><br><span class="beagle-muted">#' + escapeHtml(String(item.vmid || "")) + ' / ' + escapeHtml(item.node || "") + '</span></td>' +
        '  <td>' + renderStatusBadge(item.compliance && item.compliance.status || "unknown") + '<br><span class="beagle-muted">' + escapeHtml(item.assignment_source || "unassigned") + '</span></td>' +
        '  <td>' + (provisioning ? renderProvisioningBadge(provisioning) + '<br><span class="beagle-muted">' + escapeHtml(String(provisioning.phase || "")) + '</span><br><span class="beagle-muted">' + escapeHtml(String(provisioning.hostname || "")) + '</span>' : '<span class="beagle-muted">kein Provisioning-State</span>') + '</td>' +
        '  <td>' + escapeHtml(item.assigned_target ? (item.assigned_target.name + " (#" + item.assigned_target.vmid + ")") : "") + '<br><span class="beagle-muted">' + escapeHtml(item.stream_host || "") + '</span></td>' +
        '  <td>' + escapeHtml(policyName || "keine") + '<br><span class="beagle-muted">Bundles: ' + escapeHtml(String(item.support_bundle_count || 0)) + '</span></td>' +
        '  <td>' + escapeHtml(item.endpoint && item.endpoint.reported_at || "") + '<br><span class="beagle-muted">Age: ' + escapeHtml(String(item.endpoint && item.endpoint.report_age_seconds || 0)) + 's</span><br><span class="beagle-muted">' + escapeHtml(lastAction.action || "") + " " + escapeHtml(formatActionState(lastAction.ok)) + '</span></td>' +
        '  <td><div class="beagle-inline-actions">' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="profile" data-vmid="' + escapeHtml(String(item.vmid || "")) + '" data-node="' + escapeHtml(item.node || "") + '">Profil</button>' +
        (String(item.beagle_role || "").toLowerCase() === 'desktop' ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="edit-desktop" data-vmid="' + escapeHtml(String(item.vmid || "")) + '" data-node="' + escapeHtml(item.node || "") + '">Bearbeiten</button>' : '') +
        (provisioning ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="copy-credentials" data-vmid="' + escapeHtml(String(item.vmid || "")) + '">Credentials</button>' : '') +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="healthcheck" data-vmid="' + escapeHtml(String(item.vmid || "")) + '">Check</button>' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="support-bundle" data-vmid="' + escapeHtml(String(item.vmid || "")) + '">Bundle</button>' +
        (bundleDownloadPath ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="download-bundle" data-bundle-path="' + escapeHtml(bundleDownloadPath) + '" data-bundle-name="vm-' + escapeHtml(String(item.vmid || "")) + '-support.tar.gz">Download</button>' : '') +
        (policyName ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="delete-policy" data-policy-name="' + escapeHtml(policyName) + '">Policy loeschen</button>' : (item.assigned_target ? '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="create-policy" data-vmid="' + escapeHtml(String(item.vmid || "")) + '">Zu Policy</button>' : '')) +
        '  </div></td>' +
        '</tr>';
    }).join("");
    var policyRows = policies.map(function(policy) {
      var selector = policy.selector || {};
      var profile = policy.profile || {};
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(policy.name || "") + '</strong></td>' +
        '  <td>' + escapeHtml(String(policy.priority || 0)) + '</td>' +
        '  <td>' + escapeHtml(selector.vmid ? ("VM " + selector.vmid) : "") + ' ' + escapeHtml(selector.node || "") + ' ' + escapeHtml(selector.role || "") + '</td>' +
        '  <td>' + escapeHtml(profile.expected_profile_name || "") + '<br><span class="beagle-muted">' + escapeHtml(profile.network_mode || "") + '</span></td>' +
        '  <td><button type="button" class="beagle-mini-btn" data-beagle-fleet-action="delete-policy" data-policy-name="' + escapeHtml(policy.name || "") + '">Loeschen</button></td>' +
        '</tr>';
    }).join("");
    var requestRows = requests.slice(0, 10).map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(String(item.name || ("vm-" + item.vmid))) + '</strong><br><span class="beagle-muted">#' + escapeHtml(String(item.vmid || "")) + ' / ' + escapeHtml(String(item.node || "")) + '</span></td>' +
        '  <td>' + renderProvisioningBadge(item) + '</td>' +
        '  <td>' + escapeHtml(String(item.phase || "")) + '<br><span class="beagle-muted">' + escapeHtml(String(item.message || "")) + '</span></td>' +
        '  <td>' + escapeHtml(String(item.created_at || "")) + '<br><span class="beagle-muted">' + escapeHtml(String(item.completed_at || item.updated_at || "")) + '</span></td>' +
        '  <td><div class="beagle-inline-actions">' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="request-profile" data-vmid="' + escapeHtml(String(item.vmid || "")) + '" data-node="' + escapeHtml(String(item.node || "")) + '">Profil</button>' +
        '    <button type="button" class="beagle-mini-btn" data-beagle-fleet-action="copy-credentials" data-vmid="' + escapeHtml(String(item.vmid || "")) + '">Credentials</button>' +
        '  </div></td>' +
        '</tr>';
    }).join("");
    var osProfileRows = osProfiles.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + escapeHtml(String(item.release || "")) + '</td>' +
        '  <td>' + escapeHtml(String(item.desktop || "")) + '</td>' +
        '  <td>' + escapeHtml(String(item.streaming || "")) + '</td>' +
        '  <td>' + escapeHtml(Array.isArray(item.features) ? item.features.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");
    var desktopProfileRows = desktopProfiles.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + escapeHtml(String(item.session || "")) + '</td>' +
        '  <td>' + escapeHtml(Array.isArray(item.packages) ? item.packages.join(", ") : "") + '</td>' +
        '  <td>' + escapeHtml(Array.isArray(item.features) ? item.features.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");
    var softwarePresetRows = softwarePresetCatalog.map(function(item) {
      return '' +
        '<tr>' +
        '  <td><strong>' + escapeHtml(String(item.label || item.id || "")) + '</strong><br><span class="beagle-muted">' + escapeHtml(String(item.id || "")) + '</span></td>' +
        '  <td>' + escapeHtml(String(item.description || "")) + '</td>' +
        '  <td>' + escapeHtml(Array.isArray(item.packages) ? item.packages.join(", ") : "") + '</td>' +
        '</tr>';
    }).join("");

    overlay.id = OVERLAY_ID;
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
                kvRow('Endpoints', escapeHtml(String(health.endpoint_count || 0))) +
                kvRow('Policies', escapeHtml(String(health.policy_count || 0))) +
                kvRow('Healthy', escapeHtml(String(endpointCounts.healthy || 0))) +
                kvRow('Pending', escapeHtml(String(endpointCounts.pending || 0))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Compliance</h3><div class="beagle-kv">' +
                kvRow('Stale', escapeHtml(String(endpointCounts.stale || 0))) +
                kvRow('Degraded', escapeHtml(String(endpointCounts.degraded || 0))) +
                kvRow('Drifted', escapeHtml(String(endpointCounts.drifted || 0))) +
                kvRow('Unmanaged', escapeHtml(String(endpointCounts.unmanaged || 0))) +
                kvRow('Generated', escapeHtml(health.generated_at || '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Provisioning</h3><div class="beagle-kv">' +
                kvRow('Next VMID', escapeHtml(String(defaults.next_vmid || ''))) +
                kvRow('Default Node', escapeHtml(String(defaults.node || ''))) +
                kvRow('Bridge', escapeHtml(String(defaults.bridge || ''))) +
                kvRow('Disk Storage', escapeHtml(String(defaults.disk_storage || ''))) +
                kvRow('ISO Storage', escapeHtml(String(defaults.iso_storage || ''))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Katalog</h3><div class="beagle-kv">' +
                kvRow('OS Profile', escapeHtml(String(osProfiles.length || 0))) +
                kvRow('Desktop Profile', escapeHtml(String(desktopProfiles.length || 0))) +
                kvRow('Software Presets', escapeHtml(String(softwarePresetCatalog.length || 0))) +
                kvRow('Nodes', escapeHtml(String(nodes.length || 0))) +
                kvRow('Image Storages', escapeHtml(String(imageStorages.length || 0))) +
                kvRow('ISO Storages', escapeHtml(String(isoStorages.length || 0))) +
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

    overlay.addEventListener('click', function(event) {
      var target;
      var item;
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
        return;
      }
      target = event.target instanceof HTMLElement ? event.target.closest('[data-beagle-fleet-action]') : null;
      if (!target) {
        return;
      }
      switch (target.getAttribute('data-beagle-fleet-action')) {
        case 'create-vm':
          removeOverlay();
          showUbuntuBeagleCreateModal({ node: String(defaults.node || selectedNodeName() || "") });
          break;
        case 'refresh':
          showFleetModal();
          break;
        case 'toggle-all':
          Array.prototype.slice.call(overlay.querySelectorAll('.beagle-row-select[data-vmid]')).forEach(function(checkbox) {
            checkbox.checked = target.checked;
          });
          break;
        case 'open-health':
          openUrl(resolveControlPlaneHealthUrl());
          break;
        case 'copy-policies':
          copyText(JSON.stringify(policies, null, 2), 'Beagle Policies kopiert.');
          break;
        case 'bulk-healthcheck':
        case 'bulk-support-bundle':
          queueBulkAction(selectedFleetVmids(overlay), target.getAttribute('data-beagle-fleet-action') === 'bulk-healthcheck' ? 'healthcheck' : 'support-bundle').then(function(result) {
            showToast('Beagle Bulk-Aktion gequeued: ' + String(result.queued_count || 0));
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'bulk-create-policy':
          Promise.all(selectedFleetItems(overlay, vms).map(function(item) {
            return platformService.createPolicy(createPolicyFromInventoryItem(item));
          })).then(function(result) {
            showToast('Beagle Policies erzeugt: ' + String(result.length || 0));
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'profile':
          showProfileModal({ vmid: Number(target.getAttribute('data-vmid')), node: target.getAttribute('data-node') });
          break;
        case 'edit-desktop':
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute('data-vmid')); });
          removeOverlay();
          showUbuntuBeagleCreateModal({ profile: item || { vmid: Number(target.getAttribute('data-vmid')), node: target.getAttribute('data-node') }, node: target.getAttribute('data-node') });
          break;
        case 'request-profile':
          showProfileModal({ vmid: Number(target.getAttribute('data-vmid')), node: target.getAttribute('data-node') });
          break;
        case 'copy-credentials':
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute('data-vmid')); }) ||
            requests.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute('data-vmid')); });
          apiGetProvisioningState(target.getAttribute('data-vmid')).then(function(state) {
            copyText(buildProvisioningCredentialText(item || {}, state || {}), 'Provisioning-Credentials kopiert.');
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'healthcheck':
        case 'support-bundle':
          platformService.queueVmAction(target.getAttribute('data-vmid'), target.getAttribute('data-beagle-fleet-action')).then(function() {
            showToast('Beagle Aktion wurde in die Queue gestellt.');
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'download-bundle':
          downloadProtectedFile('/beagle-api' + target.getAttribute('data-bundle-path'), target.getAttribute('data-bundle-name')).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'create-policy':
          item = vms.find(function(candidate) { return Number(candidate.vmid) === Number(target.getAttribute('data-vmid')); });
          platformService.createPolicy(createPolicyFromInventoryItem(item)).then(function() {
            showToast('Beagle Policy wurde erzeugt.');
            showFleetModal();
          }).catch(function(error) {
            showError(error.message);
          });
          break;
        case 'delete-policy':
          platformService.deletePolicy(target.getAttribute('data-policy-name')).then(function() {
            showToast('Beagle Policy wurde geloescht.');
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

  function showFleetModal() {
    ensureStyles();
    removeOverlay();
    if (!ensureApiToken()) {
      return;
    }
    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = '<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Fleet wird geladen</h2><p class="beagle-subtitle">Inventar, Policies und Endpoint-Zustand werden vom Manager geladen.</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Beagle Control Plane wird abgefragt.</div></div></div>';
    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);
    Promise.all([
      platformService.fetchHealth(),
      platformService.fetchInventory(),
      platformService.fetchPolicies(),
      apiGetProvisioningCatalog()
    ]).then(function(results) {
      removeOverlay();
      renderFleetModal({
        health: results[0] || {},
        vms: results[1] || [],
        policies: results[2] || [],
        catalog: results[3] || {}
      });
    }).catch(function(error) {
      removeOverlay();
      showError('Beagle Fleet konnte nicht geladen werden: ' + error.message);
    });
  }

  function resolveVmProfile(ctx) {
    return Promise.all([
      virtualizationService.getVmConfig(ctx),
      virtualizationService.listVms().catch(function() { return []; }),
      virtualizationService.getVmGuestInterfaces(ctx).catch(function() { return []; }),
      apiGetVmCredentials(ctx.vmid).catch(function() { return null; }),
      platformService.fetchPublicVmState(ctx.vmid),
      platformService.fetchVmUsbState(ctx.vmid).catch(function() { return null; })
    ]).then(function(results) {
      var config = results[0] || {};
      var resources = Array.isArray(results[1]) ? results[1] : [];
      var guestInterfaces = Array.isArray(results[2]) ? results[2] : [];
      var credentials = results[3] || null;
      var endpointPayload = results[4] || null;
      var usbPayload = results[5] || null;
      var controlPlaneProfile = endpointPayload && endpointPayload.profile ? endpointPayload.profile : null;
      var endpointSummary = endpointPayload && endpointPayload.endpoint ? endpointPayload.endpoint : null;
      var compliance = endpointPayload && endpointPayload.compliance ? endpointPayload.compliance : null;
      var lastAction = endpointPayload && endpointPayload.last_action ? endpointPayload.last_action : null;
      var pendingActionCount = endpointPayload && endpointPayload.pending_action_count ? endpointPayload.pending_action_count : 0;
      var installerPrep = endpointPayload && endpointPayload.installer_prep ? endpointPayload.installer_prep : null;
      var resource = resources.find(function(item) {
        return item && item.type === "qemu" && Number(item.vmid) === Number(ctx.vmid);
      }) || {};
      var meta = parseDescriptionMeta(config.description || "");
      var guestIp = firstGuestIpv4(guestInterfaces);
      var streamHost = controlPlaneProfile && controlPlaneProfile.stream_host || meta["moonlight-host"] || meta["sunshine-ip"] || meta["sunshine-host"] || guestIp || "";
      var moonlightPort = controlPlaneProfile && controlPlaneProfile.moonlight_port || meta["moonlight-port"] || meta["beagle-public-moonlight-port"] || "";
      var sunshineApiUrl = controlPlaneProfile && controlPlaneProfile.sunshine_api_url || meta["sunshine-api-url"] || (streamHost ? "https://" + streamHost + ":" + (moonlightPort ? String(Number(moonlightPort) + 1) : "47990") : "");
      var profile = {
        vmid: Number(ctx.vmid),
        node: ctx.node,
        name: config.name || resource.name || ("vm-" + ctx.vmid),
        status: resource.status || "unknown",
        guestIp: guestIp,
        streamHost: streamHost,
        moonlightPort: moonlightPort,
        sunshineApiUrl: sunshineApiUrl,
        sunshineUsername: credentials && credentials.sunshine_username || "",
        sunshinePassword: credentials && credentials.sunshine_password || "",
        sunshinePin: credentials && credentials.sunshine_pin || "",
        thinclientUsername: credentials && credentials.thinclient_username || "thinclient",
        thinclientPassword: credentials && credentials.thinclient_password || "",
        guestUser: controlPlaneProfile && controlPlaneProfile.guest_user || meta["sunshine-guest-user"] || "beagle",
        app: controlPlaneProfile && controlPlaneProfile.moonlight_app || meta["moonlight-app"] || meta["sunshine-app"] || "Desktop",
        resolution: controlPlaneProfile && controlPlaneProfile.moonlight_resolution || meta["moonlight-resolution"] || "auto",
        fps: controlPlaneProfile && controlPlaneProfile.moonlight_fps || meta["moonlight-fps"] || "60",
        bitrate: controlPlaneProfile && controlPlaneProfile.moonlight_bitrate || meta["moonlight-bitrate"] || "20000",
        codec: controlPlaneProfile && controlPlaneProfile.moonlight_video_codec || meta["moonlight-video-codec"] || "H.264",
        decoder: controlPlaneProfile && controlPlaneProfile.moonlight_video_decoder || meta["moonlight-video-decoder"] || "auto",
        audio: controlPlaneProfile && controlPlaneProfile.moonlight_audio_config || meta["moonlight-audio-config"] || "stereo",
        identityHostname: controlPlaneProfile && controlPlaneProfile.identity_hostname || meta["beagle-identity-hostname"] || "",
        desktopId: controlPlaneProfile && controlPlaneProfile.desktop_id || meta["beagle-desktop-id"] || "",
        desktopLabel: controlPlaneProfile && controlPlaneProfile.desktop_label || meta["beagle-desktop"] || "",
        desktopSession: controlPlaneProfile && controlPlaneProfile.desktop_session || meta["beagle-desktop-session"] || "",
        packagePresets: controlPlaneProfile && controlPlaneProfile.package_presets || parseListText(meta["beagle-package-presets"] || ""),
        extraPackages: controlPlaneProfile && controlPlaneProfile.extra_packages || parseListText(meta["beagle-extra-packages"] || ""),
        softwarePackages: controlPlaneProfile && controlPlaneProfile.software_packages || [],
        proxmoxHost: meta["proxmox-host"] || window.location.hostname,
        managerPinnedPubkey: controlPlaneProfile && controlPlaneProfile.beagle_manager_pinned_pubkey || "",
        installerUrl: controlPlaneProfile && controlPlaneProfile.installer_url || resolveUsbInstallerUrl(ctx),
        liveUsbUrl: controlPlaneProfile && controlPlaneProfile.live_usb_url || ("/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/live-usb.sh"),
        installerWindowsUrl: controlPlaneProfile && controlPlaneProfile.installer_windows_url || ("/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/installer.ps1"),
        installerIsoUrl: controlPlaneProfile && controlPlaneProfile.installer_iso_url || resolveInstallerIsoUrl(ctx),
        controlPlaneHealthUrl: resolveControlPlaneHealthUrl(),
        managerUrl: managerUrlFromHealthUrl(resolveControlPlaneHealthUrl()),
        endpointSummary: endpointSummary,
        usbState: usbPayload && usbPayload.usb ? usbPayload.usb : null,
        compliance: compliance,
        lastAction: lastAction,
        pendingActionCount: pendingActionCount,
        installerPrep: installerPrep,
        installerTargetEligible: controlPlaneProfile && typeof controlPlaneProfile.installer_target_eligible === "boolean" ? controlPlaneProfile.installer_target_eligible : Boolean(streamHost),
        installerTargetMessage: controlPlaneProfile && controlPlaneProfile.installer_target_message || "",
        assignedTarget: controlPlaneProfile && controlPlaneProfile.assigned_target || null,
        assignmentSource: controlPlaneProfile && controlPlaneProfile.assignment_source || "",
        appliedPolicy: controlPlaneProfile && controlPlaneProfile.applied_policy || null,
        beagleRole: controlPlaneProfile && controlPlaneProfile.beagle_role || meta["beagle-role"] || "",
        expectedProfileName: controlPlaneProfile && controlPlaneProfile.expected_profile_name || "",
        metadata: meta
      };
      profile.notes = buildNotes(profile);
      if (!profile.endpointSummary) {
        profile.notes.push("Endpoint hat noch keinen Check-in an die Beagle Control Plane geliefert.");
      }
      profile.endpointEnv = buildEndpointEnv(profile);
      return profile;
    });
  }

  function kvRow(label, value) {
    return renderHelpers.kvRow(label, value);
  }

  function escapeHtml(text) {
    return renderHelpers.escapeHtml(text);
  }

  function renderDesktopOverlay(profile) {
    return desktopOverlay.renderDesktopOverlay({
      overlayId: OVERLAY_ID,
      profile: profile,
      removeOverlay: removeOverlay,
      showProfileModal: renderProfileModal
    });
  }

  function renderProfileModal(profile, options) {
    var overlay = document.createElement("div");
    var usbState = profile.usbState || {};
    var usbDevices = Array.isArray(usbState.devices) ? usbState.devices : [];
    var usbAttached = Array.isArray(usbState.attached) ? usbState.attached : [];
    var notesHtml = profile.notes.map(function(note) {
      return "<li>" + escapeHtml(note) + "</li>";
    }).join("");
    var installerPrep = profile.installerPrep || {
      status: "idle",
      phase: "inspect",
      progress: 0,
      message: "Download startet zuerst die Sunshine-Pruefung und die Stream-Vorbereitung fuer diese VM.",
      sunshine_status: { binary: false, service: false, process: false }
    };
    var profileJson = JSON.stringify({
      vmid: profile.vmid,
      node: profile.node,
      name: profile.name,
      status: profile.status,
      stream_host: profile.streamHost,
      sunshine_api_url: profile.sunshineApiUrl,
      sunshine_username: profile.sunshineUsername,
      sunshine_password_configured: Boolean(profile.sunshinePassword),
      sunshine_pin: profile.sunshinePin,
      guest_user: profile.guestUser,
      desktop_id: profile.desktopId,
      desktop_label: profile.desktopLabel,
      desktop_session: profile.desktopSession,
      package_presets: profile.packagePresets,
      extra_packages: profile.extraPackages,
      software_packages: profile.softwarePackages,
      identity_locale: profile.identityLocale,
      identity_keymap: profile.identityKeymap,
      moonlight_app: profile.app,
      moonlight_resolution: profile.resolution,
      moonlight_fps: profile.fps,
      moonlight_bitrate: profile.bitrate,
      moonlight_video_codec: profile.codec,
      moonlight_video_decoder: profile.decoder,
      moonlight_audio_config: profile.audio,
      manager_url: profile.managerUrl,
      installer_url: profile.installerUrl,
      live_usb_url: profile.liveUsbUrl,
      installer_windows_url: profile.installerWindowsUrl,
      installer_iso_url: profile.installerIsoUrl,
      control_plane_health_url: profile.controlPlaneHealthUrl,
      assigned_target: profile.assignedTarget,
      assignment_source: profile.assignmentSource,
      applied_policy: profile.appliedPolicy,
      expected_profile_name: profile.expectedProfileName,
      endpoint_summary: profile.endpointSummary,
      compliance: profile.compliance,
      last_action: profile.lastAction,
      pending_action_count: profile.pendingActionCount,
      installer_prep: installerPrep,
      installer_target_eligible: profile.installerTargetEligible,
      installer_target_message: profile.installerTargetMessage,
      usb_state: usbState
    }, null, 2);
    var usbDevicesHtml = usbDevices.length ? usbDevices.map(function(device) {
      var busid = String(device.busid || "");
      return '<div class="beagle-kv-row"><strong>' + escapeHtml(busid) + '</strong><span>' + escapeHtml(device.description || "") + '</span><span>' +
        '<button type="button" class="beagle-mini-btn" data-beagle-action="usb-attach" data-beagle-usb-busid="' + escapeHtml(busid) + '">Attach</button>' +
        (device.bound ? ' <span class="beagle-muted">exported</span>' : '') +
      '</span></div>';
    }).join("") : '<div class="beagle-kv-row"><strong>USB</strong><span class="beagle-muted">Keine exportierbaren USB-Geraete gemeldet.</span></div>';
    var usbAttachedHtml = usbAttached.length ? usbAttached.map(function(item) {
      var busid = String(item.busid || "");
      var port = String(item.port || "");
      return '<div class="beagle-kv-row"><strong>Port ' + escapeHtml(port) + '</strong><span>' + escapeHtml(busid || item.device || "") + '</span><span>' +
        '<button type="button" class="beagle-mini-btn" data-beagle-action="usb-detach" data-beagle-usb-busid="' + escapeHtml(busid) + '" data-beagle-usb-port="' + escapeHtml(port) + '">Detach</button>' +
      '</span></div>';
    }).join("") : '<div class="beagle-kv-row"><strong>USB</strong><span class="beagle-muted">Keine USB-Geraete in der VM angehaengt.</span></div>';

    overlay.id = OVERLAY_ID;
    overlay.innerHTML = '' +
      '<div class="beagle-modal" role="dialog" aria-modal="true" aria-label="Beagle OS Profil">' +
      '  <div class="beagle-header">' +
      '    <div>' +
      '      <h2 class="beagle-title">Beagle Profil fuer VM ' + escapeHtml(profile.name) + ' (#' + String(profile.vmid) + ')</h2>' +
      '      <p class="beagle-subtitle">Moonlight-Endpunkt, Sunshine-Ziel und Proxmox-Bereitstellung in einer Sicht.</p>' +
      '    </div>' +
      '    <button type="button" class="beagle-close" aria-label="Schliessen">×</button>' +
      '  </div>' +
      '  <div class="beagle-body">' +
      '    <div class="beagle-banner ' + (profile.streamHost ? 'info' : 'warn') + '">' + escapeHtml(profile.streamHost ? 'Streaming-Ziel erkannt: ' + profile.streamHost : 'Streaming-Ziel fehlt in den VM-Metadaten.') + '</div>' +
      '    <div class="beagle-banner ' + installerTargetState(profile, installerPrep).bannerClass + '" data-beagle-download-banner><strong data-beagle-download-state>' + escapeHtml(installerTargetState(profile, installerPrep).label) + '</strong>: <span data-beagle-download-message>' + escapeHtml(installerTargetState(profile, installerPrep).message) + '</span></div>' +
      '    <div class="beagle-actions">' +
      (String(profile.beagleRole || "").toLowerCase() === 'desktop' ? '      <button type="button" class="beagle-btn primary" data-beagle-action="edit-desktop">Desktop bearbeiten</button>' : '') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn primary" data-beagle-action="download">USB Installer Skript</button>') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-live">Live USB Skript</button>') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-windows">Windows USB Installer</button>') +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-iso">ISO Download</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-web-ui">Open Web UI</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="copy-json">Profil JSON kopieren</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="copy-env">Endpoint Env kopieren</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-sunshine">Sunshine Web UI</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="usb-refresh">USB Refresh</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-health">Control Plane Status</button>' +
      '    </div>' +
      '    <div class="beagle-grid">' +
      '      <section class="beagle-card"><h3>VM</h3><div class="beagle-kv">' +
                kvRow('Name', escapeHtml(profile.name)) +
                kvRow('VMID', escapeHtml(String(profile.vmid))) +
                kvRow('Node', escapeHtml(profile.node)) +
                kvRow('Status', escapeHtml(profile.status)) +
                kvRow('Guest IP', escapeHtml(profile.guestIp || '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Desktop</h3><div class="beagle-kv">' +
                kvRow('Desktop', escapeHtml(profile.desktopLabel || profile.desktopId || '')) +
                kvRow('Session', escapeHtml(profile.desktopSession || '')) +
                kvRow('Gast-User', escapeHtml(profile.guestUser || '')) +
                kvRow('Locale', escapeHtml(profile.identityLocale || '')) +
                kvRow('Keymap', escapeHtml(profile.identityKeymap || '')) +
                kvRow('Paket-Presets', escapeHtml((profile.packagePresets || []).join(', '))) +
                kvRow('Weitere Pakete', escapeHtml((profile.extraPackages || []).join(', '))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Streaming</h3><div class="beagle-kv">' +
                kvRow('Stream Host', escapeHtml(profile.streamHost || '')) +
                kvRow('Moonlight Port', escapeHtml(profile.moonlightPort || 'default')) +
                kvRow('Sunshine API', escapeHtml(profile.sunshineApiUrl || '')) +
                kvRow('App', escapeHtml(profile.app)) +
                kvRow('Manager', escapeHtml(profile.managerUrl || '')) +
                kvRow('Assigned Target', escapeHtml(profile.assignedTarget ? (profile.assignedTarget.name + " (#" + profile.assignedTarget.vmid + ")") : '')) +
                kvRow('Assignment Source', escapeHtml(profile.assignmentSource || '')) +
                kvRow('Applied Policy', escapeHtml(profile.appliedPolicy && profile.appliedPolicy.name || '')) +
                kvRow('USB Script', escapeHtml(profile.installerUrl)) +
                kvRow('Live USB Script', escapeHtml(profile.liveUsbUrl)) +
                kvRow('Windows USB Script', escapeHtml(profile.installerWindowsUrl)) +
                kvRow('Installer ISO', escapeHtml(profile.installerIsoUrl)) +
                kvRow('Health', escapeHtml(profile.controlPlaneHealthUrl)) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Endpoint Defaults</h3><div class="beagle-kv">' +
                kvRow('Resolution', escapeHtml(profile.resolution)) +
                kvRow('FPS', escapeHtml(profile.fps)) +
                kvRow('Bitrate', escapeHtml(profile.bitrate)) +
                kvRow('Codec', escapeHtml(profile.codec)) +
                kvRow('Decoder', escapeHtml(profile.decoder)) +
                kvRow('Audio', escapeHtml(profile.audio)) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Credentials</h3><div class="beagle-kv">' +
                kvRow('Thin Client User', escapeHtml(profile.thinclientUsername || 'thinclient')) +
                kvRow('Thin Client Password', escapeHtml(profile.thinclientPassword || '')) +
                kvRow('Sunshine User', escapeHtml(profile.sunshineUsername || '')) +
                kvRow('Sunshine Password', escapeHtml(profile.sunshinePassword || '')) +
                kvRow('Pairing PIN', escapeHtml(profile.sunshinePin || '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Endpoint State</h3><div class="beagle-kv">' +
                kvRow('Compliance', escapeHtml(profile.compliance && profile.compliance.status || '')) +
                kvRow('Drift Count', escapeHtml(profile.compliance ? String(profile.compliance.drift_count || 0) : '')) +
                kvRow('Alert Count', escapeHtml(profile.compliance ? String(profile.compliance.alert_count || 0) : '')) +
                kvRow('Pending Actions', escapeHtml(String(profile.pendingActionCount || 0))) +
                kvRow('Last Seen', escapeHtml(profile.endpointSummary && profile.endpointSummary.reported_at || '')) +
                kvRow('Target Reachable', escapeHtml(profile.endpointSummary && profile.endpointSummary.moonlight_target_reachable || '')) +
                kvRow('Sunshine Reachable', escapeHtml(profile.endpointSummary && profile.endpointSummary.sunshine_api_reachable || '')) +
                kvRow('Prepare', escapeHtml(profile.endpointSummary && profile.endpointSummary.prepare_state || '')) +
                kvRow('Last Launch', escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_mode || '')) +
                kvRow('Launch Target', escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_target || '')) +
                kvRow('Last Action', escapeHtml(profile.lastAction && profile.lastAction.action || '')) +
                kvRow('Action Result', escapeHtml(formatActionState(profile.lastAction && profile.lastAction.ok))) +
                kvRow('Action Time', escapeHtml(profile.lastAction && profile.lastAction.completed_at || '')) +
                kvRow('Action Message', escapeHtml(profile.lastAction && profile.lastAction.message || '')) +
                kvRow('Stored Artifact', escapeHtml(profile.lastAction && profile.lastAction.stored_artifact_path || '')) +
                kvRow('Artifact Size', escapeHtml(profile.lastAction ? String(profile.lastAction.stored_artifact_size || 0) : '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>USB Tunnel</h3><div class="beagle-kv">' +
                kvRow('Tunnel State', escapeHtml(usbState.tunnel_state || '')) +
                kvRow('Tunnel Host', escapeHtml(usbState.tunnel_host || '')) +
                kvRow('Tunnel Port', escapeHtml(String(usbState.tunnel_port || ''))) +
                kvRow('Exportable', escapeHtml(String(usbState.device_count || 0))) +
                kvRow('Attached in VM', escapeHtml(String(usbState.attached_count || 0))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Installer Readiness</h3><div class="beagle-kv">' +
                kvRow('Status', '<span data-beagle-installer-status>' + escapeHtml(installerPrep.status || 'idle') + '</span>') +
                kvRow('Zielstatus', '<span data-beagle-download-state>' + escapeHtml(installerTargetState(profile, installerPrep).label) + '</span>') +
                kvRow('Phase', '<span data-beagle-installer-phase>' + escapeHtml(installerPrep.phase || 'inspect') + '</span>') +
                kvRow('Progress', '<span data-beagle-installer-progress>' + escapeHtml(String(installerPrep.progress || 0)) + '%</span>') +
                kvRow('Message', '<span data-beagle-installer-message>' + escapeHtml(installerPrep.message || '') + '</span>') +
                kvRow('Sunshine Binary', '<span data-beagle-installer-binary>' + escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.binary ? 'ok' : 'missing') + '</span>') +
                kvRow('Sunshine Service', '<span data-beagle-installer-service>' + escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.service ? 'active' : 'inactive') + '</span>') +
                kvRow('Sunshine Process', '<span data-beagle-installer-process>' + escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.process ? 'running' : 'stopped') + '</span>') +
      '      </div></section>' +
      '    </div>' +
      '    <section class="beagle-card"><h3>USB-Geraete vom Thin Client</h3><div class="beagle-kv">' + usbDevicesHtml + '</div></section>' +
      '    <section class="beagle-card"><h3>USB-Geraete in der VM</h3><div class="beagle-kv">' + usbAttachedHtml + '</div></section>' +
      '    <section class="beagle-card"><h3>Operator Notes</h3><ul class="beagle-notes">' + notesHtml + '</ul></section>' +
      '    <section class="beagle-card"><h3>Beagle Endpoint Env</h3><textarea class="beagle-code" readonly>' + escapeHtml(profile.endpointEnv) + '</textarea></section>' +
      '    <section class="beagle-card"><h3>Profile JSON</h3><textarea class="beagle-code" readonly>' + escapeHtml(profileJson) + '</textarea></section>' +
      '  </div>' +
      '</div>';

    overlay.__beagleProfile = profile;
    syncInstallerButtons(overlay, installerPrep);

    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
        return;
      }

      if (!(event.target instanceof HTMLElement)) {
        return;
      }

      switch (event.target.getAttribute('data-beagle-action')) {
        case 'edit-desktop':
          removeOverlay();
          showUbuntuBeagleCreateModal({ profile: profile, node: profile.node });
          break;
        case 'download':
          prepareInstallerDownload(profile, overlay, 'installerUrl', 'download', 'Installer wird vorbereitet', 'Beagle USB Installer Skript wird heruntergeladen.');
          break;
        case 'download-live':
          prepareInstallerDownload(profile, overlay, 'liveUsbUrl', 'download-live', 'Live USB wird vorbereitet', 'Beagle Live USB Skript wird heruntergeladen.', 'pve-thin-client-live-usb-vm-' + profile.vmid + '.sh');
          break;
        case 'download-windows':
          prepareInstallerDownload(profile, overlay, 'installerWindowsUrl', 'download-windows', 'Windows Installer wird vorbereitet', 'Beagle Windows USB Installer wird heruntergeladen.');
          break;
        case 'download-iso':
          openUrl(withNoCache(profile.installerIsoUrl));
          break;
        case 'open-web-ui':
          openUrl(webUiUrlWithToken(true));
          break;
        case 'copy-json':
          copyText(profileJson, 'Beagle Profil als JSON kopiert.');
          break;
        case 'copy-env':
          copyText(profile.endpointEnv, 'Beagle Endpoint-Umgebung kopiert.');
          break;
        case 'open-sunshine':
          apiCreateSunshineAccess(profile.vmid).then(function(access) {
            openUrl(access && access.url ? access.url : profile.sunshineApiUrl);
          }).catch(function(error) {
            showError("Sunshine Web UI konnte nicht geoeffnet werden: " + (error && error.message ? error.message : error));
          });
          break;
        case 'usb-refresh':
          platformService.refreshVmUsb(profile.vmid).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Refresh fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case 'usb-attach':
          platformService.attachUsb(profile.vmid, event.target.getAttribute("data-beagle-usb-busid")).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Attach fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case 'usb-detach':
          platformService.detachUsb(profile.vmid, event.target.getAttribute("data-beagle-usb-busid"), event.target.getAttribute("data-beagle-usb-port")).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Detach fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case 'open-health':
          openUrl(profile.controlPlaneHealthUrl);
          break;
        default:
          break;
      }
    });

    document.body.appendChild(overlay);
    applyInstallerPrepState(overlay, installerPrep);
    if (options && options.autoPrepareDownload) {
      prepareInstallerDownload(profile, overlay, 'installerUrl', 'download', 'Installer wird vorbereitet', 'Beagle USB Installer Skript wird heruntergeladen.');
    }
  }

  function showProfileModal(ctx, options) {
    ensureStyles();
    removeOverlay();

    var overlay = document.createElement('div');
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = '<div class="beagle-modal"><div class="beagle-header"><div><h2 class="beagle-title">Beagle Profil wird geladen</h2><p class="beagle-subtitle">VM ' + String(ctx.vmid) + ' auf Node ' + escapeHtml(ctx.node || '') + '</p></div><button type="button" class="beagle-close" aria-label="Schliessen">×</button></div><div class="beagle-body"><div class="beagle-banner info">Proxmox-Konfiguration, Guest-Agent-Daten und Beagle-Metadaten werden aufgeloest.</div></div></div>';
    overlay.addEventListener('click', function(event) {
      if (event.target === overlay || event.target.closest('.beagle-close')) {
        removeOverlay();
      }
    });
    document.body.appendChild(overlay);

    resolveVmProfile(ctx).then(function(profile) {
      removeOverlay();
      if (options && options.showDetails) {
        renderProfileModal(profile, options);
      } else {
        renderDesktopOverlay(profile);
      }
    }).catch(function(error) {
      removeOverlay();
      showError('Beagle Profil konnte nicht geladen werden: ' + error.message);
    });
  }

  function ensureConsoleButtonIntegration(button) {
    if (!button || !button.vmid || button.consoleType !== "kvm" || button.__beagleIntegrated) {
      return;
    }

    var menu = button.getMenu ? button.getMenu() : button.menu;
    if (menu && !menu.down("#beagleOsProfileMenuItem")) {
      menu.add({
        itemId: "beagleOsProfileMenuItem",
        text: PRODUCT_LABEL + " Profil",
        iconCls: "fa fa-desktop",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid });
        }
      });
    }

    if (menu) {
      getVmInstallerEligibility({ node: button.nodename, vmid: button.vmid }).then(function(result) {
        var existingInstallerItem = menu.down("#beagleOsInstallerMenuItem");
        if (result && result.eligible) {
          if (!existingInstallerItem) {
            menu.add({
              itemId: "beagleOsInstallerMenuItem",
              text: PRODUCT_LABEL + " Installer",
              iconCls: "fa fa-usb",
              handler: function() {
                openUsbInstaller({ node: button.nodename, vmid: button.vmid });
              }
            });
          }
          return;
        }
        if (existingInstallerItem) {
          menu.remove(existingInstallerItem);
        }
      });
    }

    var toolbar = button.up && button.up("toolbar");
    if (toolbar && !toolbar.down("#beagleOsButton")) {
      var index = toolbar.items.indexOf(button);
      toolbar.insert(index + 1, {
        xtype: "button",
        itemId: "beagleOsButton",
        text: PRODUCT_LABEL,
        iconCls: "fa fa-desktop",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid });
        },
        tooltip: "Zeigt das aufgeloeste Beagle-Profil fuer diese VM und bietet Download-, Export- und Health-Aktionen."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsDetailsButton")) {
      var detailsIndex = toolbar.items.indexOf(button);
      toolbar.insert(detailsIndex + 2, {
        xtype: "button",
        itemId: "beagleOsDetailsButton",
        text: PRODUCT_LABEL + " Details",
        iconCls: "fa fa-info-circle",
        handler: function() {
          showProfileModal({ node: button.nodename, vmid: button.vmid }, { showDetails: true });
        },
        tooltip: "Zeigt das technische Beagle-Profil mit allen Details fuer diese VM."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsWebUIButton")) {
      var webIndex = toolbar.items.indexOf(button);
      toolbar.insert(webIndex + 3, {
        xtype: "button",
        itemId: "beagleOsWebUIButton",
        text: "Beagle Web UI",
        iconCls: "fa fa-globe",
        handler: function() {
          openUrl(webUiUrlWithToken(true));
        },
        tooltip: "Oeffnet die zentrale Beagle Web UI auf diesem Host."
      });
    }

    button.__beagleIntegrated = true;
  }

  function ensureFleetLauncher() {
    ensureStyles();
    if (document.getElementById(FLEET_LAUNCHER_ID)) {
      return;
    }
    var button = document.createElement('button');
    button.id = FLEET_LAUNCHER_ID;
    button.type = 'button';
    button.textContent = 'Beagle Fleet';
    button.addEventListener('click', function() {
      showFleetModal();
    });
    document.body.appendChild(button);
  }

  function findCreateVmToolbarAnchor() {
    var labels = createVmLabels();
    var textNodes = Array.prototype.slice.call(document.querySelectorAll(".x-toolbar .x-btn-inner"));
    for (var index = 0; index < textNodes.length; index += 1) {
      var textNode = textNodes[index];
      var normalized = normalizeUiText(textNode.textContent || textNode.innerText || "");
      if (labels.indexOf(normalized) === -1) {
        continue;
      }
      var button = textNode.closest(".x-btn");
      if (button && button.id !== CREATE_VM_DOM_BUTTON_ID) {
        return button;
      }
    }
    return null;
  }

  function toolbarHasBeagleCreateVmButton(toolbar) {
    if (!toolbar) {
      return false;
    }
    var textNodes = Array.prototype.slice.call(toolbar.querySelectorAll(".x-btn-inner"));
    return textNodes.some(function(node) {
      return normalizeUiText(node.textContent || node.innerText || "") === normalizeUiText("Erstelle Beagle OS VM");
    });
  }

  function ensureCreateVmDomFallback() {
    var anchor = findCreateVmToolbarAnchor();
    var existing = document.getElementById(CREATE_VM_DOM_BUTTON_ID);
    if (!anchor) {
      if (existing) {
        existing.remove();
      }
      return;
    }

    var toolbar = anchor.parentElement;
    if (!toolbar) {
      return;
    }

    if (toolbarHasBeagleCreateVmButton(toolbar) && (!existing || existing.parentElement === toolbar)) {
      if (existing && existing.parentElement !== toolbar) {
        existing.remove();
      }
      return;
    }

    if (!existing) {
      existing = anchor.cloneNode(true);
      existing.id = CREATE_VM_DOM_BUTTON_ID;
      existing.setAttribute("data-beagle-create-vm-dom", "1");
      existing.removeAttribute("aria-describedby");
      existing.removeAttribute("data-componentid");
      existing.style.width = "auto";
      var inner = existing.querySelector(".x-btn-inner");
      if (inner) {
        inner.textContent = "Erstelle Beagle OS VM";
      } else {
        existing.textContent = "Erstelle Beagle OS VM";
      }
      existing.title = "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine.";
      existing.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
        showUbuntuBeagleCreateModal({ node: selectedNodeName() || "" });
      });
    }

    if (existing.parentElement !== toolbar || existing.nextSibling !== anchor) {
      toolbar.insertBefore(existing, anchor);
    }
  }

  function ensureCreateVmIntegration(component) {
    if (!component || component.__beagleUbuntuCreateIntegrated) {
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("menu")) {
      var menu = component.up("menu");
      if (!menu.down("#beagleUbuntuCreateVmMenuItem")) {
        menu.insert(menu.items.indexOf(component), {
          itemId: "beagleUbuntuCreateVmMenuItem",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            showUbuntuBeagleCreateModal({ node: menu.nodename || selectedNodeName() || "" });
          }
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("toolbar")) {
      var toolbar = component.up && component.up("toolbar");
      if (toolbar && !toolbar.down("#beagleUbuntuCreateVmButton")) {
        toolbar.insert(toolbar.items.indexOf(component), {
          xtype: "button",
          itemId: "beagleUbuntuCreateVmButton",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            showUbuntuBeagleCreateModal({ node: selectedNodeName() || "" });
          },
          tooltip: "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine."
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
    }
  }

  function integrate() {
    if (!(window.Ext && Ext.ComponentQuery)) {
      return;
    }

    Ext.ComponentQuery.query("pveConsoleButton").forEach(ensureConsoleButtonIntegration);
    Ext.ComponentQuery.query("#createvm").forEach(ensureCreateVmIntegration);
    Ext.ComponentQuery.query("button").forEach(ensureCreateVmIntegration);
    Ext.ComponentQuery.query("menuitem").forEach(ensureCreateVmIntegration);
    ensureFleetLauncher();
    ensureCreateVmDomFallback();
  }

  function boot() {
    ensureStyles();
    integrate();
    window.setInterval(integrate, 1000);
  }

  if (window.Ext && Ext.onReady) {
    Ext.onReady(boot);
  } else {
    boot();
  }
})();

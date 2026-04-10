(function() {
  "use strict";

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

  function showUbuntuBeagleCreateModal(options) {
    var ctx = options.ctx || {};
    var showError = options.showError;
    var showToast = options.showToast;
    var ensureApiToken = options.ensureApiToken;
    var apiGetProvisioningCatalog = options.apiGetProvisioningCatalog;
    var apiCreateProvisionedVm = options.apiCreateProvisionedVm;
    var apiUpdateProvisionedVm = options.apiUpdateProvisionedVm;
    var virtualizationService = options.virtualizationService;
    var selectedNodeName = options.selectedNodeName;
    var parseListText = options.parseListText;
    var showProfileModal = options.showProfileModal;
    var showProvisioningResultWindow = options.showProvisioningResultWindow;

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

  window.BeagleUiProvisioningCreateModal = {
    showUbuntuBeagleCreateModal: showUbuntuBeagleCreateModal
  };
})();

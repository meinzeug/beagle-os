(function() {
  "use strict";

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

  function ensureConsoleButtonIntegration(button, options) {
    var menu;
    var toolbar;

    if (!button || !button.vmid || button.consoleType !== "kvm" || button.__beagleIntegrated) {
      return;
    }

    menu = button.getMenu ? button.getMenu() : button.menu;
    if (menu && !menu.down("#beagleOsProfileMenuItem")) {
      menu.add({
        itemId: "beagleOsProfileMenuItem",
        text: options.productLabel + " Profil",
        iconCls: "fa fa-desktop",
        handler: function() {
          options.showProfileModal({ node: button.nodename, vmid: button.vmid });
        }
      });
    }

    if (menu) {
      options.getVmInstallerEligibility({ node: button.nodename, vmid: button.vmid }).then(function(result) {
        var existingInstallerItem = menu.down("#beagleOsInstallerMenuItem");
        if (result && result.eligible) {
          if (!existingInstallerItem) {
            menu.add({
              itemId: "beagleOsInstallerMenuItem",
              text: options.productLabel + " Installer",
              iconCls: "fa fa-usb",
              handler: function() {
                options.openUsbInstaller({ node: button.nodename, vmid: button.vmid });
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

    toolbar = button.up && button.up("toolbar");
    if (toolbar && !toolbar.down("#beagleOsButton")) {
      toolbar.insert(toolbar.items.indexOf(button) + 1, {
        xtype: "button",
        itemId: "beagleOsButton",
        text: options.productLabel,
        iconCls: "fa fa-desktop",
        handler: function() {
          options.showProfileModal({ node: button.nodename, vmid: button.vmid });
        },
        tooltip: "Zeigt das aufgeloeste Beagle-Profil fuer diese VM und bietet Download-, Export- und Health-Aktionen."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsDetailsButton")) {
      toolbar.insert(toolbar.items.indexOf(button) + 2, {
        xtype: "button",
        itemId: "beagleOsDetailsButton",
        text: options.productLabel + " Details",
        iconCls: "fa fa-info-circle",
        handler: function() {
          options.showProfileModal({ node: button.nodename, vmid: button.vmid }, { showDetails: true });
        },
        tooltip: "Zeigt das technische Beagle-Profil mit allen Details fuer diese VM."
      });
    }
    if (toolbar && !toolbar.down("#beagleOsWebUIButton")) {
      toolbar.insert(toolbar.items.indexOf(button) + 3, {
        xtype: "button",
        itemId: "beagleOsWebUIButton",
        text: "Beagle Web UI",
        iconCls: "fa fa-globe",
        handler: function() {
          options.openUrl(options.webUiUrlWithToken(true));
        },
        tooltip: "Oeffnet die zentrale Beagle Web UI auf diesem Host."
      });
    }

    button.__beagleIntegrated = true;
  }

  function ensureFleetLauncher(options) {
    var button;

    options.ensureStyles();
    if (document.getElementById(options.fleetLauncherId)) {
      return;
    }
    button = document.createElement("button");
    button.id = options.fleetLauncherId;
    button.type = "button";
    button.textContent = "Beagle Fleet";
    button.addEventListener("click", function() {
      options.showFleetModal();
    });
    document.body.appendChild(button);
  }

  function findCreateVmToolbarAnchor(createVmDomButtonId) {
    var labels = createVmLabels();
    var textNodes = Array.prototype.slice.call(document.querySelectorAll(".x-toolbar .x-btn-inner"));
    var index;
    var textNode;
    var normalized;
    var button;

    for (index = 0; index < textNodes.length; index += 1) {
      textNode = textNodes[index];
      normalized = normalizeUiText(textNode.textContent || textNode.innerText || "");
      if (labels.indexOf(normalized) === -1) {
        continue;
      }
      button = textNode.closest(".x-btn");
      if (button && button.id !== createVmDomButtonId) {
        return button;
      }
    }
    return null;
  }

  function toolbarHasBeagleCreateVmButton(toolbar) {
    if (!toolbar) {
      return false;
    }
    return Array.prototype.slice.call(toolbar.querySelectorAll(".x-btn-inner")).some(function(node) {
      return normalizeUiText(node.textContent || node.innerText || "") === normalizeUiText("Erstelle Beagle OS VM");
    });
  }

  function ensureCreateVmDomFallback(options) {
    var anchor = findCreateVmToolbarAnchor(options.createVmDomButtonId);
    var existing = document.getElementById(options.createVmDomButtonId);
    var toolbar;
    var inner;

    if (!anchor) {
      if (existing) {
        existing.remove();
      }
      return;
    }

    toolbar = anchor.parentElement;
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
      existing.id = options.createVmDomButtonId;
      existing.setAttribute("data-beagle-create-vm-dom", "1");
      existing.removeAttribute("aria-describedby");
      existing.removeAttribute("data-componentid");
      existing.style.width = "auto";
      inner = existing.querySelector(".x-btn-inner");
      if (inner) {
        inner.textContent = "Erstelle Beagle OS VM";
      } else {
        existing.textContent = "Erstelle Beagle OS VM";
      }
      existing.title = "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine.";
      existing.addEventListener("click", function(event) {
        event.preventDefault();
        event.stopPropagation();
        options.showUbuntuBeagleCreateModal({ node: options.selectedNodeName() || "" });
      });
    }

    if (existing.parentElement !== toolbar || existing.nextSibling !== anchor) {
      toolbar.insertBefore(existing, anchor);
    }
  }

  function ensureCreateVmIntegration(component, options) {
    var menu;
    var toolbar;

    if (!component || component.__beagleUbuntuCreateIntegrated) {
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("menu")) {
      menu = component.up("menu");
      if (!menu.down("#beagleUbuntuCreateVmMenuItem")) {
        menu.insert(menu.items.indexOf(component), {
          itemId: "beagleUbuntuCreateVmMenuItem",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            options.showUbuntuBeagleCreateModal({ node: menu.nodename || options.selectedNodeName() || "" });
          }
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
      return;
    }

    if (looksLikeCreateVmTrigger(component) && component.up && component.up("toolbar")) {
      toolbar = component.up("toolbar");
      if (toolbar && !toolbar.down("#beagleUbuntuCreateVmButton")) {
        toolbar.insert(toolbar.items.indexOf(component), {
          xtype: "button",
          itemId: "beagleUbuntuCreateVmButton",
          text: "Erstelle Beagle OS VM",
          iconCls: "fa fa-television",
          handler: function() {
            options.showUbuntuBeagleCreateModal({ node: options.selectedNodeName() || "" });
          },
          tooltip: "Erstellt eine vorbereitete Ubuntu-Desktop-VM mit Beagle OS und Sunshine."
        });
      }
      component.__beagleUbuntuCreateIntegrated = true;
    }
  }

  function integrate(options) {
    if (!(window.Ext && Ext.ComponentQuery)) {
      return;
    }

    Ext.ComponentQuery.query("pveConsoleButton").forEach(function(button) {
      ensureConsoleButtonIntegration(button, options);
    });
    Ext.ComponentQuery.query("#createvm").forEach(function(component) {
      ensureCreateVmIntegration(component, options);
    });
    Ext.ComponentQuery.query("button").forEach(function(component) {
      ensureCreateVmIntegration(component, options);
    });
    Ext.ComponentQuery.query("menuitem").forEach(function(component) {
      ensureCreateVmIntegration(component, options);
    });
    ensureFleetLauncher(options);
    ensureCreateVmDomFallback(options);
  }

  function boot(options) {
    options.ensureStyles();
    integrate(options);
    window.setInterval(function() {
      integrate(options);
    }, 1000);
  }

  window.BeagleUiExtJsIntegration = {
    boot: boot,
    integrate: integrate
  };
})();

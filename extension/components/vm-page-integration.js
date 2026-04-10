(function() {
  "use strict";

  function createToolbarButton(label, onClick, buttonMarker) {
    var button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute(buttonMarker, label);
    button.className = "x-btn-text";
    button.style.marginLeft = "6px";
    button.style.padding = "4px 10px";
    button.style.border = "1px solid #b5b8c8";
    button.style.background = "#f5f5f5";
    button.style.borderRadius = "3px";
    button.style.cursor = "pointer";
    button.style.lineHeight = "20px";
    button.addEventListener("click", function(event) {
      event.preventDefault();
      event.stopPropagation();
      onClick();
    });
    return button;
  }

  function isConsoleMenuTrigger(element, menuText) {
    var text = String(element && element.textContent || "").trim();
    return text === menuText || text.indexOf(menuText) !== -1;
  }

  function findToolbarRow(menuText) {
    var buttons = Array.from(document.querySelectorAll("button, a, div, span"));
    var i;
    var element;
    var row;
    for (i = 0; i < buttons.length; i += 1) {
      element = buttons[i];
      if (!isConsoleMenuTrigger(element, menuText)) {
        continue;
      }
      row = element.closest(".x-toolbar") ||
        element.closest(".x-box-inner") ||
        element.closest(".x-panel-header") ||
        element.parentElement;
      if (row) {
        return row;
      }
    }
    return null;
  }

  function ensureToolbarButtons(options) {
    var buttonMarker = options.buttonMarker;
    var productLabel = options.productLabel;
    var virtualizationService = options.virtualizationService;
    var toolbar;
    var existingButton;
    var existingWebButton;

    document.querySelectorAll("[" + buttonMarker + "]").forEach(function(node) {
      if (!virtualizationService.isVmView()) {
        node.remove();
      }
    });

    if (!virtualizationService.isVmView()) {
      return;
    }

    toolbar = findToolbarRow(options.menuText);
    if (!toolbar) {
      return;
    }

    existingButton = toolbar.querySelector("[" + buttonMarker + "=\"" + productLabel + "\"]");
    existingWebButton = toolbar.querySelector("[" + buttonMarker + "=\"" + productLabel + " Web UI\"]");

    if (!existingButton) {
      existingButton = createToolbarButton(productLabel, options.showProfileModal, buttonMarker);
      existingButton.title = "Zeigt das aufgeloeste Beagle-Profil fuer diese VM und bietet Download-, Export- und Health-Aktionen.";
      toolbar.appendChild(existingButton);
    }
    if (!existingWebButton) {
      existingWebButton = createToolbarButton(productLabel + " Web UI", options.openWebUi, buttonMarker);
      existingWebButton.title = "Oeffnet die zentrale Beagle Web UI auf diesem Host.";
      toolbar.appendChild(existingWebButton);
    }
  }

  function getVisibleMenu() {
    var menus = Array.from(document.querySelectorAll(".x-menu, [role='menu']"));
    return menus.find(function(menu) {
      return menu.offsetParent !== null;
    }) || null;
  }

  function menuAlreadyHasLabel(menu, label) {
    return Array.from(menu.querySelectorAll("*")).some(function(node) {
      return String(node.textContent || "").trim() === label;
    });
  }

  function createMenuItem(label, onClick, buttonMarker) {
    var item = document.createElement("a");
    item.href = "#";
    item.setAttribute(buttonMarker, label);
    item.className = "x-menu-item";
    item.style.display = "block";
    item.style.padding = "4px 24px";
    item.style.cursor = "pointer";
    item.textContent = label;
    item.addEventListener("click", function(event) {
      event.preventDefault();
      event.stopPropagation();
      onClick();
    });
    return item;
  }

  function ensureMenuItems(options) {
    var productLabel = options.productLabel;
    var buttonMarker = options.buttonMarker;
    var virtualizationService = options.virtualizationService;
    var menu;
    var hasConsoleItems;

    if (!virtualizationService.isVmView()) {
      return;
    }

    menu = getVisibleMenu();
    if (!menu) {
      return;
    }

    hasConsoleItems = Array.from(menu.querySelectorAll("*")).some(function(node) {
      var text = String(node.textContent || "").trim();
      return text === "noVNC" || text === "SPICE" || text === "xterm.js";
    });

    if (!hasConsoleItems) {
      return;
    }
    if (!menuAlreadyHasLabel(menu, productLabel + " Profil")) {
      menu.appendChild(createMenuItem(productLabel + " Profil", options.showProfileModal, buttonMarker));
    }

    virtualizationService.parseVmContext().then(function(ctx) {
      if (!ctx) {
        return null;
      }
      return options.getVmInstallerEligibility(ctx).then(function(result) {
        var existingInstaller = Array.from(menu.querySelectorAll("[" + buttonMarker + "]")).find(function(node) {
          return String(node.textContent || "").trim() === productLabel + " Installer";
        });
        if (result && result.eligible) {
          if (!existingInstaller) {
            menu.appendChild(createMenuItem(productLabel + " Installer", options.downloadUsbInstaller, buttonMarker));
          }
          return;
        }
        if (existingInstaller) {
          existingInstaller.remove();
        }
      });
    }).catch(function() {});
  }

  async function boot(options) {
    var ensureInjected = function() {
      ensureToolbarButtons(options);
      ensureMenuItems(options);
    };
    var observer;
    var i;

    for (i = 0; i < 12; i += 1) {
      ensureInjected();
      await options.sleep(500);
    }

    window.addEventListener("hashchange", ensureInjected);
    document.addEventListener("click", function() {
      window.setTimeout(ensureInjected, 50);
    }, true);

    observer = new MutationObserver(ensureInjected);
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  window.BeagleExtensionVmPageIntegration = {
    boot: boot,
    ensureMenuItems: ensureMenuItems,
    ensureToolbarButtons: ensureToolbarButtons
  };
})();

(function() {
  "use strict";

  var common = window.BeagleUiCommon;

  if (!common) {
    throw new Error("BeagleUiCommon must be loaded before BeagleUiBrowserActions");
  }

  function showError(productLabel, message) {
    if (window.Ext && Ext.Msg && Ext.Msg.alert) {
      Ext.Msg.alert(productLabel, message);
    } else {
      window.alert(message);
    }
  }

  function showToast(productLabel, message) {
    if (window.Ext && Ext.toast) {
      Ext.toast({ html: message, title: productLabel, align: "t" });
      return;
    }
    window.alert(message);
  }

  function openUrl(showErrorFn, url) {
    if (!url) {
      showErrorFn("URL konnte nicht ermittelt werden.");
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  }

  function triggerDownload(showErrorFn, url) {
    if (!url) {
      showErrorFn("Download-URL konnte nicht ermittelt werden.");
      return;
    }
    var anchor = document.createElement("a");
    anchor.href = common.withNoCache(url);
    anchor.rel = "noopener noreferrer";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }

  window.BeagleUiBrowserActions = {
    showError: showError,
    showToast: showToast,
    openUrl: openUrl,
    triggerDownload: triggerDownload
  };
})();

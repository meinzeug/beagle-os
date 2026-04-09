(function() {
  "use strict";

  function kvRow(label, value) {
    return '<div class="beagle-kv-row"><strong>' + label + '</strong><span>' + (value || '<span class="beagle-muted">nicht gesetzt</span>') + '</span></div>';
  }

  function escapeHtml(text) {
    return String(text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  window.BeagleUiRenderHelpers = {
    kvRow: kvRow,
    escapeHtml: escapeHtml
  };
})();

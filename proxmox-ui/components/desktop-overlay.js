(function() {
  "use strict";

  var renderHelpers = window.BeagleUiRenderHelpers;

  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before BeagleUiDesktopOverlay");
  }

  function buildCityBlocks() {
    var buildings = [];
    var widths = [18, 28, 14, 35, 22, 12, 30, 16, 40, 20, 15, 32, 18, 25, 14, 38, 20, 16, 28, 22, 35, 18, 24, 14, 30, 20, 28, 16, 22, 35, 18, 40, 14, 25, 20, 32, 16, 28, 22, 18];
    var heights = [55, 75, 40, 90, 60, 35, 80, 45, 95, 50, 38, 85, 55, 70, 42, 92, 52, 44, 78, 58, 88, 48, 65, 36, 82, 54, 72, 46, 62, 86, 50, 98, 38, 68, 52, 84, 44, 76, 56, 48];
    for (var i = 0; i < widths.length; i++) {
      buildings.push('<div class="bd-building" style="width:' + widths[i] + 'px;height:' + heights[i] + '%;"></div>');
    }
    return buildings.join("");
  }

  function buildNeonLines() {
    var lines = [];
    var colors = ["#ff00b4", "#00e5ff", "#ff1493", "#7b2dff", "#00ff88"];
    for (var i = 0; i < 12; i++) {
      var top = 20 + Math.floor(i * 5.5);
      var left = Math.floor(i * 8.3);
      var width = 30 + Math.floor((i * 17) % 60);
      var color = colors[i % colors.length];
      lines.push('<div class="bd-neon-line" style="top:' + top + '%;left:' + left + '%;width:' + width + 'px;background:' + color + ';box-shadow:0 0 6px ' + color + ';"></div>');
    }
    return lines.join("");
  }

  function renderDesktopOverlay(options) {
    var overlayId = options.overlayId;
    var profile = options.profile;
    var removeOverlay = options.removeOverlay;
    var showProfileModal = options.showProfileModal;
    var overlay = document.createElement("div");
    var vmid = String(profile.vmid || "?");
    var now = new Date();
    var clock = String(now.getHours()).replace(/^(\d)$/, "0$1") + ":" + String(now.getMinutes()).replace(/^(\d)$/, "0$1");

    overlay.id = overlayId;
    overlay.className = "beagle-desktop-mode";
    overlay.innerHTML = '' +
      '<div class="bd-scene">' +
      '  <div class="bd-bg"></div>' +
      '  <div class="bd-city">' + buildNeonLines() + '<div class="bd-city-blocks">' + buildCityBlocks() + '</div></div>' +
      '  <div class="bd-floor"></div>' +
      '  <div class="bd-topbar">' +
      '    <span class="bd-topbar-left">Activities</span>' +
      '    <span class="bd-topbar-center">' + renderHelpers.escapeHtml(clock) + '</span>' +
      '    <div class="bd-topbar-right">' +
      '      <svg viewBox="0 0 24 24"><path d="M2 17h2v.5H3v1h1v.5H2v1h3v-4H2v1zm1-9h1V4H2v1h1v3zm5 4h14v-2H7v2zm0 6h14v-2H7v2zm0-12v2h14V5H7z"/></svg>' +
      '      <svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>' +
      '      <svg viewBox="0 0 24 24"><rect x="7" y="4" width="10" height="18" rx="2" fill="none" stroke="#fff" stroke-width="2"/><rect x="10" y="7" width="4" height="10" fill="#fff" opacity="0.7"/></svg>' +
      '    </div>' +
      '  </div>' +
      '  <div class="bd-dock">' +
      '    <button class="bd-dock-icon" style="background:#e74c3c" title="Files"></button>' +
      '    <button class="bd-dock-icon" style="background:#f39c12" title="Settings"></button>' +
      '    <button class="bd-dock-icon" style="background:#2ecc71" title="Browser"></button>' +
      '    <button class="bd-dock-icon" style="background:#00bcd4" title="Desktop"></button>' +
      '    <button class="bd-dock-icon" style="background:#6a1b9a;color:#fff" title="Terminal"><svg viewBox="0 0 24 24"><path d="M20 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 14H4V8h16v10zm-2-1h-6v-2h6v2zM7.5 17l-1.41-1.41L8.67 13l-2.59-2.59L7.5 9l4 4-4 4z"/></svg></button>' +
      '    <button class="bd-dock-icon" style="background:#e91e8f" title="Steam"></button>' +
      '    <button class="bd-dock-icon" style="background:#111;border:2px solid rgba(255,255,255,0.25)" title="Heroic"></button>' +
      '  </div>' +
      '  <button class="bd-close-overlay" title="Close">&times;</button>' +
      '  <button class="bd-details-link" data-beagle-action="show-profile">Show Details</button>' +
      '  <div class="bd-window">' +
      '    <div class="bd-win-titlebar">' +
      '      <div class="bd-win-dots">' +
      '        <span class="bd-win-dot close" data-beagle-action="close-overlay"></span>' +
      '        <span class="bd-win-dot minimize"></span>' +
      '        <span class="bd-win-dot maximize"></span>' +
      '      </div>' +
      '      <span class="bd-win-title">Beagle OS Desktop &middot; VM ' + renderHelpers.escapeHtml(vmid) + '</span>' +
      '    </div>' +
      '    <div class="bd-win-body">' +
      '      <div class="bd-win-sidebar">' +
      '        <h3>Apps</h3>' +
      '        <button class="bd-app-item" data-beagle-action="app-files">Files</button>' +
      '        <button class="bd-app-item" data-beagle-action="app-desktop">Desktop</button>' +
      '        <button class="bd-app-item" data-beagle-action="app-downloads">Downloads</button>' +
      '        <button class="bd-app-item" data-beagle-action="app-steam">Steam</button>' +
      '        <button class="bd-app-item" data-beagle-action="app-heroic">Heroic</button>' +
      '        <button class="bd-app-item" data-beagle-action="app-terminal">Terminal</button>' +
      '      </div>' +
      '      <div class="bd-win-content">' +
      '        <h2 class="bd-welcome-title">Welcome to Beagle OS</h2>' +
      '        <p class="bd-welcome-sub">Open-source endpoint OS for Proxmox-native desktop</p>' +
      '        <div class="bd-wallpaper-preview">' +
      '          <span class="bd-wallpaper-label">BEAGLE OS</span>' +
      '        </div>' +
      '        <button class="bd-btn-wallpaper" data-beagle-action="wallpaper-ready">Wallpaper Ready</button>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="bd-branding">' +
      '    <h1 class="bd-brand-title">BEAGLE <span>OS</span></h1>' +
      '    <p class="bd-brand-tagline">Built for builders. &nbsp; Born to break rules.</p>' +
      '  </div>' +
      '  <div class="bd-badge">' +
      '    <span>Wallpaper preview &middot; Beagle VM ' + renderHelpers.escapeHtml(vmid) + '</span>' +
      '  </div>' +
      '</div>';

    overlay.__beagleProfile = profile;
    overlay.addEventListener("click", function(event) {
      if (!(event.target instanceof HTMLElement)) {
        return;
      }
      var action = event.target.getAttribute("data-beagle-action") || event.target.closest("[data-beagle-action]") && event.target.closest("[data-beagle-action]").getAttribute("data-beagle-action") || "";
      switch (action) {
        case "close-overlay":
          removeOverlay();
          break;
        case "show-profile":
          removeOverlay();
          showProfileModal(profile);
          break;
        default:
          break;
      }
    });

    var closeBtn = overlay.querySelector(".bd-close-overlay");
    if (closeBtn) {
      closeBtn.addEventListener("click", function() {
        removeOverlay();
      });
    }

    document.body.appendChild(overlay);
  }

  window.BeagleUiDesktopOverlay = {
    renderDesktopOverlay: renderDesktopOverlay
  };
})();

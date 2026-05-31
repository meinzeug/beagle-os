/**
 * Beagle OS Build Status Widget
 * Fetches live build data from the Beagle server's status JSON endpoint
 * and renders a live ticker on the download page.
 */
(function () {
  'use strict';

  const POLL_INTERVAL_MS = 60000; // refresh every 60s
  const DEFAULT_STATUS_URL = 'https://beagle-os.com/beagle-updates/beagle-downloads-status.json';
  const WIDGET_SELECTOR = '[data-build-status-widget]';

  function formatBytes(bytes) {
    if (!bytes) return '–';
    const units = ['B', 'KB', 'MB', 'GB'];
    let val = bytes;
    let unit = 0;
    while (val >= 1024 && unit < units.length - 1) { val /= 1024; unit++; }
    return val.toFixed(1) + ' ' + units[unit];
  }

  function formatDate(iso) {
    if (!iso) return '–';
    try {
      const d = new Date(iso);
      return d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', timeZoneName: 'short'
      });
    } catch (_) { return iso; }
  }

  function widgetLabel(widget, data) {
    const channel = (data.release_class || data.channel || 'stable').toLowerCase();
    const explicitLabel = widget.dataset.channelLabel;
    if (explicitLabel) return explicitLabel;
    if (channel === 'prerelease') return 'Prerelease';
    return 'Stable';
  }

  function renderWidget(widget, data) {
    if (!widget) return;

    const version = data.version || '–';
    const channel = (data.release_class || data.channel || 'stable').toLowerCase();
    const channelLabel = widgetLabel(widget, data);
    const generatedAt = formatDate(data.generated_at);
    const payloadSize = formatBytes(data.payload_size);
    const payloadSha = data.payload_sha256 ? data.payload_sha256.slice(0, 16) + '…' : '–';
    const releaseUrl = data.release_url || `https://github.com/meinzeug/beagle-os/releases/tag/v${version}`;
    const payloadUrl = data.payload_latest_url || data.payload_url || '#';
    const installImageUrl = data.server_installimage_url || data.server_installer_iso_url || '#';
    const checksumsUrl = data.sha256sums_url || '#';
    const primaryBadgeClass = channel === 'prerelease' ? 'build-badge--warn' : 'build-badge--ok';
    const reinstallRequired = data.endpoint_compatibility?.reinstall_required === true;
    const migrationRequired = data.endpoint_compatibility?.migration_required === true;

    const statusBadge = reinstallRequired
      ? '<span class="build-badge build-badge--warn" data-en="Reinstall required" data-de="Neuinstallation erforderlich">Reinstall required</span>'
      : migrationRequired
        ? '<span class="build-badge build-badge--warn" data-en="Migration required" data-de="Migration erforderlich">Migration required</span>'
        : `<span class="build-badge ${primaryBadgeClass}" data-en="${channelLabel}" data-de="${channelLabel}">${channelLabel}</span>`;

    widget.innerHTML = `
      <div class="build-status-ticker">
        <div class="build-status-header">
          <span class="build-status-dot build-status-dot--live"></span>
          <span class="build-status-label" data-en="${channelLabel}" data-de="${channelLabel}">${channelLabel}</span>
          <span class="build-status-updated" title="${data.generated_at || ''}">
            <span data-en="Updated" data-de="Aktualisiert">Updated</span>: ${generatedAt}
          </span>
        </div>
        <div class="build-status-body">
          <div class="build-stat">
            <span class="build-stat-key" data-en="Version" data-de="Version">Version</span>
            <span class="build-stat-val"><strong>v${version}</strong></span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="USB Payload size" data-de="USB-Payload-Größe">USB Payload size</span>
            <span class="build-stat-val">${payloadSize}</span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="SHA256 (payload)" data-de="SHA256 (Payload)">SHA256 (payload)</span>
            <span class="build-stat-val build-stat-mono">${payloadSha}</span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="Compatibility" data-de="Kompatibilität">Compatibility</span>
            <span class="build-stat-val">${statusBadge}</span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="Full checksums" data-de="Alle Checksummen">Full checksums</span>
            <span class="build-stat-val">
              <a href="${checksumsUrl}" target="_blank" rel="noreferrer" data-en="SHA256SUMS" data-de="SHA256SUMS">SHA256SUMS ↗</a>
            </span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="Primary download" data-de="Primärer Download">Primary download</span>
            <span class="build-stat-val"><a href="${payloadUrl}" target="_blank" rel="noreferrer" data-en="Payload" data-de="Payload">Payload ↗</a></span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="Install image" data-de="Installimage">Install image</span>
            <span class="build-stat-val"><a href="${installImageUrl}" target="_blank" rel="noreferrer" data-en="Install image" data-de="Installimage">Install image ↗</a></span>
          </div>
          <div class="build-stat">
            <span class="build-stat-key" data-en="Release page" data-de="Release-Seite">Release page</span>
            <span class="build-stat-val"><a href="${releaseUrl}" target="_blank" rel="noreferrer" data-en="GitHub release" data-de="GitHub-Release">GitHub release ↗</a></span>
          </div>
        </div>
      </div>`;

    // re-apply lang translations if lang.js is present
    if (typeof window.__beagleLang === 'function') {
      window.__beagleLang();
    }
  }

  function renderError(widget, msg) {
    if (!widget) return;
    widget.innerHTML = `<div class="build-status-ticker build-status-ticker--error">
      <span class="build-status-dot build-status-dot--err"></span>
      <span class="muted" data-en="Build status unavailable" data-de="Build-Status nicht verfügbar">${msg}</span>
    </div>`;
  }

  function fetchStatus(widget) {
    const statusUrl = widget.dataset.statusUrl || DEFAULT_STATUS_URL;
    fetch(statusUrl, { cache: 'no-cache' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) { renderWidget(widget, data); })
      .catch(function (err) {
        renderError(widget, 'Build status unavailable (' + err.message + ')');
      });
  }

  function initWidget(widget) {
    widget.innerHTML = '<div class="build-status-ticker build-status-ticker--loading"><span class="build-status-dot build-status-dot--loading"></span><span class="muted">Loading build status…</span></div>';
    fetchStatus(widget);
    setInterval(function () { fetchStatus(widget); }, POLL_INTERVAL_MS);
  }

  function init() {
    const widgets = document.querySelectorAll(WIDGET_SELECTOR);
    if (!widgets.length) return;
    widgets.forEach(initWidget);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

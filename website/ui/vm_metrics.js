/**
 * VM Live Metrics panel — SSE-driven CPU/RAM/Disk/Net gauges.
 *
 * Export:
 *   startVmMetrics(vmid, containerEl, token)
 *     Opens an EventSource to /api/v1/vms/:vmid/metrics-stream and
 *     renders live gauges inside containerEl.
 *     Returns a cleanup() function that must be called when the panel
 *     is hidden or when the user navigates away.
 */

import { apiBase } from './api.js';
import { escapeHtml } from './dom.js';

// -------------------------------------------------------------------------
// Formatting helpers
// -------------------------------------------------------------------------

function fmtBytes(bytes) {
  const b = Number(bytes || 0);
  if (b >= 1024 ** 3) return (b / 1024 ** 3).toFixed(1) + ' GiB';
  if (b >= 1024 ** 2) return (b / 1024 ** 2).toFixed(1) + ' MiB';
  if (b >= 1024)      return (b / 1024).toFixed(1) + ' KiB';
  return b + ' B';
}

function fmtBps(bps) {
  return fmtBytes(bps) + '/s';
}

function fmtPct(pct) {
  return Number(pct || 0).toFixed(1) + '%';
}

// -------------------------------------------------------------------------
// DOM builder
// -------------------------------------------------------------------------

function buildPanelHtml() {
  return `
    <section class="detail-section vm-metrics-section">
      <div class="vm-metrics-header">
        <h3>Live Metriken</h3>
        <span class="chip muted" id="vdp-metrics-status">Verbinde…</span>
      </div>

      <div class="vm-metrics-grid">

        <div class="vm-metric-card">
          <div class="vm-metric-label">CPU</div>
          <div class="vm-metric-value" id="vdp-m-cpu-pct">—</div>
          <progress class="vm-metric-bar bar-ok" id="vdp-m-cpu-bar" value="0" max="100"></progress>
        </div>

        <div class="vm-metric-card">
          <div class="vm-metric-label">RAM</div>
          <div class="vm-metric-value" id="vdp-m-ram-pct">—</div>
          <progress class="vm-metric-bar bar-ok" id="vdp-m-ram-bar" value="0" max="100"></progress>
          <div class="vm-metric-sub" id="vdp-m-ram-detail">—</div>
        </div>

        <div class="vm-metric-card">
          <div class="vm-metric-label">Disk (Dateisystem)</div>
          <div class="vm-metric-value" id="vdp-m-disk-pct">—</div>
          <progress class="vm-metric-bar bar-ok" id="vdp-m-disk-bar" value="0" max="100"></progress>
          <div class="vm-metric-sub" id="vdp-m-disk-detail">—</div>
        </div>

        <div class="vm-metric-card">
          <div class="vm-metric-label">Disk I/O</div>
          <div class="vm-metric-value" id="vdp-m-disk-io">—</div>
          <div class="vm-metric-sub">
            <span id="vdp-m-disk-rd">↑ 0 B/s</span>
            &nbsp;/&nbsp;
            <span id="vdp-m-disk-wr">↓ 0 B/s</span>
          </div>
        </div>

        <div class="vm-metric-card">
          <div class="vm-metric-label">Netzwerk I/O</div>
          <div class="vm-metric-value" id="vdp-m-net-io">—</div>
          <div class="vm-metric-sub">
            <span id="vdp-m-net-rx">↓ 0 B/s</span>
            &nbsp;/&nbsp;
            <span id="vdp-m-net-tx">↑ 0 B/s</span>
          </div>
        </div>

        <div class="vm-metric-card">
          <div class="vm-metric-label">Letztes Update</div>
          <div class="vm-metric-value vm-metric-ts" id="vdp-m-ts">—</div>
        </div>

      </div>
    </section>
  `;
}

// -------------------------------------------------------------------------
// Bar fill tone
// -------------------------------------------------------------------------

// Update progress bar value and color-tone class without using inline styles
// (CSP blocks element.style assignments when style-src 'self' is active).
// <progress>.value is a DOM property change — not blocked by style-src.
function updateBar(barId, pct) {
  const el = document.getElementById(barId);
  if (!el) return;
  const clamped = Math.min(100, Math.max(0, Number(pct || 0)));
  el.value = clamped;  // DOM property on <progress>, NOT an inline style
  el.classList.remove('bar-ok', 'bar-warn', 'bar-crit');
  if (clamped >= 90)      el.classList.add('bar-crit');
  else if (clamped >= 75) el.classList.add('bar-warn');
  else                    el.classList.add('bar-ok');
}

function updateText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = String(value);
}

// -------------------------------------------------------------------------
// Core SSE logic
// -------------------------------------------------------------------------

function applyMetrics(data) {
  const cpu  = Number(data.cpu_pct  || 0);
  const ram  = Number(data.ram_pct  || 0);
  const disk = Number(data.disk_used_pct || 0);

  // CPU
  updateText('vdp-m-cpu-pct', fmtPct(cpu));
  updateBar('vdp-m-cpu-bar', cpu);

  // RAM
  updateText('vdp-m-ram-pct', fmtPct(ram));
  updateBar('vdp-m-ram-bar', ram);
  updateText('vdp-m-ram-detail',
    fmtBytes(data.ram_used) + ' / ' + fmtBytes(data.ram_total));

  // Disk filesystem
  updateText('vdp-m-disk-pct', disk > 0 ? fmtPct(disk) : '—');
  updateBar('vdp-m-disk-bar', disk);
  updateText('vdp-m-disk-detail',
    data.disk_total_bytes > 0
      ? fmtBytes(data.disk_used_bytes) + ' / ' + fmtBytes(data.disk_total_bytes)
      : 'Kein Gast-Agent');

  // Disk I/O
  const rdBps = Number(data.disk_read_bps  || 0);
  const wrBps = Number(data.disk_write_bps || 0);
  updateText('vdp-m-disk-io', fmtBps(rdBps + wrBps));
  updateText('vdp-m-disk-rd', '↑ ' + fmtBps(rdBps));
  updateText('vdp-m-disk-wr', '↓ ' + fmtBps(wrBps));

  // Network I/O
  const rxBps = Number(data.net_rx_bps || 0);
  const txBps = Number(data.net_tx_bps || 0);
  updateText('vdp-m-net-io', fmtBps(rxBps + txBps));
  updateText('vdp-m-net-rx', '↓ ' + fmtBps(rxBps));
  updateText('vdp-m-net-tx', '↑ ' + fmtBps(txBps));

  // Timestamp
  updateText('vdp-m-ts', String(data.ts || '').replace('T', ' ').replace('Z', ' UTC'));
}

/**
 * Open SSE stream for vmid, render into containerEl.
 * Returns cleanup().
 */
export function startVmMetrics(vmid, containerEl, token) {
  if (!containerEl) return () => {};

  containerEl.innerHTML = buildPanelHtml();

  const statusEl = document.getElementById('vdp-metrics-status');

  const url = apiBase().replace(/\/api\/v1$/, '') + '/api/v1/vms/' + encodeURIComponent(String(vmid)) + '/metrics-stream';

  // Build URL with auth token in query string for EventSource (which
  // cannot set custom request headers in browsers).
  const fullUrl = token ? url + '?access_token=' + encodeURIComponent(String(token)) : url;

  let es = null;
  let closed = false;

  function open() {
    if (closed) return;
    es = new EventSource(fullUrl);

    es.addEventListener('hello', () => {
      if (statusEl) {
        statusEl.textContent = 'Live';
        statusEl.className = 'chip ok';
      }
    });

    es.addEventListener('metrics', (evt) => {
      try {
        const data = JSON.parse(evt.data);
        applyMetrics(data);
      } catch (err) {
        void err;
      }
    });

    es.addEventListener('error', (evt) => {
      void evt;
      if (statusEl) {
        statusEl.textContent = 'Unterbrochen';
        statusEl.className = 'chip warn';
      }
    });

    es.onerror = () => {
      if (statusEl) {
        statusEl.textContent = 'Unterbrochen';
        statusEl.className = 'chip warn';
      }
    };
  }

  open();

  return function cleanup() {
    closed = true;
    if (es) {
      es.close();
      es = null;
    }
  };
}

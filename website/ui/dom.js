import {
  USAGE_INFO_THRESHOLD,
  USAGE_WARN_THRESHOLD
} from './state.js';

const secretVault = Object.create(null);

export function qs(id) {
  return document.getElementById(id);
}

export function text(id, value) {
  const node = qs(id);
  if (node) {
    node.textContent = value;
  }
}

export function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function chip(label, tone) {
  return '<span class="chip ' + String(tone || '') + '">' + escapeHtml(label) + '</span>';
}

export function fieldBlock(label, value, tone) {
  return '<div class="kv ' + String(tone || '') + '"><div class="kv-label">' +
    escapeHtml(label) + '</div><div class="kv-value">' + escapeHtml(value || 'n/a') + '</div></div>';
}

export function actionButton(action, label, tone) {
  return '<button type="button" class="btn btn-' + escapeHtml(tone || 'ghost') +
    '" data-action="' + escapeHtml(action) + '">' + escapeHtml(label) + '</button>';
}

export function formatDate(value) {
  if (!value) {
    return 'n/a';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' });
}

export function formatGiB(value) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return 'n/a';
  }
  return (numeric / (1024 * 1024 * 1024)).toFixed(1) + ' GiB';
}

export function formatBytes(bytes) {
  if (!bytes) {
    return '0 B';
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let index = 0;
  let value = Number(bytes);
  while (value >= 1024 && index < units.length - 1) {
    value = value / 1024;
    index += 1;
  }
  return value.toFixed(1) + '\u00a0' + units[index];
}

export function usageBar(used, total, label) {
  const pct = total > 0 ? Math.min(100, Math.round((Number(used) / Number(total)) * 100)) : 0;
  const tone = pct >= USAGE_WARN_THRESHOLD ? 'warn' : pct >= USAGE_INFO_THRESHOLD ? 'info' : '';
  return '<span class="usage-bar-outer ' + tone + '">' +
    '<progress class="usage-bar-track usage-progress" max="100" value="' + pct + '"></progress>' +
    '<span class="usage-label">' + escapeHtml(label || (pct + '%')) + '</span>' +
    '</span>';
}

export function maskedFieldBlock(label, value) {
  const safeId = 'cred-' + Math.random().toString(36).slice(2, 10);
  const hasValue = Boolean(value);
  secretVault[safeId] = String(value || '');
  return '<div class="kv"><div class="kv-label">' + escapeHtml(label) + '</div>' +
    '<div class="kv-value kv-value-masked">' +
    '<span class="kv-secret" id="' + safeId + '" data-visible="0">' +
    (hasValue ? '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' : 'n/a') +
    '</span>' +
    (hasValue ? '<button type="button" class="btn-reveal" data-reveal-id="' + safeId + '">Anzeigen</button>' : '') +
    '</div></div>';
}

export function readSecretValue(secretId) {
  return String(secretVault[String(secretId || '')] || '');
}

export function clearSecretVault() {
  Object.keys(secretVault).forEach((key) => {
    delete secretVault[key];
  });
}

export function downloadTextFile(filename, content, contentType) {
  const blob = new Blob([String(content || '')], { type: contentType || 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
    link.remove();
  }, 1000);
}
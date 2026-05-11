import {
  DISK_KEY_PATTERN,
  NET_KEY_PATTERN,
  VM_MAIN_KEYS
} from './state.js';
import { escapeHtml, fieldBlock } from './dom.js';
import { putJson } from './api.js';

const EDITOR_SECTIONS = [
  {
    id: 'general',
    title: 'Allgemein',
    fields: [
      { key: 'name', label: 'Name', type: 'text' },
      { key: 'description', label: 'Beschreibung', type: 'textarea' },
      { key: 'tags', label: 'Tags', type: 'text' },
      { key: 'ostype', label: 'OS Type', type: 'text' },
      { key: 'protection', label: 'Protection', type: 'checkbox' },
      { key: 'template', label: 'Template', type: 'checkbox' }
    ]
  },
  {
    id: 'resources',
    title: 'CPU & RAM',
    fields: [
      { key: 'sockets', label: 'Sockets', type: 'number', min: 1 },
      { key: 'cores', label: 'Cores', type: 'number', min: 1 },
      { key: 'vcpus', label: 'vCPUs', type: 'number', min: 0 },
      { key: 'cpu', label: 'CPU Type', type: 'text' },
      { key: 'memory', label: 'Memory MB', type: 'number', min: 16 },
      { key: 'balloon', label: 'Balloon MB', type: 'number', min: 0 },
      { key: 'cpuunits', label: 'CPU Units', type: 'number', min: 1 },
      { key: 'cpulimit', label: 'CPU Limit', type: 'text' },
      { key: 'numa', label: 'NUMA', type: 'checkbox' },
      { key: 'affinity', label: 'CPU Affinity', type: 'text' }
    ]
  },
  {
    id: 'boot',
    title: 'Boot & Firmware',
    fields: [
      { key: 'bios', label: 'BIOS', type: 'text' },
      { key: 'machine', label: 'Machine', type: 'text' },
      { key: 'boot', label: 'Boot Order', type: 'text' },
      { key: 'bootdisk', label: 'Boot Disk', type: 'text' },
      { key: 'scsihw', label: 'SCSI Controller', type: 'text' },
      { key: 'agent', label: 'QEMU Agent', type: 'text' },
      { key: 'onboot', label: 'On Boot', type: 'checkbox' },
      { key: 'startup', label: 'Startup', type: 'text' },
      { key: 'tablet', label: 'Tablet', type: 'checkbox' },
      { key: 'acpi', label: 'ACPI', type: 'checkbox' },
      { key: 'kvm', label: 'KVM', type: 'checkbox' }
    ]
  },
  {
    id: 'display',
    title: 'Display & Audio',
    fields: [
      { key: 'vga', label: 'Display', type: 'text' },
      { key: 'audio0', label: 'Audio', type: 'text' },
      { key: 'keyboard', label: 'Keyboard', type: 'text' },
      { key: 'spice_enhancements', label: 'SPICE Enhancements', type: 'text' }
    ]
  },
  {
    id: 'cloudinit',
    title: 'Cloud-Init',
    fields: [
      { key: 'ciuser', label: 'User', type: 'text' },
      { key: 'sshkeys', label: 'SSH Keys', type: 'textarea' },
      { key: 'ipconfig0', label: 'IP Config 0', type: 'text' },
      { key: 'ipconfig1', label: 'IP Config 1', type: 'text' },
      { key: 'nameserver', label: 'Nameserver', type: 'text' },
      { key: 'searchdomain', label: 'Search Domain', type: 'text' },
      { key: 'citype', label: 'Cloud-Init Type', type: 'text' },
      { key: 'ciupgrade', label: 'Upgrade Packages', type: 'checkbox' }
    ]
  },
  {
    id: 'advanced',
    title: 'Advanced',
    fields: [
      { key: 'hotplug', label: 'Hotplug', type: 'text' },
      { key: 'watchdog', label: 'Watchdog', type: 'text' },
      { key: 'rng0', label: 'RNG', type: 'text' },
      { key: 'hookscript', label: 'Hookscript', type: 'text' },
      { key: 'args', label: 'QEMU Args', type: 'textarea' },
      { key: 'vmgenid', label: 'VM Generation ID', type: 'text' }
    ]
  }
];

const BOOLEAN_FIELDS = new Set(
  EDITOR_SECTIONS.flatMap((section) => section.fields).filter((field) => field.type === 'checkbox').map((field) => field.key)
);
const NUMBER_FIELDS = new Set(
  EDITOR_SECTIONS.flatMap((section) => section.fields).filter((field) => field.type === 'number').map((field) => field.key)
);

function normalize(value) {
  if (value == null) {
    return '';
  }
  return String(value);
}

function normalizeBoolean(value) {
  if (typeof value === 'boolean') {
    return value;
  }
  return ['1', 'true', 'yes', 'on', 'ja'].includes(String(value || '').trim().toLowerCase());
}

function hardwareKeys(config) {
  return Object.keys(config || {}).filter((key) => {
    return DISK_KEY_PATTERN.test(key) || NET_KEY_PATTERN.test(key) || /^(usb|hostpci|serial|parallel|tpmstate|efidisk|virtiofs)\d+$/.test(key);
  }).sort();
}

function unknownKeys(config) {
  const known = new Set(VM_MAIN_KEYS);
  EDITOR_SECTIONS.forEach((section) => section.fields.forEach((field) => known.add(field.key)));
  hardwareKeys(config).forEach((key) => known.add(key));
  return Object.keys(config || {}).filter((key) => !known.has(key)).sort();
}

function fieldValue(config, key, type) {
  if (type === 'checkbox') {
    return normalizeBoolean(config[key]);
  }
  return normalize(config[key]);
}

function renderInput(field, config) {
  const value = fieldValue(config, field.key, field.type);
  const common = ' data-vm-config-field="' + escapeHtml(field.key) + '"';
  if (field.type === 'checkbox') {
    return '<label class="check-label"><input type="checkbox"' + common + (value ? ' checked' : '') + '> ' + escapeHtml(field.label) + '</label>';
  }
  if (field.type === 'textarea') {
    return '<label class="field"><span>' + escapeHtml(field.label) + '</span><textarea rows="3"' + common + '>' + escapeHtml(value) + '</textarea></label>';
  }
  const min = field.min == null ? '' : ' min="' + escapeHtml(String(field.min)) + '"';
  return '<label class="field"><span>' + escapeHtml(field.label) + '</span><input type="' + escapeHtml(field.type || 'text') + '"' + min + common + ' value="' + escapeHtml(value) + '"></label>';
}

function renderHardwareEditor(config) {
  const keys = hardwareKeys(config);
  let html = '<section class="detail-section"><h3>Hardware</h3>';
  if (!keys.length) {
    html += '<div class="muted">Keine Hardware-Optionen in der gespeicherten VM-Konfiguration.</div>';
  }
  keys.forEach((key) => {
    html += '<label class="field"><span>' + escapeHtml(key) + '</span><input class="mono" data-vm-config-field="' + escapeHtml(key) + '" value="' + escapeHtml(normalize(config[key])) + '"></label>';
  });
  html += '</section>';
  return html;
}

function renderInterfaces(interfaces) {
  if (!Array.isArray(interfaces) || !interfaces.length) {
    return '';
  }
  let html = '<section class="detail-section"><h3>Guest Agent Interfaces</h3>';
  interfaces.forEach((iface) => {
    const addrs = (iface['ip-addresses'] || []).map((addr) => {
      return String(addr['ip-address'] || '') + (addr.prefix ? '/' + addr.prefix : '');
    }).join(', ');
    html += fieldBlock(String(iface.name || ''), addrs || 'n/a');
  });
  html += '</section>';
  return html;
}

export class VmConfigEditor {
  constructor({ vmid, config, interfaces, onStatus }) {
    this.vmid = Number(vmid);
    this.config = Object.assign({}, config || {});
    this.interfaces = Array.isArray(interfaces) ? interfaces : [];
    this.onStatus = typeof onStatus === 'function' ? onStatus : function noop() {};
  }

  render() {
    let html = '<form class="vm-config-editor" data-vm-config-editor data-vmid="' + escapeHtml(String(this.vmid)) + '">';
    html += '<section class="detail-section"><div class="section-head"><div><h3>VM Konfiguration</h3><p class="muted">Beagle-native KVM/libvirt API, Proxmox-nahe Optionsabdeckung.</p></div><button type="submit" class="primary">Speichern</button></div><div class="banner banner-info" data-vm-config-status hidden></div></section>';
    EDITOR_SECTIONS.forEach((section) => {
      html += '<section class="detail-section"><h3>' + escapeHtml(section.title) + '</h3><div class="provision-grid">';
      section.fields.forEach((field) => {
        html += renderInput(field, this.config);
      });
      html += '</div></section>';
    });
    html += renderHardwareEditor(this.config);
    const extraKeys = unknownKeys(this.config);
    if (extraKeys.length) {
      html += '<section class="detail-section"><h3>Weitere Optionen</h3><div class="provision-grid">';
      extraKeys.forEach((key) => {
        html += '<label class="field"><span>' + escapeHtml(key) + '</span><input class="mono" data-vm-config-field="' + escapeHtml(key) + '" value="' + escapeHtml(normalize(this.config[key])) + '"></label>';
      });
      html += '</div></section>';
    }
    html += renderInterfaces(this.interfaces);
    html += '</form>';
    return html;
  }

  bind(root) {
    const form = root && root.querySelector ? root.querySelector('[data-vm-config-editor]') : null;
    if (!form) {
      return;
    }
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.save(form);
    });
  }

  collect(form) {
    const updates = {};
    form.querySelectorAll('[data-vm-config-field]').forEach((control) => {
      const key = String(control.getAttribute('data-vm-config-field') || '').trim();
      if (!key) {
        return;
      }
      let value;
      if (BOOLEAN_FIELDS.has(key)) {
        value = Boolean(control.checked);
      } else if (NUMBER_FIELDS.has(key)) {
        const text = String(control.value || '').trim();
        value = text === '' ? '' : Number(text);
      } else {
        value = String(control.value || '').trim();
      }
      if (String(value) !== String(fieldValue(this.config, key, BOOLEAN_FIELDS.has(key) ? 'checkbox' : 'text'))) {
        updates[key] = value;
      }
    });
    return { updates };
  }

  setLocalStatus(form, message, tone) {
    const box = form.querySelector('[data-vm-config-status]');
    if (!box) {
      this.onStatus(message, tone);
      return;
    }
    box.hidden = false;
    box.className = 'banner ' + (tone === 'bad' ? 'warn' : tone === 'ok' ? 'banner-ok' : 'banner-info');
    box.textContent = message;
    this.onStatus(message, tone);
  }

  save(form) {
    const payload = this.collect(form);
    if (!Object.keys(payload.updates).length) {
      this.setLocalStatus(form, 'Keine Aenderungen.', 'info');
      return Promise.resolve(null);
    }
    const button = form.querySelector('button[type="submit"]');
    if (button) {
      button.disabled = true;
    }
    this.setLocalStatus(form, 'Speichere VM-Konfiguration ...', 'info');
    return putJson('/virtualization/vms/' + encodeURIComponent(String(this.vmid)) + '/config', payload).then((result) => {
      this.config = Object.assign({}, result.config || this.config, payload.updates);
      this.setLocalStatus(form, 'Gespeichert: ' + Object.keys(payload.updates).join(', '), 'ok');
      return result;
    }).catch((error) => {
      this.setLocalStatus(form, 'Speichern fehlgeschlagen: ' + error.message, 'bad');
      throw error;
    }).finally(() => {
      if (button) {
        button.disabled = false;
      }
    });
  }
}

export function renderVmConfigEditor(options) {
  return new VmConfigEditor(options).render();
}

export function bindVmConfigEditor(root, options) {
  new VmConfigEditor(options).bind(root);
}

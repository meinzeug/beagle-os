import {
  DISK_KEY_PATTERN,
  NET_KEY_PATTERN,
  VM_MAIN_KEYS
} from './state.js';
import { escapeHtml, fieldBlock } from './dom.js';
import { putJson } from './api.js';

const DEVICE_PATTERNS = {
  disk: /^(ide|sata|scsi|virtio)\d+$/,
  network: /^net\d+$/,
  firmware: /^(efidisk|tpmstate)\d+$/,
  passthrough: /^(hostpci|usb|serial|parallel|rng|virtiofs|unused|numa)\d+$|^(ivshmem|amd-sev|intel-tdx|watchdog|smbios1)$/
};

const SLOT_LIMITS = {
  ide: 4,
  sata: 6,
  scsi: 31,
  virtio: 16,
  net: 32,
  efidisk: 1,
  tpmstate: 1,
  hostpci: 16,
  usb: 15,
  serial: 4,
  parallel: 3,
  rng: 1,
  virtiofs: 10,
  unused: 16,
  numa: 8
};

const OPTION_GROUPS = [
  {
    id: 'summary',
    title: 'General',
    fields: [
      { key: 'name', label: 'Name', type: 'text', important: true },
      { key: 'description', label: 'Description', type: 'textarea', important: true },
      { key: 'tags', label: 'Tags', type: 'text', important: true },
      { key: 'ostype', label: 'Guest OS', type: 'select', important: true, options: [
        ['l26', 'Linux 6.x/2.6 Kernel'],
        ['win11', 'Windows 11'],
        ['win10', 'Windows 10/2016/2019'],
        ['win8', 'Windows 8/2012'],
        ['win7', 'Windows 7/2008r2'],
        ['other', 'Other']
      ] },
      { key: 'protection', label: 'Protection', type: 'toggle', important: true },
      { key: 'template', label: 'Template', type: 'toggle' }
    ]
  },
  {
    id: 'cpu-memory',
    title: 'CPU & Memory',
    fields: [
      { key: 'sockets', label: 'Sockets', type: 'number', min: 1, max: 256, step: 1, important: true },
      { key: 'cores', label: 'Cores / Socket', type: 'number', min: 1, max: 512, step: 1, important: true },
      { key: 'vcpus', label: 'Hotplugged vCPUs', type: 'number', min: 0, max: 512, step: 1 },
      { key: 'cpu', label: 'CPU Type', type: 'select', important: true, options: [
        ['x86-64-v2-AES', 'x86-64-v2-AES'],
        ['host', 'host'],
        ['kvm64', 'kvm64'],
        ['qemu64', 'qemu64'],
        ['max', 'max']
      ] },
      { key: 'memory', label: 'Memory (MiB)', type: 'number', min: 16, max: 1048576, step: 256, important: true },
      { key: 'balloon', label: 'Balloon Target (MiB)', type: 'number', min: 0, max: 1048576, step: 256, important: true },
      { key: 'shares', label: 'Memory Shares', type: 'number', min: 0, max: 50000, step: 100 },
      { key: 'hugepages', label: 'Hugepages', type: 'select', options: [['', 'Default'], ['2', '2 MiB'], ['1024', '1 GiB'], ['any', 'Any']] },
      { key: 'keephugepages', label: 'Keep Hugepages', type: 'toggle' },
      { key: 'cpulimit', label: 'CPU Limit', type: 'text' },
      { key: 'cpuunits', label: 'CPU Weight', type: 'number', min: 1, max: 262144, step: 100 },
      { key: 'numa', label: 'NUMA', type: 'toggle' },
      { key: 'affinity', label: 'CPU Affinity', type: 'text' },
      { key: 'allow-ksm', label: 'Allow KSM', type: 'toggle' }
    ]
  },
  {
    id: 'system',
    title: 'System & Boot',
    fields: [
      { key: 'bios', label: 'Firmware', type: 'select', important: true, options: [['seabios', 'SeaBIOS'], ['ovmf', 'OVMF / UEFI']] },
      { key: 'machine', label: 'Machine Type', type: 'select', important: true, options: [['q35', 'q35'], ['pc-i440fx', 'i440fx'], ['pc', 'pc']] },
      { key: 'scsihw', label: 'SCSI Controller', type: 'select', important: true, options: [
        ['virtio-scsi-single', 'VirtIO SCSI single'],
        ['virtio-scsi-pci', 'VirtIO SCSI'],
        ['lsi', 'LSI 53C895A'],
        ['megasas', 'MegaRAID SAS'],
        ['pvscsi', 'VMware PVSCSI']
      ] },
      { key: 'boot', label: 'Boot Order', type: 'text', important: true },
      { key: 'bootdisk', label: 'Legacy Boot Disk', type: 'text' },
      { key: 'onboot', label: 'Start at Boot', type: 'toggle', important: true },
      { key: 'startup', label: 'Start/Shutdown Order', type: 'text' },
      { key: 'agent', label: 'QEMU Guest Agent', type: 'text', important: true },
      { key: 'hotplug', label: 'Hotplug', type: 'text' },
      { key: 'tablet', label: 'Tablet Pointer', type: 'toggle' },
      { key: 'acpi', label: 'ACPI', type: 'toggle' },
      { key: 'kvm', label: 'KVM Hardware Virtualization', type: 'toggle' },
      { key: 'localtime', label: 'RTC Local Time', type: 'toggle' },
      { key: 'startdate', label: 'RTC Start Date', type: 'text' },
      { key: 'reboot', label: 'Allow Reboot', type: 'toggle' },
      { key: 'arch', label: 'Architecture', type: 'select', options: [['', 'Default'], ['x86_64', 'x86_64'], ['aarch64', 'aarch64']] },
      { key: 'freeze', label: 'Freeze CPU at Start', type: 'toggle' },
      { key: 'tdf', label: 'Time Drift Fix', type: 'toggle' },
      { key: 'autostart', label: 'Autostart after Crash', type: 'toggle' }
    ]
  },
  {
    id: 'display',
    title: 'Display & Console',
    fields: [
      { key: 'vga', label: 'Display Adapter', type: 'select', important: true, options: [
        ['std', 'Standard VGA'],
        ['virtio', 'VirtIO GPU'],
        ['virtio-gl', 'VirtIO GL'],
        ['qxl', 'QXL / SPICE'],
        ['qxl2', 'QXL dual monitor'],
        ['qxl4', 'QXL quad monitor'],
        ['vmware', 'VMware compatible'],
        ['serial0', 'Serial terminal'],
        ['none', 'None']
      ] },
      { key: 'audio0', label: 'Audio Device', type: 'text', important: true },
      { key: 'spice_enhancements', label: 'SPICE Enhancements', type: 'text' },
      { key: 'keyboard', label: 'Keyboard Layout', type: 'select', options: [['', 'Default'], ['de', 'de'], ['en-us', 'en-us'], ['fr', 'fr'], ['es', 'es']] }
    ]
  },
  {
    id: 'cloudinit',
    title: 'Cloud-Init',
    fields: [
      { key: 'ciuser', label: 'User', type: 'text', important: true },
      { key: 'cipassword', label: 'Password', type: 'password', sensitive: true },
      { key: 'sshkeys', label: 'SSH Public Keys', type: 'textarea', important: true },
      { key: 'ipconfig0', label: 'IP Config 0', type: 'text', important: true },
      { key: 'ipconfig1', label: 'IP Config 1', type: 'text' },
      { key: 'nameserver', label: 'DNS Servers', type: 'text', important: true },
      { key: 'searchdomain', label: 'DNS Search Domain', type: 'text' },
      { key: 'citype', label: 'Cloud-Init Type', type: 'select', options: [['', 'Auto'], ['nocloud', 'NoCloud'], ['configdrive2', 'ConfigDrive2']] },
      { key: 'ciupgrade', label: 'Upgrade Packages', type: 'toggle' },
      { key: 'cicustom', label: 'Custom Cloud-Init Snippets', type: 'text' }
    ]
  },
  {
    id: 'advanced',
    title: 'Advanced',
    fields: [
      { key: 'args', label: 'Extra Hypervisor Args', type: 'textarea' },
      { key: 'hookscript', label: 'Hookscript', type: 'text' },
      { key: 'vmgenid', label: 'VM Generation ID', type: 'text' },
      { key: 'vmstatestorage', label: 'VM State Storage', type: 'text' },
      { key: 'migrate_downtime', label: 'Migration Downtime', type: 'text' },
      { key: 'migrate_speed', label: 'Migration Speed', type: 'text' },
      { key: 'lock', label: 'Lock State', type: 'text' }
    ]
  }
];

const FIELD_PRESETS = {
  tags: [{ label: '+desktop', value: 'desktop', mode: 'append' }, { label: '+gaming', value: 'gaming', mode: 'append' }, { label: '+prod', value: 'prod', mode: 'append' }],
  cpu: [{ label: 'portable', value: 'x86-64-v2-AES' }, { label: 'host', value: 'host' }],
  memory: [{ label: '4 GiB', value: '4096' }, { label: '8 GiB', value: '8192' }, { label: '16 GiB', value: '16384' }],
  balloon: [{ label: 'off', value: '0' }, { label: '2 GiB', value: '2048' }, { label: '4 GiB', value: '4096' }],
  boot: [{ label: 'disk', value: 'order=scsi0;ide2' }, { label: 'installer', value: 'order=ide2;scsi0' }, { label: 'network', value: 'order=net0;scsi0' }],
  agent: [{ label: 'enabled', value: 'enabled=1' }, { label: 'disabled', value: '0' }],
  hotplug: [{ label: 'default', value: 'network,disk,usb' }, { label: 'all', value: 'network,disk,cpu,memory,usb,cloudinit' }, { label: 'off', value: '0' }],
  audio0: [{ label: 'SPICE', value: 'device=ich9-intel-hda,driver=spice' }, { label: 'none', value: 'device=ich9-intel-hda,driver=none' }],
  ipconfig0: [{ label: 'DHCP', value: 'ip=dhcp' }, { label: 'static', value: 'ip=192.168.1.50/24,gw=192.168.1.1' }],
  nameserver: [{ label: 'router', value: '192.168.1.1' }, { label: '1.1.1.1', value: '1.1.1.1' }],
  rng0: [{ label: 'urandom', value: 'source=/dev/urandom' }]
};

const FIELD_HELP = {
  name: help('Name', 'Anzeigename in Inventar, Logs und Backups.', 'Niedriges Risiko; wirkt in der Verwaltung sofort.'),
  memory: help('Memory', 'Fester Arbeitsspeicher der VM in MiB.', 'Aenderungen an laufenden VMs brauchen je nach Gast Neustart oder Hotplug.'),
  balloon: help('Ballooning', 'Dynamischer RAM-Zielwert fuer Rueckgabe an den Host.', 'Fuer Gaming- und Latenz-Workloads vorsichtig einsetzen.'),
  cpu: help('CPU Type', 'CPU-Modell, das der Gast sieht.', 'host liefert maximale Features, erschwert aber Migration zwischen unterschiedlichen Hosts.'),
  boot: help('Boot Order', 'Reihenfolge der bootbaren Devices.', 'Nur vorhandene Devices wie scsi0, ide2 oder net0 eintragen.'),
  scsihw: help('SCSI Controller', 'Virtueller Storage-Controller fuer SCSI-Disks.', 'VirtIO SCSI ist fuer moderne Linux/Windows-Gaeste die robuste Standardwahl.'),
  agent: help('Guest Agent', 'Kommunikation mit dem Agent im Gast fuer Shutdown, IPs und Snapshots.', 'Aktivieren, wenn der Agent im Gast installiert ist.'),
  protection: help('Protection', 'Schutz gegen versehentliches Loeschen und riskante Aktionen.', 'Fuer produktive VMs aktivieren.'),
  cipassword: help('Cloud-Init Password', 'Optionales Initialpasswort fuer Cloud-Init.', 'Nicht speichern, wenn SSH-Keys reichen; private Keys niemals hier eintragen.'),
  sshkeys: help('SSH Keys', 'Oeffentliche SSH-Schluessel fuer Cloud-Init.', 'Nur Public Keys eintragen. Private Keys und Passwoerter bleiben ausserhalb der Config.')
};

const ALL_FIELDS = OPTION_GROUPS.flatMap((group) => group.fields);
const FIELD_BY_KEY = Object.fromEntries(ALL_FIELDS.map((field) => [field.key, field]));
const BOOLEAN_FIELDS = new Set(ALL_FIELDS.filter((field) => field.type === 'toggle').map((field) => field.key));
const NUMBER_FIELDS = new Set(ALL_FIELDS.filter((field) => field.type === 'number').map((field) => field.key));
const SENSITIVE_FIELDS = new Set(ALL_FIELDS.filter((field) => field.sensitive).map((field) => field.key));
const SIMPLE_FIELDS = new Set(ALL_FIELDS.filter((field) => field.important).map((field) => field.key));

const FIELD_VALIDATIONS = {
  name(value) {
    return String(value || '').trim() ? '' : 'Name darf nicht leer sein.';
  },
  memory(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < 16) return 'Memory muss mindestens 16 MiB sein.';
    if (numeric % 256 !== 0) return 'Memory sollte in 256-MiB-Schritten geplant werden.';
    return '';
  },
  cores(value) {
    return Number(value) >= 1 ? '' : 'Mindestens ein Core ist erforderlich.';
  },
  sockets(value) {
    return Number(value) >= 1 ? '' : 'Mindestens ein Socket ist erforderlich.';
  },
  boot(value) {
    const text = String(value || '').trim();
    return !text || /^order=[A-Za-z0-9;_-]+$/.test(text) || /^[acdn]{1,4}$/.test(text)
      ? ''
      : 'Boot Order sollte wie order=scsi0;ide2 aussehen.';
  },
  bootdisk(value) {
    const text = String(value || '').trim();
    return !text || /^(ide|sata|scsi|virtio)\d+$/.test(text)
      ? ''
      : 'Boot Disk sollte wie scsi0, virtio0 oder sata0 aussehen.';
  },
  ipconfig0(value) {
    const text = String(value || '').trim().toLowerCase();
    return !text || text === 'ip=dhcp' || /^ip=[^,]+\/[0-9]{1,2}(,gw=[^,]+)?$/.test(text)
      ? ''
      : 'IP Config 0 sollte ip=dhcp oder CIDR mit optionalem Gateway sein.';
  },
  nameserver(value) {
    const text = String(value || '').trim();
    return !text || /^[0-9a-fA-F:.,\s]+$/.test(text)
      ? ''
      : 'Nameserver sollte IPv4/IPv6-Adressen enthalten.';
  }
};

function help(title, summary, guidance) {
  return { title, summary, guidance };
}

function normalize(value) {
  return value == null ? '' : String(value);
}

function normalizeBoolean(value) {
  if (typeof value === 'boolean') return value;
  return ['1', 'true', 'yes', 'on', 'ja'].includes(String(value || '').trim().toLowerCase());
}

function normalizedFieldValue(config, key) {
  if (BOOLEAN_FIELDS.has(key)) {
    return normalizeBoolean(config[key]);
  }
  if (NUMBER_FIELDS.has(key)) {
    const text = normalize(config[key]).trim();
    return text === '' ? '' : Number(text);
  }
  return normalize(config[key]);
}

function parseParams(value) {
  const params = { __head: '' };
  String(value || '').split(',').forEach((part, index) => {
    const trimmed = part.trim();
    if (!trimmed) return;
    const eq = trimmed.indexOf('=');
    if (eq === -1) {
      if (index === 0 && !params.__head) params.__head = trimmed;
      else params[trimmed] = '1';
      return;
    }
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim();
    if (key) params[key] = val;
  });
  return params;
}

function joinParams(head, params, keys) {
  const parts = [];
  const primary = String(head || '').trim();
  if (primary) parts.push(primary);
  keys.forEach((key) => {
    const value = String(params[key] == null ? '' : params[key]).trim();
    if (value) parts.push(key + '=' + value);
  });
  Object.keys(params).sort().forEach((key) => {
    if (key === '__head' || keys.includes(key)) return;
    const value = String(params[key] == null ? '' : params[key]).trim();
    if (value) parts.push(key + '=' + value);
  });
  return parts.join(',');
}

function deviceKind(key) {
  if (DEVICE_PATTERNS.disk.test(key)) return 'disk';
  if (DEVICE_PATTERNS.network.test(key)) return 'network';
  if (DEVICE_PATTERNS.firmware.test(key)) return 'firmware';
  if (DEVICE_PATTERNS.passthrough.test(key)) return 'passthrough';
  return '';
}

function hardwareKeys(config) {
  return Object.keys(config || {}).filter((key) => Boolean(deviceKind(key))).sort(slotSort);
}

function unknownKeys(config) {
  const known = new Set([...VM_MAIN_KEYS, ...ALL_FIELDS.map((field) => field.key)]);
  hardwareKeys(config).forEach((key) => known.add(key));
  return Object.keys(config || {}).filter((key) => !known.has(key)).sort();
}

function slotSort(left, right) {
  const leftParts = String(left).match(/^([a-z-]+)(\d*)$/i) || [];
  const rightParts = String(right).match(/^([a-z-]+)(\d*)$/i) || [];
  if (leftParts[1] !== rightParts[1]) return String(left).localeCompare(String(right));
  return Number(leftParts[2] || 0) - Number(rightParts[2] || 0);
}

function nextSlot(config, prefix) {
  const used = new Set(Object.keys(config || {}).filter((key) => key.indexOf(prefix) === 0));
  const limit = SLOT_LIMITS[prefix] || 16;
  for (let idx = 0; idx < limit; idx += 1) {
    const candidate = prefix + idx;
    if (!used.has(candidate)) return candidate;
  }
  return prefix + limit;
}

function fieldGuide(key) {
  if (FIELD_HELP[key]) return FIELD_HELP[key];
  if (DISK_KEY_PATTERN.test(key)) return help(key, 'Virtuelle Disk, CD-ROM oder spezielles Storage-Device.', 'Storage-Werte nur mit Backup/Snapshot aendern.');
  if (NET_KEY_PATTERN.test(key)) return help(key, 'Virtuelle Netzwerkkarte der VM.', 'Bridge, VLAN, Firewall und Modell bestimmen die Netzpfade.');
  if (/^(hostpci|usb)/.test(key)) return help(key, 'Host-Device-Passthrough.', 'Nur fuer gepruefte Hardware verwenden; falsche Werte koennen den Start blockieren.');
  return help(key, 'VM-Konfigurationsoption.', 'Aenderung vor produktiver Nutzung pruefen.');
}

function riskForKey(key) {
  if (/^(args|hookscript|hostpci|usb|tpmstate|efidisk|rng|watchdog|machine|bios|scsihw|boot|bootdisk|amd-sev|intel-tdx)/.test(key)) {
    return 'Risiko: hoch';
  }
  if (/^(memory|balloon|sockets|cores|vcpus|cpu|cpulimit|affinity|numa|net|scsi|virtio|sata|ide|vga|audio)/.test(key)) {
    return 'Risiko: mittel';
  }
  return 'Risiko: niedrig';
}

function restartHintForKey(key) {
  if (/^(name|description|tags|protection|onboot|startup)$/.test(key)) {
    return 'Wirkt meist ohne Gast-Neustart.';
  }
  if (/^(ci|ipconfig|nameserver|searchdomain|sshkeys)/.test(key)) {
    return 'Greift beim naechsten Cloud-Init-Lauf.';
  }
  return 'Shutdown/Neustart wahrscheinlich erforderlich.';
}

function renderPresetRail(field) {
  const presets = FIELD_PRESETS[field.key] || [];
  if (!presets.length) return '';
  return '<div class="vm-control-presets">' + presets.map((preset) => {
    const mode = String(preset.mode || 'set');
    return '<button type="button" data-vm-preset-key="' + escapeHtml(field.key) + '" data-vm-preset-value="' + escapeHtml(String(preset.value || '')) + '" data-vm-preset-mode="' + escapeHtml(mode) + '">' + escapeHtml(String(preset.label || preset.value || 'Preset')) + '</button>';
  }).join('') + '</div>';
}

function renderHelpButton(key, label) {
  return '<button type="button" class="vm-config-help-button" data-vm-config-help="' + escapeHtml(key) + '" aria-label="Hilfe zu ' + escapeHtml(label) + '" title="Hilfe zu ' + escapeHtml(label) + '">?</button>';
}

function renderFieldCaption(field) {
  const label = String(field.label || field.key || '').trim();
  return '<span class="vm-config-field-caption"><span>' + escapeHtml(label) + '</span>' + renderHelpButton(field.key, label) + '</span>';
}

function renderField(field, config) {
  const key = field.key;
  const value = SENSITIVE_FIELDS.has(key) ? '' : normalizedFieldValue(config, key);
  const common = ' data-vm-config-field="' + escapeHtml(key) + '"';
  if (field.type === 'number') {
    const min = Number(field.min == null ? 0 : field.min);
    const max = Number(field.max == null ? Math.max(min + 1, Number(value || min) + 1) : field.max);
    const step = Number(field.step || 1);
    const rangeValue = String(value === '' ? min : value);
    return '' +
      '<div class="vm-control-card vm-control-card-range" data-vm-config-control="' + escapeHtml(key) + '">' +
      '<div class="vm-control-head">' + renderFieldCaption(field) + '<output data-vm-config-output="' + escapeHtml(key) + '">' + escapeHtml(value === '' ? 'leer' : String(value)) + '</output></div>' +
      '<input class="vm-control-range" type="range" data-vm-config-range="' + escapeHtml(key) + '" min="' + escapeHtml(String(min)) + '" max="' + escapeHtml(String(max)) + '" step="' + escapeHtml(String(step)) + '" value="' + escapeHtml(rangeValue) + '">' +
      '<div class="vm-control-foot"><span>' + escapeHtml(String(min)) + '</span><label><input class="vm-control-number" type="number"' + common + ' min="' + escapeHtml(String(min)) + '" max="' + escapeHtml(String(max)) + '" step="' + escapeHtml(String(step)) + '" value="' + escapeHtml(String(value)) + '"></label><span>' + escapeHtml(String(max)) + '</span></div>' +
      renderPresetRail(field) +
      '</div>';
  }
  if (field.type === 'toggle') {
    return '' +
      '<div class="vm-control-card vm-control-card-toggle" data-vm-config-control="' + escapeHtml(key) + '">' +
      '<div class="vm-control-head">' + renderFieldCaption(field) + '<span class="vm-toggle-state" data-vm-config-toggle-state="' + escapeHtml(key) + '">' + (value ? 'Aktiv' : 'Aus') + '</span></div>' +
      '<label class="vm-control-switch"><input type="checkbox"' + common + (value ? ' checked' : '') + '><span><i></i></span></label>' +
      renderPresetRail(field) +
      '</div>';
  }
  if (field.type === 'select') {
    const options = (field.options || []).map(([optionValue, optionLabel]) => {
      const selected = String(value) === String(optionValue) ? ' selected' : '';
      return '<option value="' + escapeHtml(String(optionValue)) + '"' + selected + '>' + escapeHtml(String(optionLabel)) + '</option>';
    }).join('');
    return '<label class="field">' + renderFieldCaption(field) + '<select' + common + '>' + options + '</select>' + renderPresetRail(field) + '</label>';
  }
  if (field.type === 'textarea') {
    return '<label class="field">' + renderFieldCaption(field) + '<textarea rows="4"' + common + '>' + escapeHtml(String(value)) + '</textarea>' + renderPresetRail(field) + '</label>';
  }
  const type = field.type === 'password' ? 'password' : 'text';
  const placeholder = SENSITIVE_FIELDS.has(key) && normalize(config[key]) ? 'gesetzt - leer lassen fuer keine Aenderung' : '';
  return '<label class="field">' + renderFieldCaption(field) + '<input type="' + type + '"' + common + ' value="' + escapeHtml(String(value)) + '" placeholder="' + escapeHtml(placeholder) + '">' + renderPresetRail(field) + '</label>';
}

function renderParamInput(label, key, value, kind) {
  return '<label><span>' + escapeHtml(label) + '</span><input data-vm-device-param="' + escapeHtml(key) + '" data-vm-device-kind="' + escapeHtml(kind) + '" value="' + escapeHtml(String(value || '')) + '"></label>';
}

function renderDeviceEditor(key, value) {
  const kind = deviceKind(key);
  const params = parseParams(value);
  if (kind === 'disk') {
    const diskKeys = ['size', 'cache', 'discard', 'iothread', 'ssd', 'backup', 'replicate', 'media', 'format', 'serial', 'ro'];
    const diskHead = params.file || params.__head;
    return '' +
      '<div class="vm-device-fields" data-vm-device-compose="disk">' +
      renderParamInput('Volume / File', '__head', diskHead, 'disk') +
      diskKeys.map((param) => renderParamInput(param, param, params[param], 'disk')).join('') +
      '</div>';
  }
  if (kind === 'network') {
    const model = params.model || params.__head || 'virtio';
    const netKeys = ['bridge', 'macaddr', 'firewall', 'tag', 'trunks', 'queues', 'rate', 'mtu', 'link_down'];
    return '' +
      '<div class="vm-device-fields" data-vm-device-compose="network">' +
      renderParamInput('Model', '__head', model, 'network') +
      netKeys.map((param) => renderParamInput(param, param, params[param], 'network')).join('') +
      '</div>';
  }
  return '<label class="field vm-device-raw"><span>Value</span><input class="mono" data-vm-device-raw value="' + escapeHtml(normalize(value)) + '"></label>';
}

function renderDeviceRow(key, value, isNew) {
  return '' +
    '<article class="vm-device-row" data-vm-device-row data-vm-config-item="' + escapeHtml(key) + '" data-vm-device-key="' + escapeHtml(key) + '" data-vm-device-new="' + (isNew ? '1' : '0') + '">' +
    '<div class="vm-device-row-head">' +
    '<div><strong>' + escapeHtml(key) + '</strong><span>' + escapeHtml(deviceKind(key) || 'option') + '</span></div>' +
    '<button type="button" class="button ghost small" data-vm-device-remove="' + escapeHtml(key) + '">Remove</button>' +
    '</div>' +
    renderDeviceEditor(key, value) +
    '</article>';
}

function renderDeviceSection(title, kind, entries, buttons) {
  return '' +
    '<section class="detail-section vm-config-device-section" data-vm-device-section="' + escapeHtml(kind) + '">' +
    '<div class="section-head"><div><h3>' + escapeHtml(title) + '</h3></div><div class="vm-device-add-bar">' + buttons.map((button) => {
      return '<button type="button" class="button ghost small" data-vm-device-add="' + escapeHtml(button.prefix) + '" data-vm-device-template="' + escapeHtml(button.template) + '">' + escapeHtml(button.label) + '</button>';
    }).join('') + '</div></div>' +
    '<div class="vm-device-list" data-vm-device-list="' + escapeHtml(kind) + '">' +
    (entries.length ? entries.map(([key, value]) => renderDeviceRow(key, value, false)).join('') : '<div class="empty-card">Keine Eintraege.</div>') +
    '</div>' +
    '</section>';
}

function renderHardware(config) {
  const keys = hardwareKeys(config);
  const byKind = { disk: [], network: [], firmware: [], passthrough: [] };
  keys.forEach((key) => byKind[deviceKind(key)].push([key, normalize(config[key])]));
  return '' +
    renderDeviceSection('Disks & Drives', 'disk', byKind.disk, [
      { label: '+ SCSI', prefix: 'scsi', template: 'local:32,format=qcow2,iothread=1,discard=on' },
      { label: '+ VirtIO', prefix: 'virtio', template: 'local:32,format=qcow2,iothread=1' },
      { label: '+ SATA', prefix: 'sata', template: 'local:32,format=qcow2' },
      { label: '+ IDE/CD-ROM', prefix: 'ide', template: 'local:iso/installer.iso,media=cdrom' }
    ]) +
    renderDeviceSection('Network', 'network', byKind.network, [
      { label: '+ NIC', prefix: 'net', template: 'virtio,bridge=vmbr0,firewall=1' }
    ]) +
    renderDeviceSection('Firmware & Security Devices', 'firmware', byKind.firmware, [
      { label: '+ EFI Disk', prefix: 'efidisk', template: 'local:0,efitype=4m,pre-enrolled-keys=1' },
      { label: '+ TPM', prefix: 'tpmstate', template: 'local:0,version=v2.0' }
    ]) +
    renderDeviceSection('Passthrough & Special Devices', 'passthrough', byKind.passthrough, [
      { label: '+ PCI', prefix: 'hostpci', template: 'host=0000:00:00.0,pcie=1' },
      { label: '+ USB', prefix: 'usb', template: 'host=0000:0000,usb3=1' },
      { label: '+ Serial', prefix: 'serial', template: 'socket' },
      { label: '+ RNG', prefix: 'rng', template: 'source=/dev/urandom' },
      { label: '+ VirtioFS', prefix: 'virtiofs', template: 'dirid=share0,cache=auto' }
    ]);
}

function renderHelpModal() {
  return '' +
    '<div class="vm-config-help-modal" data-vm-config-help-modal hidden aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="vm-config-help-title">' +
    '<div class="vm-config-help-backdrop" data-vm-config-help-close></div>' +
    '<div class="vm-config-help-dialog">' +
    '<div class="vm-config-help-head"><div><span class="vm-config-guide-kicker">Beagle Guide Layer</span><h3 id="vm-config-help-title" data-vm-config-help-title>Option</h3></div><button type="button" class="vm-config-help-close" data-vm-config-help-close aria-label="Hilfe schliessen">x</button></div>' +
    '<div class="vm-config-help-body"><section><h4>Was ist das?</h4><p data-vm-config-help-summary></p></section><section><h4>Wann aendern?</h4><p data-vm-config-help-guidance></p></section><section><h4>Risiko & Neustart</h4><p data-vm-config-help-risk></p><p data-vm-config-help-restart></p></section><section><h4>Aktueller Wert</h4><pre data-vm-config-help-current></pre></section></div>' +
    '<div class="vm-config-help-actions"><button type="button" class="primary" data-vm-config-help-close>Verstanden</button></div>' +
    '</div></div>';
}

function renderGuidePanel() {
  return '' +
    '<aside class="vm-config-guide-panel" data-vm-config-guide-panel aria-live="polite">' +
    '<div class="vm-config-guide-panel-head"><span>Beagle Info View</span><strong data-vm-config-guide-panel-title>Feldhilfe</strong></div>' +
    '<p data-vm-config-guide-panel-summary>Feld fokussieren oder Hilfe oeffnen.</p>' +
    '<div class="vm-config-guide-panel-meta"><span data-vm-config-guide-panel-risk>Risiko: kontextabhaengig</span><span data-vm-config-guide-panel-restart>Neustart: kontextabhaengig</span></div>' +
    '</aside>';
}

function renderEnterpriseConsole() {
  return '' +
    '<section class="detail-section vm-enterprise-console">' +
    '<div class="vm-enterprise-console-head"><div><h3>Enterprise Change Console</h3></div><div class="vm-enterprise-impact"><span data-vm-enterprise-risk="low">Risiko: niedrig</span><span data-vm-enterprise-restart="soft">Neustart: unkritisch</span></div></div>' +
    '<div class="vm-enterprise-toolbar"><label><span>Suche Einstellung</span><input type="search" data-vm-config-filter placeholder="memory, boot, net0"></label><label class="check-label"><input type="checkbox" data-vm-show-changed><span>Nur geaenderte Felder</span></label></div>' +
    '<div class="vm-enterprise-summary"><div><strong data-vm-change-count>0</strong><span>Aenderungen</span></div><div><strong data-vm-warning-count>0</strong><span>Pruefhinweise</span></div><div><strong data-vm-filter-count>0</strong><span>sichtbar</span></div></div>' +
    '<p class="vm-enterprise-change-list" data-vm-change-list>Noch keine Aenderungen.</p>' +
    '</section>';
}

function renderModeSwitcher(mode) {
  const simpleActive = mode !== 'pro';
  return '' +
    '<section class="detail-section vm-mode-switcher">' +
    '<div class="vm-mode-switcher-head"><h3>Bedienmodus</h3><div class="vm-mode-switcher-buttons" role="tablist" aria-label="VM Konfigurationsmodus">' +
    '<button type="button" data-vm-mode="simple" aria-pressed="' + (simpleActive ? 'true' : 'false') + '" class="' + (simpleActive ? 'is-active' : '') + '">Einfach</button>' +
    '<button type="button" data-vm-mode="pro" aria-pressed="' + (!simpleActive ? 'true' : 'false') + '" class="' + (!simpleActive ? 'is-active' : '') + '">Profi</button>' +
    '</div></div><p class="muted">Einfach zeigt nur die wichtigsten Einstellungen. Profi blendet alle Optionen ein.</p></section>';
}

function renderInterfaces(interfaces) {
  if (!Array.isArray(interfaces) || !interfaces.length) return '';
  let html = '<section class="detail-section"><h3>Guest Agent Interfaces</h3>';
  interfaces.forEach((iface) => {
    const addrs = (iface['ip-addresses'] || []).map((addr) => String(addr['ip-address'] || '') + (addr.prefix ? '/' + addr.prefix : '')).join(', ');
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
    this.mode = 'simple';
    this.filterText = '';
    this.showChangedOnly = false;
    try {
      const savedMode = String(localStorage.getItem('beagle.vmConfigEditor.mode') || '').trim().toLowerCase();
      if (savedMode === 'pro' || savedMode === 'simple') this.mode = savedMode;
    } catch (error) {
      void error;
    }
  }

  render() {
    let html = '<form class="vm-config-editor vm-config-editor-v2" data-vm-config-editor data-vmid="' + escapeHtml(String(this.vmid)) + '">';
    html += '<section class="detail-section vm-config-hero"><div class="section-head"><div><h3>VM Konfiguration</h3><p class="muted">Beagle-native KVM/libvirt API, Proxmox-nahe Optionsabdeckung.</p></div><button type="submit" class="primary">Speichern</button></div><div class="banner banner-info" data-vm-config-status hidden></div></section>';
    html += renderModeSwitcher(this.mode);
    html += renderEnterpriseConsole();
    html += renderGuidePanel();
    OPTION_GROUPS.forEach((group) => {
      html += '<section class="detail-section vm-config-group" data-vm-config-group="' + escapeHtml(group.id) + '"><h3>' + escapeHtml(group.title) + '</h3><div class="vm-config-grid">';
      group.fields.forEach((field) => {
        html += '<div class="vm-config-item" data-vm-config-item="' + escapeHtml(field.key) + '" data-vm-simple="' + (SIMPLE_FIELDS.has(field.key) ? '1' : '0') + '">' + renderField(field, this.config) + '</div>';
      });
      html += '</div></section>';
    });
    html += renderHardware(this.config);
    const extraKeys = unknownKeys(this.config);
    if (extraKeys.length) {
      html += '<section class="detail-section vm-config-group"><h3>Weitere Optionen</h3><div class="vm-config-grid">';
      extraKeys.forEach((key) => {
        html += '<div class="vm-config-item" data-vm-config-item="' + escapeHtml(key) + '" data-vm-simple="0"><label class="field">' + renderFieldCaption({ key, label: key }) + '<input class="mono" data-vm-config-field="' + escapeHtml(key) + '" value="' + escapeHtml(normalize(this.config[key])) + '"></label></div>';
      });
      html += '</div></section>';
    }
    html += renderInterfaces(this.interfaces);
    html += renderHelpModal();
    html += '</form>';
    return html;
  }

  bind(root) {
    const form = root && root.querySelector ? root.querySelector('[data-vm-config-editor]') : null;
    if (!form) return;
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.save(form);
    });
    form.addEventListener('click', (event) => {
      const modeButton = event.target && event.target.closest ? event.target.closest('[data-vm-mode]') : null;
      if (modeButton) {
        event.preventDefault();
        this.setMode(form, String(modeButton.getAttribute('data-vm-mode') || 'simple'));
        return;
      }
      const presetButton = event.target && event.target.closest ? event.target.closest('[data-vm-preset-key]') : null;
      if (presetButton) {
        event.preventDefault();
        this.applyPreset(form, presetButton);
        return;
      }
      const addButton = event.target && event.target.closest ? event.target.closest('[data-vm-device-add]') : null;
      if (addButton) {
        event.preventDefault();
        this.addDevice(form, addButton);
        return;
      }
      const removeButton = event.target && event.target.closest ? event.target.closest('[data-vm-device-remove]') : null;
      if (removeButton) {
        event.preventDefault();
        this.removeDevice(form, removeButton);
        return;
      }
      const helpButton = event.target && event.target.closest ? event.target.closest('[data-vm-config-help]') : null;
      if (helpButton) {
        event.preventDefault();
        this.openHelp(form, String(helpButton.getAttribute('data-vm-config-help') || ''));
        return;
      }
      const closeButton = event.target && event.target.closest ? event.target.closest('[data-vm-config-help-close]') : null;
      if (closeButton) {
        event.preventDefault();
        this.closeHelp(form);
      }
    });
    form.addEventListener('mouseover', (event) => {
      const key = this.keyFromGuideTarget(event.target);
      if (key) this.updateGuidePanel(form, key);
    });
    form.addEventListener('focusin', (event) => {
      const key = this.keyFromGuideTarget(event.target);
      if (key) this.updateGuidePanel(form, key);
    });
    form.addEventListener('input', (event) => {
      if (event.target && event.target.matches && event.target.matches('[data-vm-config-filter]')) {
        this.filterText = String(event.target.value || '').trim().toLowerCase();
      }
      this.syncControlSurface(form, event.target);
    });
    form.addEventListener('change', (event) => {
      if (event.target && event.target.matches && event.target.matches('[data-vm-show-changed]')) {
        this.showChangedOnly = Boolean(event.target.checked);
      }
      this.syncControlSurface(form, event.target);
    });
    form.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') this.closeHelp(form);
    });
    form.querySelectorAll('[data-vm-device-add]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        this.addDevice(form, button);
      });
    });
    this.applyVisibility(form);
    this.refreshEnterpriseConsole(form);
  }

  applyPreset(form, button) {
    const key = String(button.getAttribute('data-vm-preset-key') || '').trim();
    const value = String(button.getAttribute('data-vm-preset-value') || '');
    const mode = String(button.getAttribute('data-vm-preset-mode') || 'set').trim().toLowerCase();
    const control = key ? form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]') : null;
    if (!control) return;
    if (BOOLEAN_FIELDS.has(key)) {
      control.checked = normalizeBoolean(value);
    } else if (mode === 'append') {
      const current = String(control.value || '').trim();
      control.value = current && !current.split(',').map((token) => token.trim()).includes(value) ? current + ',' + value : (current || value);
    } else {
      control.value = value;
    }
    this.syncControlSurface(form, control);
    this.refreshEnterpriseConsole(form);
  }

  setMode(form, mode) {
    this.mode = mode === 'pro' ? 'pro' : 'simple';
    try {
      localStorage.setItem('beagle.vmConfigEditor.mode', this.mode);
    } catch (error) {
      void error;
    }
    this.applyVisibility(form);
    this.refreshEnterpriseConsole(form);
  }

  addDevice(form, button) {
    const prefix = String(button.getAttribute('data-vm-device-add') || '').trim();
    const template = String(button.getAttribute('data-vm-device-template') || '').trim();
    if (!prefix) return;
    const currentKeys = Object.assign({}, this.config);
    form.querySelectorAll('[data-vm-device-row]').forEach((row) => {
      currentKeys[String(row.getAttribute('data-vm-device-key') || '')] = true;
    });
    const key = nextSlot(currentKeys, prefix);
    const kind = deviceKind(key);
    const list = form.querySelector('[data-vm-device-list="' + CSS.escape(kind || 'passthrough') + '"]') || form.querySelector('[data-vm-device-list]');
    if (!list) return;
    const empty = list.querySelector('.empty-card');
    if (empty) empty.remove();
    list.insertAdjacentHTML('beforeend', renderDeviceRow(key, template, true));
    this.refreshEnterpriseConsole(form);
  }

  removeDevice(form, button) {
    const row = button.closest('[data-vm-device-row]');
    if (!row) return;
    const key = String(row.getAttribute('data-vm-device-key') || '').trim();
    if (Object.prototype.hasOwnProperty.call(this.config, key)) {
      row.setAttribute('data-vm-device-deleted', '1');
      row.hidden = true;
    } else {
      row.remove();
    }
    this.refreshEnterpriseConsole(form);
  }

  applyVisibility(form) {
    const simple = this.mode !== 'pro';
    form.setAttribute('data-vm-mode', simple ? 'simple' : 'pro');
    form.querySelectorAll('[data-vm-mode]').forEach((button) => {
      const selected = String(button.getAttribute('data-vm-mode') || '') === (simple ? 'simple' : 'pro');
      button.classList.toggle('is-active', selected);
      button.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    let visibleCount = 0;
    form.querySelectorAll('[data-vm-config-item]').forEach((item) => {
      const key = String(item.getAttribute('data-vm-config-item') || '').trim();
      const isHardware = Boolean(item.closest('[data-vm-device-section]'));
      const simpleAllowed = isHardware || !simple || String(item.getAttribute('data-vm-simple') || '0') === '1';
      const matchesFilter = !this.filterText || (key + ' ' + item.textContent).toLowerCase().includes(this.filterText);
      const changedAllowed = !this.showChangedOnly || this.isKeyChanged(form, key) || item.getAttribute('data-vm-device-deleted') === '1';
      const keep = simpleAllowed && matchesFilter && changedAllowed && item.getAttribute('data-vm-device-deleted') !== '1';
      item.hidden = !keep;
      if (keep) visibleCount += 1;
    });
    const filterCount = form.querySelector('[data-vm-filter-count]');
    if (filterCount) filterCount.textContent = String(visibleCount);
  }

  baselineValueForKey(key) {
    return normalizedFieldValue(this.config, key);
  }

  controlValueForKey(form, key) {
    const control = form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]');
    if (control) {
      if (BOOLEAN_FIELDS.has(key)) return Boolean(control.checked);
      if (NUMBER_FIELDS.has(key)) {
        const text = String(control.value || '').trim();
        return text === '' ? '' : Number(text);
      }
      return String(control.value || '').trim();
    }
    const row = form.querySelector('[data-vm-device-key="' + CSS.escape(key) + '"]');
    if (row) return this.collectDeviceValue(row);
    return normalize(this.config[key]);
  }

  isKeyChanged(form, key) {
    if (!key) return false;
    if (form.querySelector('[data-vm-device-key="' + CSS.escape(key) + '"][data-vm-device-deleted="1"]')) return true;
    return String(this.controlValueForKey(form, key)) !== String(this.baselineValueForKey(key));
  }

  validateKey(form, key) {
    const validator = FIELD_VALIDATIONS[key];
    if (typeof validator !== 'function') return '';
    return String(validator(this.controlValueForKey(form, key)) || '').trim();
  }

  severityForKey(key) {
    return riskForKey(key).includes('hoch') ? 'high' : (riskForKey(key).includes('mittel') ? 'medium' : 'low');
  }

  restartImpactForKey(key) {
    if (/^(name|description|tags|protection|onboot|startup)$/.test(key)) return 'soft';
    if (/^(ci|ipconfig|nameserver|searchdomain|sshkeys)/.test(key)) return 'pending';
    return 'hard';
  }

  refreshEnterpriseConsole(form) {
    const changed = [];
    const warnings = [];
    form.querySelectorAll('[data-vm-config-field], [data-vm-device-row]').forEach((node) => {
      const key = String(node.getAttribute('data-vm-config-field') || node.getAttribute('data-vm-device-key') || '').trim();
      if (!key) return;
      const warning = this.validateKey(form, key);
      if (warning) warnings.push(key + ': ' + warning);
      if (node.matches && node.matches('[data-vm-config-field]')) node.classList.toggle('vm-input-invalid', Boolean(warning));
      if (this.isKeyChanged(form, key)) changed.push(key);
    });
    const countNode = form.querySelector('[data-vm-change-count]');
    if (countNode) countNode.textContent = String(changed.length);
    const warningCount = form.querySelector('[data-vm-warning-count]');
    if (warningCount) warningCount.textContent = String(warnings.length);
    const listNode = form.querySelector('[data-vm-change-list]');
    if (listNode) listNode.textContent = changed.length ? 'Aenderungsumfang: ' + changed.slice(0, 14).join(', ') + (changed.length > 14 ? ' ...' : '') : 'Noch keine Aenderungen.';
    const highest = changed.reduce((acc, key) => Math.max(acc, this.severityForKey(key) === 'high' ? 3 : this.severityForKey(key) === 'medium' ? 2 : 1), 1);
    const riskNode = form.querySelector('[data-vm-enterprise-risk]');
    if (riskNode) {
      const level = highest === 3 ? 'high' : highest === 2 ? 'medium' : 'low';
      riskNode.textContent = level === 'high' ? 'Risiko: hoch' : level === 'medium' ? 'Risiko: mittel' : 'Risiko: niedrig';
      riskNode.setAttribute('data-vm-enterprise-risk', level);
    }
    const restart = changed.reduce((acc, key) => Math.max(acc, this.restartImpactForKey(key) === 'hard' ? 3 : this.restartImpactForKey(key) === 'pending' ? 2 : 1), 1);
    const restartNode = form.querySelector('[data-vm-enterprise-restart]');
    if (restartNode) {
      const level = restart === 3 ? 'hard' : restart === 2 ? 'pending' : 'soft';
      restartNode.textContent = level === 'hard' ? 'Neustart: wahrscheinlich' : level === 'pending' ? 'Neustart: pending' : 'Neustart: unkritisch';
      restartNode.setAttribute('data-vm-enterprise-restart', level);
    }
    this.applyVisibility(form);
  }

  keyFromGuideTarget(target) {
    if (!target || !target.closest) return '';
    const explicit = target.closest('[data-vm-config-help]');
    if (explicit) return String(explicit.getAttribute('data-vm-config-help') || '').trim();
    const field = target.closest('[data-vm-config-field]');
    if (field) return String(field.getAttribute('data-vm-config-field') || '').trim();
    const row = target.closest('[data-vm-device-key]');
    return row ? String(row.getAttribute('data-vm-device-key') || '').trim() : '';
  }

  syncControlSurface(form, target) {
    if (!target || !target.getAttribute) return;
    const rangeKey = String(target.getAttribute('data-vm-config-range') || '').trim();
    const fieldKey = String(target.getAttribute('data-vm-config-field') || '').trim();
    const key = rangeKey || fieldKey || String((target.closest('[data-vm-device-row]') || {}).getAttribute?.('data-vm-device-key') || '');
    if (!key) return;
    if (NUMBER_FIELDS.has(key)) {
      const range = form.querySelector('[data-vm-config-range="' + CSS.escape(key) + '"]');
      const number = form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]');
      const output = form.querySelector('[data-vm-config-output="' + CSS.escape(key) + '"]');
      const value = String(target.value || '').trim();
      if (range && target !== range) range.value = value;
      if (number && target !== number) number.value = value;
      if (output) output.textContent = value || 'leer';
    }
    if (BOOLEAN_FIELDS.has(key)) {
      const stateLabel = form.querySelector('[data-vm-config-toggle-state="' + CSS.escape(key) + '"]');
      if (stateLabel) stateLabel.textContent = target.checked ? 'Aktiv' : 'Aus';
    }
    this.refreshEnterpriseConsole(form);
  }

  updateGuidePanel(form, key) {
    const panel = form.querySelector('[data-vm-config-guide-panel]');
    if (!panel || !key) return;
    const guide = fieldGuide(key);
    panel.querySelector('[data-vm-config-guide-panel-title]').textContent = guide.title || key;
    panel.querySelector('[data-vm-config-guide-panel-summary]').textContent = guide.summary || '';
    panel.querySelector('[data-vm-config-guide-panel-risk]').textContent = riskForKey(key);
    panel.querySelector('[data-vm-config-guide-panel-restart]').textContent = restartHintForKey(key);
  }

  openHelp(form, key) {
    const modal = form.querySelector('[data-vm-config-help-modal]');
    if (!modal) return;
    const guide = fieldGuide(key);
    const control = form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]');
    const current = control ? (control.type === 'checkbox' ? (control.checked ? 'An' : 'Aus') : String(control.value || '')) : this.controlValueForKey(form, key);
    modal.querySelector('[data-vm-config-help-title]').textContent = guide.title || key;
    modal.querySelector('[data-vm-config-help-summary]').textContent = guide.summary || '';
    modal.querySelector('[data-vm-config-help-guidance]').textContent = guide.guidance || '';
    modal.querySelector('[data-vm-config-help-risk]').textContent = riskForKey(key);
    modal.querySelector('[data-vm-config-help-restart]').textContent = restartHintForKey(key);
    modal.querySelector('[data-vm-config-help-current]').textContent = current || '(leer)';
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    const close = modal.querySelector('[data-vm-config-help-close]');
    if (close && close.focus) close.focus();
  }

  closeHelp(form) {
    const modal = form.querySelector('[data-vm-config-help-modal]');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  collectDeviceValue(row) {
    const raw = row.querySelector('[data-vm-device-raw]');
    if (raw) return String(raw.value || '').trim();
    const compose = row.querySelector('[data-vm-device-compose]');
    if (!compose) return '';
    const params = {};
    compose.querySelectorAll('[data-vm-device-param]').forEach((input) => {
      params[String(input.getAttribute('data-vm-device-param') || '')] = String(input.value || '').trim();
    });
    const kind = String(compose.getAttribute('data-vm-device-compose') || '');
    if (kind === 'disk') {
      return joinParams(params.__head, params, ['size', 'cache', 'discard', 'iothread', 'ssd', 'backup', 'replicate', 'media', 'format', 'serial', 'ro']);
    }
    if (kind === 'network') {
      delete params.model;
      return joinParams(params.__head || 'virtio', params, ['bridge', 'macaddr', 'firewall', 'tag', 'trunks', 'queues', 'rate', 'mtu', 'link_down']);
    }
    return '';
  }

  collect(form) {
    const updates = {};
    const deletes = [];
    form.querySelectorAll('[data-vm-config-field]').forEach((control) => {
      const key = String(control.getAttribute('data-vm-config-field') || '').trim();
      if (!key) return;
      if (SENSITIVE_FIELDS.has(key) && !String(control.value || '').trim()) return;
      let value;
      if (BOOLEAN_FIELDS.has(key)) value = Boolean(control.checked);
      else if (NUMBER_FIELDS.has(key)) {
        const text = String(control.value || '').trim();
        value = text === '' ? '' : Number(text);
      } else value = String(control.value || '').trim();
      if (String(value) !== String(this.baselineValueForKey(key))) updates[key] = value;
    });
    form.querySelectorAll('[data-vm-device-row]').forEach((row) => {
      const key = String(row.getAttribute('data-vm-device-key') || '').trim();
      if (!key) return;
      if (row.getAttribute('data-vm-device-deleted') === '1') {
        deletes.push(key);
        return;
      }
      const value = this.collectDeviceValue(row);
      if (String(value) !== String(normalize(this.config[key]))) updates[key] = value;
    });
    return { updates, delete: deletes };
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
    if (!Object.keys(payload.updates).length && !payload.delete.length) {
      this.setLocalStatus(form, 'Keine Aenderungen.', 'info');
      return Promise.resolve(null);
    }
    const button = form.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    this.setLocalStatus(form, 'Speichere VM-Konfiguration ...', 'info');
    return putJson('/virtualization/vms/' + encodeURIComponent(String(this.vmid)) + '/config', payload).then((result) => {
      const next = Object.assign({}, this.config, payload.updates);
      payload.delete.forEach((key) => delete next[key]);
      this.config = Object.assign({}, result.config || next);
      this.setLocalStatus(form, 'Gespeichert: ' + [...Object.keys(payload.updates), ...payload.delete.map((key) => '-' + key)].join(', '), 'ok');
      return result;
    }).catch((error) => {
      this.setLocalStatus(form, 'Speichern fehlgeschlagen: ' + error.message, 'bad');
      throw error;
    }).finally(() => {
      if (button) button.disabled = false;
    });
  }
}

export function renderVmConfigEditor(options) {
  return new VmConfigEditor(options).render();
}

export function bindVmConfigEditor(root, options) {
  new VmConfigEditor(options).bind(root);
}

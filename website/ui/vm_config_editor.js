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

const CONTROL_LIMITS = {
  sockets: { min: 1, max: 4, step: 1, unit: 'socket' },
  cores: { min: 1, max: 32, step: 1, unit: 'cores' },
  vcpus: { min: 0, max: 32, step: 1, unit: 'vCPU' },
  memory: { min: 16, max: 131072, step: 256, unit: 'MB' },
  balloon: { min: 0, max: 131072, step: 256, unit: 'MB' },
  cpuunits: { min: 1, max: 10000, step: 100, unit: 'weight' }
};

const FIELD_HELP = {
  name: help('Name', 'Der Anzeigename der VM. Er hilft dir, die Maschine in Listen, Logs und Backups eindeutig wiederzufinden.', 'Aendere ihn frei, solange er eindeutig und gut lesbar bleibt.', ['win11-gaming', 'office-terminal-01']),
  description: help('Beschreibung', 'Freitext fuer Zweck, Besitzer, Besonderheiten oder Wartungshinweise.', 'Hier kannst du notieren, warum es diese VM gibt und worauf man achten muss.', ['Gaming VM fuer Wohnzimmer', 'Nicht loeschen, Buchhaltung']),
  tags: help('Tags', 'Kurze Schlagwoerter zum Sortieren und Filtern.', 'Nutze einfache Begriffe ohne lange Saetze.', ['gaming,windows', 'prod,buchhaltung']),
  ostype: help('OS Type', 'Hinweis fuer den Hypervisor, welches Betriebssystem in der VM laeuft.', 'Aendere das nur, wenn du das Gast-System wirklich wechselst oder die VM falsch erkannt wurde.', ['l26 fuer Linux', 'win11 fuer Windows 11']),
  protection: help('Protection', 'Schutzschalter gegen versehentliches Loeschen oder gefaehrliche Aktionen.', 'Aktiviere ihn fuer wichtige VMs. Zum absichtlichen Loeschen musst du ihn spaeter wieder deaktivieren.', ['An fuer Produktiv-VMs', 'Aus fuer Test-VMs']),
  template: help('Template', 'Markiert die VM als Vorlage fuer neue Maschinen.', 'Eine Vorlage wird normalerweise nicht wie ein normaler Desktop benutzt.', ['An fuer Golden Image', 'Aus fuer normale VM']),
  sockets: help('Sockets', 'Virtuelle CPU-Sockel. Zusammen mit Cores ergibt das die sichtbare CPU-Struktur.', 'Fuer Laien meist auf 1 lassen und lieber Cores anpassen.', ['1 Socket mit 4 Cores']),
  cores: help('Cores', 'Anzahl der CPU-Kerne pro Socket.', 'Mehr Kerne machen die VM nicht automatisch schneller, wenn der Host ausgelastet ist.', ['2 fuer kleine VM', '4 bis 8 fuer Gaming/Workstation']),
  vcpus: help('vCPUs', 'Optionales Limit fuer aktiv nutzbare virtuelle CPUs.', 'Leer oder 0 bedeutet normalerweise: alle konfigurierten Cores nutzen.', ['0', '4']),
  cpu: help('CPU Type', 'Legt fest, welches CPU-Modell die VM sieht.', 'host ist oft am schnellsten, kann Migration zwischen sehr unterschiedlichen Hosts aber erschweren.', ['host', 'x86-64-v2-AES']),
  memory: help('Memory MB', 'Arbeitsspeicher der VM in Megabyte.', 'Zu wenig RAM macht das Gast-System langsam. Zu viel RAM fehlt anderen VMs.', ['4096 fuer 4 GB', '8192 fuer 8 GB']),
  balloon: help('Balloon MB', 'Dynamischer Mindest-/Zielwert fuer RAM-Ballooning.', 'Damit kann der Host Speicher zurueckholen. Fuer Gaming oder sensible Workloads eher vorsichtig nutzen.', ['0 zum Deaktivieren', '2048 als Mindestwert']),
  cpuunits: help('CPU Units', 'Relative CPU-Prioritaet, wenn mehrere VMs gleichzeitig CPU brauchen.', 'Hoehere Werte bekommen mehr Anteil bei Last, aber keine garantierte Extra-Leistung.', ['1000 normal', '2000 wichtiger']),
  cpulimit: help('CPU Limit', 'Harte Obergrenze fuer CPU-Nutzung.', 'Nur setzen, wenn eine VM andere Workloads nicht stoeren darf.', ['leer fuer kein Limit', '2 fuer maximal etwa 2 CPUs']),
  numa: help('NUMA', 'Optimierung fuer grosse VMs auf Hosts mit mehreren Speicher-/CPU-Bereichen.', 'Bei kleinen VMs meist aus lassen. Bei sehr grossen VMs kann es Performance verbessern.', ['Aus fuer Standard', 'An fuer grosse Server-VMs']),
  affinity: help('CPU Affinity', 'Bindet die VM an bestimmte Host-CPU-Kerne.', 'Nur fuer Spezialfaelle. Falsche Werte koennen Performance verschlechtern.', ['0-3', '4,5,6,7']),
  bios: help('BIOS', 'Firmware-Modus der VM.', 'SeaBIOS ist klassisch, OVMF ist UEFI. Windows 11 braucht meist UEFI/OVMF plus TPM.', ['seabios', 'ovmf']),
  machine: help('Machine', 'Virtueller Chipsatz bzw. Maschinentyp.', 'q35 ist modern und meist passend fuer neue Windows/Linux-VMs.', ['q35', 'pc-i440fx']),
  boot: help('Boot Order', 'Reihenfolge, in der die VM von Disk, ISO oder Netzwerk startet.', 'Aendere das, wenn die VM von Installations-ISO oder anderer Disk starten soll.', ['order=scsi0;ide2', 'cdn']),
  bootdisk: help('Boot Disk', 'Die bevorzugte Start-Festplatte.', 'Muss zu einer vorhandenen Disk wie scsi0 oder virtio0 passen.', ['scsi0', 'virtio0']),
  scsihw: help('SCSI Controller', 'Virtueller Controller fuer SCSI-Disks.', 'VirtIO SCSI ist fuer moderne VMs meist die beste Wahl.', ['virtio-scsi-single', 'lsi']),
  agent: help('QEMU Agent', 'Erlaubt bessere Infos und Aktionen im Gast, wenn der Agent im Gast installiert ist.', 'Aktivieren ist sinnvoll, wenn qemu-guest-agent in der VM installiert ist.', ['enabled=1', '1']),
  onboot: help('On Boot', 'Startet die VM automatisch, wenn der Host startet.', 'Aktiviere das fuer Dienste, die nach einem Neustart sofort wieder laufen sollen.', ['An fuer Server', 'Aus fuer manuelle Desktops']),
  startup: help('Startup', 'Feinsteuerung fuer automatische Startreihenfolge und Wartezeiten.', 'Nur noetig, wenn mehrere VMs in bestimmter Reihenfolge hochfahren sollen.', ['order=2,up=30', 'order=1']),
  tablet: help('Tablet', 'Virtuelles Tablet fuer praezisere Mausposition in grafischen Konsolen.', 'Meist anlassen, ausser Spezial-Setups brauchen es nicht.', ['An fuer Desktop-VMs']),
  acpi: help('ACPI', 'Ermoeglicht sauberes Herunterfahren und Energieverwaltungsfunktionen.', 'Normalerweise aktiviert lassen.', ['An']),
  kvm: help('KVM', 'Hardwarebeschleunigung fuer die VM.', 'Nur deaktivieren, wenn du einen sehr speziellen Kompatibilitaetsgrund hast.', ['An fuer normale Nutzung']),
  vga: help('Display', 'Virtuelle Grafikkarte bzw. Konsolenanzeige.', 'SPICE/QXL oder virtio sind fuer grafische Desktops ueblich.', ['virtio', 'qxl', 'std']),
  audio0: help('Audio', 'Virtuelles Audiogeraet fuer Ton im Gast.', 'Fuer Gaming, Medien oder Remote-Desktop mit Audio aktivieren.', ['device=ich9-intel-hda,driver=spice']),
  keyboard: help('Keyboard', 'Tastaturlayout fuer die Konsole.', 'Setze es passend zur physischen Tastatur.', ['de', 'en-us']),
  spice_enhancements: help('SPICE Enhancements', 'Zusatzfunktionen fuer SPICE wie Zwischenablage oder bessere Anzeige.', 'Sinnvoll fuer interaktive Desktop-VMs.', ['foldersharing=1', 'videostreaming=all']),
  ciuser: help('Cloud-Init User', 'Benutzername, den Cloud-Init beim ersten Start im Gast einrichtet.', 'Nur wirksam, wenn die VM ein Cloud-Init-faehiges Image nutzt.', ['beagle', 'ubuntu']),
  sshkeys: help('SSH Keys', 'Oeffentliche SSH-Schluessel fuer Login ohne Passwort.', 'Nur Public Keys eintragen, niemals private Keys oder Passwoerter.', ['ssh-ed25519 AAAA... user@device']),
  ipconfig0: help('IP Config 0', 'Netzwerkadresse fuer die erste Cloud-Init-Netzwerkkarte.', 'dhcp ist am einfachsten. Statische Werte muessen zu deinem Netz passen.', ['ip=dhcp', 'ip=192.168.1.50/24,gw=192.168.1.1']),
  ipconfig1: help('IP Config 1', 'Netzwerkadresse fuer die zweite Cloud-Init-Netzwerkkarte.', 'Nur nutzen, wenn die VM wirklich eine zweite Netzwerkkarte hat.', ['ip=dhcp']),
  nameserver: help('Nameserver', 'DNS-Server, die der Gast fuer Namensaufloesung nutzt.', 'Falsche DNS-Werte fuehren dazu, dass Webseiten oder Paketquellen nicht gefunden werden.', ['1.1.1.1', '192.168.1.1']),
  searchdomain: help('Search Domain', 'DNS-Suchdomain fuer kurze Hostnamen.', 'In Heimnetzen oft leer. In Firmen kann hier die interne Domain stehen.', ['beagle.local', 'firma.local']),
  citype: help('Cloud-Init Type', 'Format/Variante der Cloud-Init-Daten.', 'Nur aendern, wenn das Gast-Image eine bestimmte Variante erwartet.', ['nocloud', 'configdrive2']),
  ciupgrade: help('Upgrade Packages', 'Cloud-Init aktualisiert Pakete beim ersten Start.', 'Kann den ersten Boot verlaengern, bringt die VM aber direkt auf aktuellen Stand.', ['An fuer frische Server', 'Aus fuer schnelle Tests']),
  hotplug: help('Hotplug', 'Erlaubt das Hinzufuegen oder Entfernen bestimmter Hardware im laufenden Betrieb.', 'Praktisch fuer Disks oder Netzwerke, wenn Gast und Treiber das unterstuetzen.', ['disk,network,usb', 'network']),
  watchdog: help('Watchdog', 'Virtueller Wachhund, der auf Haenger im Gast reagieren kann.', 'Nur aktivieren, wenn du weisst, welche Aktion bei Fehlern passieren soll.', ['model=i6300esb,action=reset']),
  rng0: help('RNG', 'Virtueller Zufallszahlengenerator fuer Kryptografie im Gast.', 'Sinnvoll fuer Server, VPN, SSH und Zertifikate.', ['source=/dev/urandom']),
  hookscript: help('Hookscript', 'Script, das bei VM-Lifecycle-Ereignissen ausgefuehrt wird.', 'Nur fuer Administratoren. Fehlerhafte Hooks koennen Start/Stop stoeren.', ['local:snippets/vm-hook.sh']),
  args: help('QEMU Args', 'Direkte Zusatzargumente fuer QEMU.', 'Gefaehrlich fuer Laien: Nur setzen, wenn eine Anleitung exakt diese Option verlangt.', ['-cpu host,+feature']),
  vmgenid: help('VM Generation ID', 'Eindeutige ID, die manche Betriebssysteme fuer Klone und Domänenrollen nutzen.', 'Normalerweise automatisch verwalten lassen.', ['auto', 'GUID-Wert'])
};

function help(title, summary, guidance, examples) {
  return { title, summary, guidance, examples: Array.isArray(examples) ? examples : [] };
}

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

function riskForKey(key) {
  if (/^(args|hookscript|hostpci|tpmstate|efidisk|rng|watchdog|machine|bios|scsihw|boot|bootdisk)/.test(key)) {
    return 'Hoch: falsche Werte koennen verhindern, dass die VM startet. Vorher Snapshot oder Backup pruefen.';
  }
  if (/^(memory|balloon|sockets|cores|vcpus|cpu|cpulimit|affinity|numa|net|scsi|virtio|sata|ide|usb)/.test(key)) {
    return 'Mittel: die VM bleibt meist reparierbar, kann aber langsamer werden oder Netzwerk/Storage verlieren.';
  }
  if (/^(description|tags|keyboard|ciuser|nameserver|searchdomain)/.test(key)) {
    return 'Niedrig: laesst sich in der Regel gefahrlos korrigieren.';
  }
  return 'Mittel: pruefe die Wirkung, bevor du produktive VMs aenderst.';
}

function restartHintForKey(key) {
  if (/^(name|description|tags|protection|onboot|startup)$/.test(key)) {
    return 'Wirkt meist sofort in der Verwaltung, ohne Gast-Neustart.';
  }
  if (/^(ci|ipconfig|nameserver|searchdomain|sshkeys)/.test(key)) {
    return 'Cloud-Init-Werte greifen normalerweise beim naechsten Cloud-Init-Lauf oder ersten Start des Images.';
  }
  return 'Hardwarenahe Werte brauchen oft einen Shutdown und Neustart der VM.';
}

function defaultGuideForKey(key) {
  if (DISK_KEY_PATTERN.test(key)) {
    return help(key, 'Virtuelle Festplatte oder Laufwerk der VM.', 'Aendere Storage-Werte nur, wenn du weisst, welche Disk betroffen ist. Ein falscher Wert kann Daten unzugreifbar machen.', ['local-lvm:vm-100-disk-0,size=64G', 'media=cdrom']);
  }
  if (NET_KEY_PATTERN.test(key)) {
    return help(key, 'Virtuelle Netzwerkkarte der VM.', 'Bridge, Modell und Firewall bestimmen, ob die VM ins richtige Netz kommt.', ['virtio,bridge=vmbr0,firewall=1', 'e1000,bridge=br0']);
  }
  return help(key, 'Erweiterte VM-Option aus der gespeicherten Konfiguration.', 'Diese Option ist editierbar, aber nicht als Standardfeld bekannt. Nur aendern, wenn du ihre Bedeutung kennst oder eine Anleitung dafuer hast.', ['bestehenden Wert als Vorlage nutzen']);
}

function guideForField(field) {
  const key = String(field && field.key || '').trim();
  return FIELD_HELP[key] || defaultGuideForKey(key);
}

function renderHelpButton(field) {
  const key = String(field && field.key || '').trim();
  const label = String(field && field.label || key).trim();
  return '<button type="button" class="vm-config-help-button" data-vm-config-help="' + escapeHtml(key) + '" aria-label="Hilfe zu ' + escapeHtml(label) + '" title="Hilfe zu ' + escapeHtml(label) + '">?</button>';
}

function renderFieldCaption(field) {
  const label = String(field && field.label || field.key || '').trim();
  return '<span class="vm-config-field-caption"><span>' + escapeHtml(label) + '</span>' + renderHelpButton(field) + '</span>';
}

function controlLimits(field, value) {
  const base = CONTROL_LIMITS[field.key] || {};
  const numeric = Number(value || 0);
  const min = Number(base.min != null ? base.min : (field.min != null ? field.min : 0));
  const fallbackMax = Math.max(min + 1, numeric || min + 1);
  const max = Math.max(Number(base.max != null ? base.max : fallbackMax), numeric || min);
  const step = Number(base.step != null ? base.step : 1);
  return { min, max, step, unit: String(base.unit || '') };
}

function renderNumberControl(field, config) {
  const rawValue = fieldValue(config, field.key, field.type);
  const rangeValue = rawValue === '' ? String(field.min != null ? field.min : 0) : rawValue;
  const displayValue = rawValue === '' ? 'leer' : rawValue;
  const limits = controlLimits(field, rangeValue);
  const unit = limits.unit ? '<span>' + escapeHtml(limits.unit) + '</span>' : '';
  return '' +
    '<div class="vm-control-card vm-control-card-range" data-vm-config-control="' + escapeHtml(field.key) + '">' +
    '  <div class="vm-control-head">' + renderFieldCaption(field) + '<output data-vm-config-output="' + escapeHtml(field.key) + '">' + escapeHtml(displayValue) + '</output></div>' +
    '  <input class="vm-control-range" type="range" data-vm-config-range="' + escapeHtml(field.key) + '" min="' + escapeHtml(String(limits.min)) + '" max="' + escapeHtml(String(limits.max)) + '" step="' + escapeHtml(String(limits.step)) + '" value="' + escapeHtml(rangeValue) + '">' +
    '  <div class="vm-control-foot"><span>' + escapeHtml(String(limits.min)) + '</span><label><input class="vm-control-number" type="number" data-vm-config-field="' + escapeHtml(field.key) + '" min="' + escapeHtml(String(limits.min)) + '" max="' + escapeHtml(String(limits.max)) + '" step="' + escapeHtml(String(limits.step)) + '" value="' + escapeHtml(rawValue) + '">' + unit + '</label><span>' + escapeHtml(String(limits.max)) + '</span></div>' +
    '</div>';
}

function renderToggleControl(field, config) {
  const value = fieldValue(config, field.key, field.type);
  return '' +
    '<div class="vm-control-card vm-control-card-toggle" data-vm-config-control="' + escapeHtml(field.key) + '">' +
    '  <div class="vm-control-head">' + renderFieldCaption(field) + '<span class="vm-toggle-state" data-vm-config-toggle-state="' + escapeHtml(field.key) + '">' + (value ? 'Aktiv' : 'Aus') + '</span></div>' +
    '  <label class="vm-control-switch">' +
    '    <input type="checkbox" data-vm-config-field="' + escapeHtml(field.key) + '"' + (value ? ' checked' : '') + '>' +
    '    <span><i></i></span>' +
    '  </label>' +
    '</div>';
}

function renderInput(field, config) {
  const value = fieldValue(config, field.key, field.type);
  const common = ' data-vm-config-field="' + escapeHtml(field.key) + '"';
  if (field.type === 'number') {
    return renderNumberControl(field, config);
  }
  if (field.type === 'checkbox') {
    return renderToggleControl(field, config);
  }
  if (field.type === 'textarea') {
    return '<label class="field">' + renderFieldCaption(field) + '<textarea rows="3"' + common + '>' + escapeHtml(value) + '</textarea></label>';
  }
  const min = field.min == null ? '' : ' min="' + escapeHtml(String(field.min)) + '"';
  return '<label class="field">' + renderFieldCaption(field) + '<input type="' + escapeHtml(field.type || 'text') + '"' + min + common + ' value="' + escapeHtml(value) + '"></label>';
}

function renderHardwareEditor(config) {
  const keys = hardwareKeys(config);
  let html = '<section class="detail-section"><h3>Hardware</h3>';
  if (!keys.length) {
    html += '<div class="muted">Keine Hardware-Optionen in der gespeicherten VM-Konfiguration.</div>';
  }
  keys.forEach((key) => {
    html += '<label class="field">' + renderFieldCaption({ key, label: key }) + '<input class="mono" data-vm-config-field="' + escapeHtml(key) + '" value="' + escapeHtml(normalize(config[key])) + '"></label>';
  });
  html += '</section>';
  return html;
}

function renderHelpModal() {
  return '' +
    '<div class="vm-config-help-modal" data-vm-config-help-modal hidden aria-hidden="true" role="dialog" aria-modal="true" aria-labelledby="vm-config-help-title">' +
    '  <div class="vm-config-help-backdrop" data-vm-config-help-close></div>' +
    '  <div class="vm-config-help-dialog">' +
    '    <div class="vm-config-help-head">' +
    '      <div><span class="vm-config-guide-kicker">Beagle Guide Layer</span><h3 id="vm-config-help-title" data-vm-config-help-title>Option</h3></div>' +
    '      <button type="button" class="vm-config-help-close" data-vm-config-help-close aria-label="Hilfe schliessen">x</button>' +
    '    </div>' +
    '    <div class="vm-config-help-body">' +
    '      <section><h4>Was ist das?</h4><p data-vm-config-help-summary></p></section>' +
    '      <section><h4>Wann aendern?</h4><p data-vm-config-help-guidance></p></section>' +
    '      <section><h4>Typische Werte</h4><ul data-vm-config-help-examples></ul></section>' +
    '      <section><h4>Risiko & Neustart</h4><p data-vm-config-help-risk></p><p data-vm-config-help-restart></p></section>' +
    '      <section><h4>Aktueller Wert</h4><pre data-vm-config-help-current></pre></section>' +
    '    </div>' +
    '    <div class="vm-config-help-actions"><button type="button" class="primary" data-vm-config-help-close>Verstanden</button></div>' +
    '  </div>' +
    '</div>';
}

function renderGuidePanel() {
  return '' +
    '<aside class="vm-config-guide-panel" data-vm-config-guide-panel aria-live="polite">' +
    '  <div class="vm-config-guide-panel-head"><span>Beagle Info View</span><strong data-vm-config-guide-panel-title>Feldhilfe</strong></div>' +
    '  <p data-vm-config-guide-panel-summary>Bewege den Mauszeiger ueber ein Feld oder fokussiere es mit der Tastatur. Hier erscheint sofort eine kurze, laienverstaendliche Erklaerung.</p>' +
    '  <div class="vm-config-guide-panel-meta"><span data-vm-config-guide-panel-risk>Risiko: kontextabhaengig</span><span data-vm-config-guide-panel-restart>Neustart: kontextabhaengig</span></div>' +
    '</aside>';
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
    html += renderGuidePanel();
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
        html += '<label class="field">' + renderFieldCaption({ key, label: key }) + '<input class="mono" data-vm-config-field="' + escapeHtml(key) + '" value="' + escapeHtml(normalize(this.config[key])) + '"></label>';
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
    if (!form) {
      return;
    }
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      this.save(form);
    });
    form.addEventListener('click', (event) => {
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
      if (key) {
        this.updateGuidePanel(form, key);
      }
    });
    form.addEventListener('focusin', (event) => {
      const key = this.keyFromGuideTarget(event.target);
      if (key) {
        this.updateGuidePanel(form, key);
      }
    });
    form.addEventListener('input', (event) => {
      this.syncControlSurface(form, event.target);
    });
    form.addEventListener('change', (event) => {
      this.syncControlSurface(form, event.target);
    });
    form.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        this.closeHelp(form);
      }
    });
  }

  keyFromGuideTarget(target) {
    if (!target || !target.closest) {
      return '';
    }
    const explicit = target.closest('[data-vm-config-help]');
    if (explicit) {
      return String(explicit.getAttribute('data-vm-config-help') || '').trim();
    }
    const field = target.closest('[data-vm-config-field]');
    if (field) {
      return String(field.getAttribute('data-vm-config-field') || '').trim();
    }
    return '';
  }

  syncControlSurface(form, target) {
    if (!target || !target.getAttribute) {
      return;
    }
    const rangeKey = String(target.getAttribute('data-vm-config-range') || '').trim();
    const fieldKey = String(target.getAttribute('data-vm-config-field') || '').trim();
    const key = rangeKey || fieldKey;
    if (!key) {
      return;
    }
    if (NUMBER_FIELDS.has(key)) {
      const range = form.querySelector('[data-vm-config-range="' + CSS.escape(key) + '"]');
      const number = form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]');
      const output = form.querySelector('[data-vm-config-output="' + CSS.escape(key) + '"]');
      const value = String(target.value || '').trim();
      if (range && target !== range) {
        range.value = value;
      }
      if (number && target !== number) {
        number.value = value;
      }
      if (output) {
        output.textContent = value || 'leer';
      }
    }
    if (BOOLEAN_FIELDS.has(key)) {
      const stateLabel = form.querySelector('[data-vm-config-toggle-state="' + CSS.escape(key) + '"]');
      if (stateLabel) {
        stateLabel.textContent = target.checked ? 'Aktiv' : 'Aus';
      }
    }
  }

  updateGuidePanel(form, key) {
    const panel = form.querySelector('[data-vm-config-guide-panel]');
    if (!panel || !key) {
      return;
    }
    const field = EDITOR_SECTIONS.flatMap((section) => section.fields).find((candidate) => candidate.key === key) || { key, label: key };
    const guide = guideForField(field);
    const title = panel.querySelector('[data-vm-config-guide-panel-title]');
    const summary = panel.querySelector('[data-vm-config-guide-panel-summary]');
    const risk = panel.querySelector('[data-vm-config-guide-panel-risk]');
    const restart = panel.querySelector('[data-vm-config-guide-panel-restart]');
    if (title) title.textContent = guide.title || field.label || key;
    if (summary) summary.textContent = guide.summary || '';
    if (risk) risk.textContent = riskForKey(key);
    if (restart) restart.textContent = restartHintForKey(key);
  }

  openHelp(form, key) {
    const modal = form.querySelector('[data-vm-config-help-modal]');
    if (!modal) {
      return;
    }
    const field = EDITOR_SECTIONS.flatMap((section) => section.fields).find((candidate) => candidate.key === key) || { key, label: key };
    const guide = guideForField(field);
    const control = form.querySelector('[data-vm-config-field="' + CSS.escape(key) + '"]');
    const current = control ? (control.type === 'checkbox' ? (control.checked ? 'An' : 'Aus') : String(control.value || '')) : normalize(this.config[key]);
    const examples = Array.isArray(guide.examples) && guide.examples.length ? guide.examples : ['kein Beispiel hinterlegt'];
    const title = modal.querySelector('[data-vm-config-help-title]');
    const summary = modal.querySelector('[data-vm-config-help-summary]');
    const guidance = modal.querySelector('[data-vm-config-help-guidance]');
    const exampleList = modal.querySelector('[data-vm-config-help-examples]');
    const risk = modal.querySelector('[data-vm-config-help-risk]');
    const restart = modal.querySelector('[data-vm-config-help-restart]');
    const currentBox = modal.querySelector('[data-vm-config-help-current]');
    if (title) title.textContent = guide.title || field.label || key;
    if (summary) summary.textContent = guide.summary || '';
    if (guidance) guidance.textContent = guide.guidance || '';
    if (exampleList) {
      exampleList.innerHTML = examples.map((example) => '<li><code>' + escapeHtml(example) + '</code></li>').join('');
    }
    if (risk) risk.textContent = riskForKey(key);
    if (restart) restart.textContent = restartHintForKey(key);
    if (currentBox) currentBox.textContent = current || '(leer)';
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    const close = modal.querySelector('[data-vm-config-help-close]');
    if (close && close.focus) {
      close.focus();
    }
  }

  closeHelp(form) {
    const modal = form.querySelector('[data-vm-config-help-modal]');
    if (!modal || modal.hidden) {
      return;
    }
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
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

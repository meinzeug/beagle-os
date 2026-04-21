export const browserCommon = window.BeagleBrowserCommon || null;
export const config = window.BEAGLE_WEB_UI_CONFIG || {};

export const SESSION_IDLE_TIMEOUT_MS = 20 * 60 * 1000;
export const ACTIVITY_LOG_MAX = 50;
export const FETCH_TIMEOUT_MS = 20000;
export const USAGE_WARN_THRESHOLD = 90;
export const USAGE_INFO_THRESHOLD = 70;
export const MIN_PASSWORD_LEN = 8;
export const MIN_GUEST_PASSWORD_LEN = 8;
export const MAX_USERNAME_LEN = 64;
export const USERNAME_PATTERN = /^[A-Za-z0-9._-]+$/;
export const ROLE_NAME_PATTERN = /^[A-Za-z0-9._:-]+$/;
export const POLICY_NAME_PATTERN = /^[A-Za-z0-9._:-]+$/;
export const DISK_KEY_PATTERN = /^(virtio|ide|sata|scsi|efidisk|tpmstate)\d*$/;
export const NET_KEY_PATTERN = /^net\d+$/;
export const VM_MAIN_KEYS = [
  'vmid',
  'name',
  'node',
  'status',
  'tags',
  'cores',
  'memory',
  'machine',
  'bios',
  'ostype',
  'boot',
  'agent',
  'balloon',
  'onboot',
  'cpu'
];

export const BULK_ACTION_BUTTON_IDS = [
  'bulk-healthcheck',
  'bulk-support-bundle',
  'bulk-restart-session',
  'bulk-restart-runtime',
  'bulk-update-scan',
  'bulk-update-download',
  'bulk-vm-start',
  'bulk-vm-stop',
  'bulk-vm-reboot'
];

export const panelMeta = {
  overview: {
    eyebrow: 'Beagle Console',
    title: 'Dashboard',
    description: 'Live Status, Aktivitaet und Infrastruktur-Telemetrie auf einen Blick.'
  },
  inventory: {
    eyebrow: 'Compute',
    title: 'VMs & Endpoints',
    description: 'Aktive Beagle-VMs verwalten: Filter, Bulk Actions und Detailansicht.'
  },
  virtualization: {
    eyebrow: 'Compute',
    title: 'Nodes',
    description: 'Provider-neutrale Sicht auf Compute, Persistenz und Netz-Bridges.'
  },
  provisioning: {
    eyebrow: 'Compute',
    title: 'VM erstellen',
    description: 'Provider-neutrale Provisioning-Contracts mit Verlauf der letzten Requests.'
  },
  policies: {
    eyebrow: 'Pools & Sessions',
    title: 'Pools & Policies',
    description: 'Desktop-Pools, Zuweisungen, Profile und Prioritaeten fuer die Beagle-Flotte verwalten.'
  },
  iam: {
    eyebrow: 'Identity',
    title: 'Users & Roles',
    description: 'Konsolen-Anmeldung, RBAC und Sessions zentral steuern.'
  },
  settings_general: {
    eyebrow: 'Platform',
    title: 'Allgemein',
    description: 'Servername, Hostname, Zeitzone und oeffentliche URL konfigurieren.'
  },
  settings_security: {
    eyebrow: 'Platform',
    title: 'Sicherheit & TLS',
    description: 'TLS-Zertifikate, Passwort-Richtlinien und Session-Konfiguration.'
  },
  settings_firewall: {
    eyebrow: 'Network',
    title: 'Firewall',
    description: 'UFW-Firewall-Regeln verwalten und Ports freigeben.'
  },
  settings_network: {
    eyebrow: 'Network',
    title: 'Interfaces & DNS',
    description: 'Netzwerkschnittstellen, DNS-Server und Gateway-Konfiguration.'
  },
  settings_services: {
    eyebrow: 'Operations',
    title: 'Dienste',
    description: 'Beagle-Systemdienste ueberwachen und neu starten.'
  },
  settings_updates: {
    eyebrow: 'Operations',
    title: 'System-Updates',
    description: 'Verfuegbare Paket-Updates pruefen und installieren.'
  },
  settings_backup: {
    eyebrow: 'Operations',
    title: 'Backup & Recovery',
    description: 'Automatische Sicherung der Beagle-Konfiguration verwalten.'
  },
  settings_webhooks: {
    eyebrow: 'Operations',
    title: 'Webhooks',
    description: 'Externe Integrationen via Events und HMAC-signierten HTTP-POSTs anbinden.'
  },
  sessions: {
    eyebrow: 'Beagle OS 7.0',
    title: 'Sessions',
    description: 'Aktive Streaming-Sessions mit Live-Telemetrie und Endpoint-Zuordnung.'
  }
};

export const state = {
  token: '',
  refreshToken: '',
  user: null,
  onboarding: {
    pending: false,
    completed: false
  },
  inventory: [],
  endpointReports: [],
  policies: [],
  authUsers: [],
  authRoles: [],
  selectedAuthUser: '',
  selectedAuthRole: '',
  virtualizationOverview: null,
  virtualizationNodeFilter: '',
  virtualizationInspector: {
    vmid: null,
    loading: false,
    config: null,
    interfaces: [],
    error: ''
  },
  provisioningCatalog: null,
  selectedVmid: null,
  selectedVmids: [],
  selectedPolicyName: '',
  activeDetailPanel: 'summary',
  activePanel: 'overview',
  detailCache: Object.create(null),
  autoRefresh: true,
  authFailCount: 0,
  authLockUntil: 0
};

export function resetVirtualizationInspector() {
  state.virtualizationInspector = {
    vmid: null,
    loading: false,
    config: null,
    interfaces: [],
    error: ''
  };
}
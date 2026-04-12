(function () {
  'use strict';

  var browserCommon = window.BeagleBrowserCommon;
  var config = window.BEAGLE_WEB_UI_CONFIG || {};
  var tokenStore = null;

  if (!browserCommon) {
    throw new Error('BeagleBrowserCommon must be loaded before website/app.js');
  }
  tokenStore = browserCommon.createSessionTokenStore('beagle.webUi.apiToken');

  function readStoredToken() {
    return tokenStore.read();
  }

  function writeStoredToken(token) {
    tokenStore.write(token);
  }

  function clearStoredToken() {
    tokenStore.clear();
  }

  var state = {
    token: readStoredToken(),
    inventory: [],
    policies: [],
    virtualizationOverview: null,
    selectedVmid: null,
    selectedVmids: [],
    selectedPolicyName: '',
    activeDetailPanel: 'summary',
    activePanel: 'overview',
    detailCache: Object.create(null)
  };

  var USAGE_WARN_THRESHOLD = 90;
  var USAGE_INFO_THRESHOLD = 70;
  var DISK_KEY_PATTERN = /^(virtio|ide|sata|scsi|efidisk|tpmstate)\d*$/;
  var NET_KEY_PATTERN = /^net\d+$/;
  var VM_MAIN_KEYS = ['vmid', 'name', 'node', 'status', 'tags', 'cores', 'memory', 'machine', 'bios', 'ostype', 'boot', 'agent', 'balloon', 'onboot', 'cpu'];

  var panelMeta = {    overview: {
      eyebrow: 'Host Control Surface',
      title: 'Beagle OS Web UI',
      description: 'Zentrale Bedienoberflaeche fuer aktive Beagle-VMs, Endpoint-Zustand, Installer-Bereitschaft, Credentials und Operator-Aktionen.'
    },
    inventory: {
      eyebrow: 'Inventory Workspace',
      title: 'Beagle Inventar',
      description: 'Arbeite direkt mit den aktiven Beagle-VMs, Filterung, Bulk-Aktionen und Detailansicht.'
    },
    virtualization: {
      eyebrow: 'Infrastructure Workspace',
      title: 'Virtualisierung',
      description: 'Nodes, Storage und Infrastruktur-Inventar des Beagle-Hosts.'
    },
    policies: {
      eyebrow: 'Configuration Workspace',
      title: 'Beagle Policies',
      description: 'Verwalte Zuweisungen, Profile und Prioritaeten fuer deine Endpoint- und Desktop-Flotte.'
    }
  };

  function qs(id) {
    return document.getElementById(id);
  }

  function text(id, value) {
    var node = qs(id);
    if (node) {
      node.textContent = value;
    }
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function apiBase() {
    return String(config.apiBase || '/beagle-api/api/v1').replace(/\/$/, '');
  }

  function downloadsBase() {
    return String(config.downloadsBase || '/beagle-downloads').replace(/\/$/, '');
  }

  function webUiUrl() {
    return String(config.webUiUrl || window.location.origin);
  }

  function applyTitle() {
    var title = String(config.title || 'Beagle OS Web UI');
    document.title = title;
    var heading = document.querySelector('.app-header h1');
    if (heading) {
      heading.textContent = title;
    }
  }

  function consumeTokenFromLocation() {
    var hash = String(window.location.hash || '').replace(/^#/, '');
    if (!hash) {
      return;
    }
    var tokenMatch = hash.match(/(?:^|&)beagle_token=([^&]+)/);
    if (!tokenMatch) {
      return;
    }
    var params = new URLSearchParams(hash);
    var token = String(params.get('beagle_token') || '').trim();
    if (!token) {
      return;
    }
    state.token = token;
    writeStoredToken(token);
    if (qs('api-token')) {
      qs('api-token').value = token;
    }
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    } else {
      window.location.hash = '';
    }
  }

  function parseAppHash() {
    var raw = String(window.location.hash || '').replace(/^#/, '');
    if (!raw) {
      return {};
    }
    if (raw.indexOf('beagle_token=') !== -1) {
      return {};
    }
    var params = new URLSearchParams(raw);
    return {
      panel: String(params.get('panel') || '').trim(),
      vmid: String(params.get('vmid') || '').trim(),
      detail: String(params.get('detail') || '').trim()
    };
  }

  function syncHash() {
    var params = new URLSearchParams();
    if (state.activePanel && state.activePanel !== 'overview') {
      params.set('panel', state.activePanel);
    }
    if (state.activePanel === 'inventory' && state.selectedVmid) {
      params.set('vmid', String(state.selectedVmid));
    }
    if (state.activePanel === 'inventory' && state.activeDetailPanel && state.activeDetailPanel !== 'summary') {
      params.set('detail', state.activeDetailPanel);
    }
    var next = params.toString();
    var current = String(window.location.hash || '').replace(/^#/, '');
    if (current !== next) {
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search + (next ? '#' + next : ''));
      } else {
        window.location.hash = next;
      }
    }
  }

  function setAuthMode(connected) {
    document.body.classList.toggle('auth-only', !connected);
    if (connected) {
      document.body.classList.remove('auth-modal-open');
    } else {
      document.body.classList.add('auth-modal-open');
    }
    updateSessionChrome();
  }

  function setBanner(message, tone) {
    var node = qs('auth-status');
    if (!node) {
      return;
    }
    node.className = 'banner ' + (tone || 'info');
    node.textContent = message;
  }

  function updateSessionChrome() {
    var chip = qs('session-chip');
    if (chip) {
      chip.textContent = state.token ? 'Verbunden' : 'Nicht verbunden';
    }
  }

  function setActivePanel(panelName) {
    var next = panelMeta[panelName] ? panelName : 'overview';
    state.activePanel = next;
    document.querySelectorAll('[data-panel]').forEach(function (node) {
      node.classList.toggle('nav-item-active', node.getAttribute('data-panel') === next);
    });
    document.querySelectorAll('[data-panel-section]').forEach(function (node) {
      var sectionPanel = node.getAttribute('data-panel-section');
      var visible = sectionPanel === 'overview' ? next === 'overview' : sectionPanel === next;
      node.classList.toggle('panel-section-active', visible);
    });
    var meta = panelMeta[next] || panelMeta.overview;
    text('panel-eyebrow', meta.eyebrow);
    text('panel-title', meta.title);
    text('panel-description', meta.description);
    syncHash();
  }

  function setActiveDetailPanel(panelName) {
    var next = panelName || 'summary';
    state.activeDetailPanel = next;
    document.querySelectorAll('[data-detail-panel]').forEach(function(node) {
      node.classList.toggle('detail-tab-active', node.getAttribute('data-detail-panel') === next);
    });
    document.querySelectorAll('.detail-panel').forEach(function(node) {
      node.classList.toggle('detail-panel-active', node.getAttribute('data-detail-panel') === next);
    });
    syncHash();
  }

  function openAuthModal() {
    document.body.classList.add('auth-modal-open');
    var field = qs('api-token');
    if (field) {
      window.setTimeout(function () {
        field.focus();
        field.select();
      }, 30);
    }
  }

  function closeAuthModal() {
    if (!document.body.classList.contains('auth-only')) {
      document.body.classList.remove('auth-modal-open');
    }
  }

  function accountShell() {
    var toggle = qs('avatar-toggle');
    return toggle ? toggle.closest('.account-shell') : null;
  }

  function closeAccountMenu() {
    var shell = accountShell();
    if (shell) {
      shell.classList.remove('menu-open');
    }
  }

  function request(path, options) {
    var target = path.indexOf('http') === 0 ? path : apiBase() + path;
    var finalOptions = Object.assign({ method: 'GET', credentials: 'same-origin' }, options || {});
    finalOptions.headers = Object.assign({}, finalOptions.headers || {});
    if (state.token) {
      finalOptions.headers['X-Beagle-Api-Token'] = state.token;
    }
    return fetch(target, finalOptions).then(function (response) {
      if (!response.ok) {
        return response.text().then(function (body) {
          var detail = body;
          try {
            var parsed = JSON.parse(body);
            detail = parsed.error || parsed.message || body;
          } catch (error) {
            void error;
          }
          throw new Error('HTTP ' + response.status + ': ' + detail);
        });
      }
      return response.json();
    });
  }

  function blobRequest(path, filename) {
    var target = path.indexOf('http') === 0 ? path : apiBase() + path;
    return fetch(target, {
      method: 'GET',
      credentials: 'same-origin',
      headers: state.token ? { 'X-Beagle-Api-Token': state.token } : {}
    }).then(function (response) {
      if (!response.ok) {
        throw new Error('HTTP ' + response.status + ' downloading');
      }
      return response.blob().then(function (blob) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        window.setTimeout(function () {
          URL.revokeObjectURL(url);
          link.remove();
        }, 1000);
      });
    });
  }

  function formatDate(value) {
    if (!value) {
      return 'n/a';
    }
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return String(value);
    }
    return date.toLocaleString('en-GB', { dateStyle: 'short', timeStyle: 'short' });
  }

  function profileOf(vm) {
    return vm && vm.profile ? vm.profile : vm || {};
  }

  function roleOf(vm) {
    var profile = profileOf(vm);
    return String(profile.beagle_role || profile.role || '').trim().toLowerCase();
  }

  function isBeagleVm(vm) {
    var profile = profileOf(vm);
    return Boolean(
      profile.beagle_role ||
      profile.stream_host ||
      profile.installer_target_eligible ||
      (vm && vm.endpoint && vm.endpoint.reported_at)
    );
  }

  function isEligible(vm) {
    var profile = profileOf(vm);
    return Boolean(profile.installer_target_eligible);
  }

  function matchesRoleFilter(vm, value) {
    var role = roleOf(vm);
    if (value === 'all') {
      return true;
    }
    if (value === 'endpoint') {
      return role === 'endpoint' || role === 'thinclient' || role === 'client';
    }
    if (value === 'desktop') {
      return role === 'desktop';
    }
    return role !== 'desktop' && role !== 'endpoint' && role !== 'thinclient' && role !== 'client';
  }

  function filteredInventory() {
    var query = String(qs('search-input') ? qs('search-input').value : '').trim().toLowerCase();
    var roleFilter = String(qs('role-filter') ? qs('role-filter').value : 'all');
    var eligibleOnly = Boolean(qs('eligible-only') && qs('eligible-only').checked);
    return state.inventory.filter(function (vm) {
      var profile = profileOf(vm);
      if (!isBeagleVm(vm)) {
        return false;
      }
      if (!matchesRoleFilter(vm, roleFilter)) {
        return false;
      }
      if (eligibleOnly && !isEligible(vm)) {
        return false;
      }
      if (!query) {
        return true;
      }
      var haystack = [
        profile.name,
        profile.identity_hostname,
        profile.stream_host,
        profile.node,
        profile.vmid,
        profile.beagle_role,
        profile.assignment_source,
        profile.moonlight_app
      ].join(' ').toLowerCase();
      return haystack.indexOf(query) !== -1;
    }).sort(function (left, right) {
      var leftProfile = profileOf(left);
      var rightProfile = profileOf(right);
      var leftRunning = leftProfile.status === 'running' ? 0 : 1;
      var rightRunning = rightProfile.status === 'running' ? 0 : 1;
      if (leftRunning !== rightRunning) {
        return leftRunning - rightRunning;
      }
      return String(leftProfile.name || leftProfile.vmid).localeCompare(String(rightProfile.name || rightProfile.vmid), 'de');
    });
  }

  function chip(label, tone) {
    return '<span class="chip ' + tone + '">' + escapeHtml(label) + '</span>';
  }

  function formatBytes(bytes) {
    if (!bytes) {
      return '0 B';
    }
    var units = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = 0;
    var value = Number(bytes);
    while (value >= 1024 && i < units.length - 1) {
      value = value / 1024;
      i++;
    }
    return value.toFixed(1) + '\u00a0' + units[i];
  }

  function usageBar(used, total, label) {
    var pct = total > 0 ? Math.min(100, Math.round((Number(used) / Number(total)) * 100)) : 0;
    var tone = pct >= USAGE_WARN_THRESHOLD ? 'warn' : pct >= USAGE_INFO_THRESHOLD ? 'info' : '';
    return '<span class="usage-bar-outer ' + tone + '">' +
      '<span class="usage-bar-track"><span class="usage-bar-fill" style="width:' + pct + '%"></span></span>' +
      '<span class="usage-label">' + escapeHtml(label || (pct + '%')) + '</span>' +
      '</span>';
  }

  function renderVirtualizationPanel() {
    var overview = state.virtualizationOverview;
    var nodesGrid = qs('nodes-grid');
    var storageBody = qs('storage-body');
    if (!nodesGrid || !storageBody) {
      return;
    }
    if (!overview || !state.token) {
      nodesGrid.innerHTML = '<div class="empty-card">Keine Daten. Verbinde dich zuerst mit dem API-Token.</div>';
      storageBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Keine Daten verfuegbar.</td></tr>';
      return;
    }
    var nodes = Array.isArray(overview.nodes) ? overview.nodes : [];
    var storage = Array.isArray(overview.storage) ? overview.storage : [];
    if (!nodes.length) {
      nodesGrid.innerHTML = '<div class="empty-card">Keine Nodes gefunden.</div>';
    } else {
      nodesGrid.innerHTML = nodes.map(function (node) {
        var statusTone = node.status === 'online' ? 'ok' : 'warn';
        var cpuUsed = node.maxcpu > 0 ? Math.round((node.cpu || 0) * 100) : 0;
        return '<article class="node-card">' +
          '<div class="node-head">' +
            '<strong class="node-name">' + escapeHtml(node.name || node.id || 'node') + '</strong>' +
            '<span class="chip ' + statusTone + '">' + escapeHtml(node.status || 'unknown') + '</span>' +
          '</div>' +
          '<div class="node-meta"><span class="usage-key">CPU</span>' + usageBar(cpuUsed, 100, cpuUsed + '%') + '</div>' +
          '<div class="node-meta"><span class="usage-key">RAM</span>' + usageBar(node.mem, node.maxmem, formatBytes(node.mem) + ' / ' + formatBytes(node.maxmem)) + '</div>' +
          '<div class="node-footer">' +
            '<span>' + String(node.maxcpu || 0) + '\u00a0vCPU</span>' +
            '<span>' + escapeHtml(node.provider || (overview && overview.provider) || '') + '</span>' +
          '</div>' +
        '</article>';
      }).join('');
    }
    if (!storage.length) {
      storageBody.innerHTML = '<tr><td colspan="6" class="empty-cell">Kein Storage gefunden.</td></tr>';
    } else {
      storageBody.innerHTML = storage.map(function (item) {
        return '<tr>' +
          '<td><strong>' + escapeHtml(item.name || item.id || '') + '</strong></td>' +
          '<td>' + escapeHtml(item.node || '') + '</td>' +
          '<td>' + chip(item.type || 'n/a', 'muted') + '</td>' +
          '<td class="storage-content">' + escapeHtml(item.content || '') + '</td>' +
          '<td class="storage-usage">' + usageBar(item.used, item.total, formatBytes(item.used) + ' / ' + formatBytes(item.total)) + '</td>' +
          '<td>' + formatBytes(item.avail) + '</td>' +
        '</tr>';
      }).join('');
    }
  }

  function renderVmConfigPanel(config, interfaces) {
    var diskKeys = Object.keys(config).filter(function (k) { return DISK_KEY_PATTERN.test(k); }).sort();
    var netKeys = Object.keys(config).filter(function (k) { return NET_KEY_PATTERN.test(k); }).sort();
    var html = '<section class="detail-section"><h3>VM Konfiguration</h3>';
    VM_MAIN_KEYS.forEach(function (k) {
      if (config[k] != null && config[k] !== '') {
        html += fieldBlock(k, String(config[k]));
      }
    });
    html += '</section>';
    if (diskKeys.length) {
      html += '<section class="detail-section"><h3>Disks</h3>';
      diskKeys.forEach(function (k) {
        html += fieldBlock(k, String(config[k] || ''), 'mono');
      });
      html += '</section>';
    }
    if (netKeys.length) {
      html += '<section class="detail-section"><h3>Netzwerk (Config)</h3>';
      netKeys.forEach(function (k) {
        html += fieldBlock(k, String(config[k] || ''), 'mono');
      });
      html += '</section>';
    }
    if (Array.isArray(interfaces) && interfaces.length) {
      html += '<section class="detail-section"><h3>Netzwerk Interfaces (Guest Agent)</h3>';
      interfaces.forEach(function (iface) {
        var addrs = (iface['ip-addresses'] || []).map(function (a) {
          return String(a['ip-address'] || '') + (a['prefix'] ? '/' + a['prefix'] : '');
        }).join(', ');
        html += fieldBlock(String(iface.name || ''), addrs || 'n/a');
      });
      html += '</section>';
    }
    return html;
  }

  function loadVmConfig(vmid) {
    var stack = qs('detail-stack');
    if (!stack) {
      return;
    }
    var configPanel = stack.querySelector('[data-detail-panel="config"]');
    if (!configPanel) {
      return;
    }
    if (configPanel.getAttribute('data-loaded') === String(vmid)) {
      return;
    }
    configPanel.innerHTML = '<div class="banner banner-info">Lade VM-Konfiguration...</div>';
    Promise.all([
      request('/virtualization/vms/' + vmid + '/config'),
      request('/virtualization/vms/' + vmid + '/interfaces').catch(function () { return null; })
    ]).then(function (results) {
      var config = (results[0] && results[0].config) || {};
      var interfaces = (results[1] && results[1].interfaces) || [];
      configPanel.setAttribute('data-loaded', String(vmid));
      configPanel.innerHTML = renderVmConfigPanel(config, interfaces);
    }).catch(function (error) {
      configPanel.innerHTML = '<div class="banner warn">Fehler: ' + escapeHtml(error.message) + '</div>';
    });
  }

  function renderInventory() {
    var rows = filteredInventory();
    var body = qs('inventory-body');
    if (!body) {
      return;
    }
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="7" class="empty-cell">No matching Beagle VMs found.</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (vm) {
      var profile = profileOf(vm);
      var statusTone = profile.status === 'running' ? 'ok' : 'warn';
      var installerTone = profile.installer_target_eligible ? 'ok' : 'muted';
      var lastAction = vm.last_action && vm.last_action.action ? vm.last_action.action + (vm.last_action.ok ? ' ok' : ' fail') : 'n/a';
      return '' +
        '<tr class="vm-row' + (state.selectedVmid === profile.vmid ? ' selected' : '') + '" data-vmid="' + escapeHtml(profile.vmid) + '">' +
        '  <td><input class="row-select" type="checkbox" data-select-vmid="' + escapeHtml(profile.vmid) + '"' + (state.selectedVmids.indexOf(profile.vmid) !== -1 ? ' checked' : '') + '></td>' +
        '  <td><span class="vm-name">' + escapeHtml(profile.name || ('VM ' + profile.vmid)) + '</span><div class="vm-sub">#' + escapeHtml(profile.vmid) + ' · ' + escapeHtml(profile.node || '') + '</div></td>' +
        '  <td>' + chip(roleOf(vm) || 'unassigned', roleOf(vm) === 'desktop' ? 'info' : 'muted') + '</td>' +
        '  <td>' + chip(profile.status || 'unknown', statusTone) + '</td>' +
        '  <td><div>' + escapeHtml(profile.stream_host || 'n/a') + '</div><div class="vm-sub">' + escapeHtml(profile.moonlight_port || '') + '</div></td>' +
        '  <td>' + chip(profile.installer_target_status || (profile.installer_target_eligible ? 'ready' : 'not eligible'), installerTone) + '</td>' +
        '  <td>' + escapeHtml(lastAction) + '</td>' +
        '</tr>';
    }).join('');
    if (qs('inventory-select-all')) {
      qs('inventory-select-all').checked = rows.length > 0 && rows.every(function (vm) {
        return state.selectedVmids.indexOf(profileOf(vm).vmid) !== -1;
      });
    }
  }

  function statCardFromHealth(payload, overview) {
    var counts = (payload && payload.endpoint_status_counts) || {};
    var provider = String((overview && overview.provider) || payload && payload.provider || '').trim();
    var nodeCount = Number(overview && overview.node_count || 0);
    var storageCount = Number(overview && overview.storage_count || 0);
    var managerMeta = 'v' + String(payload.version || 'unknown');
    if (provider) {
      managerMeta += ' · ' + provider;
    }
    if (nodeCount > 0 || storageCount > 0) {
      managerMeta += ' · ' + String(nodeCount) + ' nodes · ' + String(storageCount) + ' storage';
    }
    text('stat-manager', 'Online');
    text('stat-manager-meta', managerMeta);
    text('stat-vms', String(payload.vm_count || state.inventory.length || 0));
    text('stat-vms-meta', 'Active Beagle VMs: ' + String(filteredInventory().length));
    text('stat-endpoints', String(payload.endpoint_count || 0));
    text('stat-endpoints-meta', 'healthy ' + String(counts.healthy || 0) + ' · stale ' + String(counts.stale || 0) + ' · offline ' + String(counts.offline || 0));
    text('stat-policies', String(payload.policy_count || 0));
    text('stat-policies-meta', 'queued actions ' + String(payload.pending_action_count || 0));
    text('stat-nodes', String(nodeCount));
    var nodes = Array.isArray(overview && overview.nodes) ? overview.nodes : [];
    var onlineNodes = nodes.filter(function (n) { return n.status === 'online'; }).length;
    text('stat-nodes-meta', nodeCount > 0 ? 'online ' + String(onlineNodes) + ' / ' + String(nodeCount) : 'Keine Daten');
    text('stat-storage', String(storageCount));
    var storageItems = Array.isArray(overview && overview.storage) ? overview.storage : [];
    var activeStorage = storageItems.filter(function (s) { return s.active; }).length;
    text('stat-storage-meta', storageCount > 0 ? 'active ' + String(activeStorage) + ' / ' + String(storageCount) : 'Keine Daten');
  }

  function fieldBlock(label, value, tone) {
    return '<div class="kv ' + (tone || '') + '"><div class="kv-label">' + escapeHtml(label) + '</div><div class="kv-value">' + escapeHtml(value || 'n/a') + '</div></div>';
  }

  function actionButton(action, label, tone) {
    return '<button type="button" class="btn btn-' + (tone || 'ghost') + '" data-action="' + escapeHtml(action) + '">' + escapeHtml(label) + '</button>';
  }

  function renderPolicies() {
    var node = qs('policies-list');
    if (!node) {
      return;
    }
    if (!state.policies.length) {
      node.innerHTML = '<div class="empty-card">No policies found.</div>';
      return;
    }
    node.innerHTML = state.policies.map(function (policy) {
      var selector = policy.selector || {};
      var profile = policy.profile || {};
      return '' +
        '<article class="policy-card' + (state.selectedPolicyName === policy.name ? ' active' : '') + '" data-policy-name="' + escapeHtml(policy.name || '') + '">' +
        '  <div class="policy-head"><strong>' + escapeHtml(policy.name || 'policy') + '</strong>' + chip('prio ' + String(policy.priority || 0), 'muted') + '</div>' +
        '  <div class="policy-grid">' +
        fieldBlock('Selector', JSON.stringify(selector), 'mono') +
        fieldBlock('Profile', JSON.stringify(profile), 'mono') +
        '  </div>' +
        '</article>';
    }).join('');
  }

  function resetPolicyEditor() {
    state.selectedPolicyName = '';
    if (qs('policy-name')) {
      qs('policy-name').value = '';
    }
    if (qs('policy-priority')) {
      qs('policy-priority').value = '100';
    }
    if (qs('policy-enabled')) {
      qs('policy-enabled').checked = true;
    }
    if (qs('policy-selector')) {
      qs('policy-selector').value = '{\n  "vmid": 100\n}';
    }
    if (qs('policy-profile')) {
      qs('policy-profile').value = '{\n  "assigned_target": {\n    "vmid": 100\n  },\n  "beagle_role": "endpoint"\n}';
    }
    renderPolicies();
  }

  function loadPolicyIntoEditor(name) {
    var policy = state.policies.find(function (item) {
      return item.name === name;
    });
    if (!policy) {
      return;
    }
    state.selectedPolicyName = policy.name || '';
    if (qs('policy-name')) {
      qs('policy-name').value = policy.name || '';
    }
    if (qs('policy-priority')) {
      qs('policy-priority').value = String(policy.priority == null ? 100 : policy.priority);
    }
    if (qs('policy-enabled')) {
      qs('policy-enabled').checked = policy.enabled !== false;
    }
    if (qs('policy-selector')) {
      qs('policy-selector').value = JSON.stringify(policy.selector || {}, null, 2);
    }
    if (qs('policy-profile')) {
      qs('policy-profile').value = JSON.stringify(policy.profile || {}, null, 2);
    }
    renderPolicies();
  }

  function renderDetail(detail) {
    var profile = detail.profile || {};
    var credentials = detail.credentials || {};
    var installerPrep = detail.installerPrep || {};
    var actions = detail.actions || {};
    var bundles = detail.supportBundles || [];
    var endpoint = detail.state && detail.state.endpoint ? detail.state.endpoint : {};
    var usb = detail.state && detail.state.usb ? detail.state.usb : {};
    var lastAction = detail.state && detail.state.last_action ? detail.state.last_action : {};
    var node = qs('detail-stack');
    var actionsNode = qs('detail-actions');
    var usbDevices = Array.isArray(usb.devices) ? usb.devices : [];
    var attachedDevices = Array.isArray(usb.attached) ? usb.attached : [];
    var usbDevicesHtml = usbDevices.length ? usbDevices.map(function (device) {
      var busid = String(device.busid || '');
      return '<div class="bundle-row">' +
        '<strong>' + escapeHtml(busid) + '</strong><span>' + escapeHtml(device.description || '') + '</span>' +
        '<div class="btn-row">' +
        '<button class="btn btn-ghost" type="button" data-action="usb-attach" data-usb-busid="' + escapeHtml(busid) + '">Attach</button>' +
        (device.bound ? '<span class="chip ok">exported</span>' : '<span class="chip muted">local</span>') +
        '</div>' +
      '</div>';
    }).join('') : '<div class="empty-card">No exportable USB devices reported.</div>';
    var attachedDevicesHtml = attachedDevices.length ? attachedDevices.map(function (item) {
      var port = String(item.port || '');
      var busid = String(item.busid || '');
      return '<div class="bundle-row">' +
        '<strong>Port ' + escapeHtml(port) + '</strong><span>' + escapeHtml(busid || item.device || '') + '</span>' +
        '<div class="btn-row">' +
        '<button class="btn btn-ghost" type="button" data-action="usb-detach" data-usb-port="' + escapeHtml(port) + '" data-usb-busid="' + escapeHtml(busid) + '">Detach</button>' +
        '</div>' +
      '</div>';
    }).join('') : '<div class="empty-card">No USB devices attached to VM.</div>';
    text('detail-title', (profile.name || ('VM ' + profile.vmid)) + ' (#' + profile.vmid + ')');
    if (actionsNode) {
      actionsNode.innerHTML = actionButton('refresh-detail', 'Reload', 'ghost') + actionButton('sunshine-ui', 'Sunshine Web UI', 'ghost') + actionButton('usb-refresh', 'USB Refresh', 'ghost');
    }
    if (!node) {
      return;
    }
    node.innerHTML = '' +
      '<div class="banner ' + (installerPrep.status === 'ready' ? 'ok' : installerPrep.status === 'failed' || installerPrep.status === 'error' ? 'warn' : 'info') + '">Installer Readiness: ' + escapeHtml(installerPrep.target_status || installerPrep.status || 'unknown') + ' · ' + escapeHtml(installerPrep.message || 'No detail message') + '</div>' +
      '<div class="detail-panel detail-panel-active" data-detail-panel="summary">' +
      '<div class="detail-grid">' +
      '  <section class="detail-section"><h3>Profil</h3>' +
           fieldBlock('Role', profile.beagle_role) +
           fieldBlock('Status', profile.status) +
           fieldBlock('Hostname', profile.identity_hostname) +
           fieldBlock('Assignment', profile.assignment_source || 'n/a') +
           fieldBlock('Policy', profile.applied_policy && profile.applied_policy.name ? profile.applied_policy.name : 'none') +
      '  </section>' +
      '  <section class="detail-section"><h3>Streaming</h3>' +
           fieldBlock('Stream Host', profile.stream_host) +
           fieldBlock('Moonlight Port', profile.moonlight_port) +
           fieldBlock('App', profile.moonlight_app) +
           fieldBlock('Sunshine API', profile.sunshine_api_url, 'mono') +
           fieldBlock('Installer Linux', profile.installer_url, 'mono') +
           fieldBlock('Installer Windows', profile.installer_windows_url, 'mono') +
      '  </section>' +
      '  <section class="detail-section"><h3>Endpoint</h3>' +
           fieldBlock('Reported', endpoint.reported_at ? formatDate(endpoint.reported_at) : 'n/a') +
           fieldBlock('Endpoint Host', endpoint.hostname || endpoint.endpoint_id || 'n/a') +
           fieldBlock('Last Action', lastAction.action || 'n/a') +
           fieldBlock('Last Result', lastAction.message || (lastAction.ok == null ? 'n/a' : String(lastAction.ok))) +
           fieldBlock('Pending Actions', String((actions.pending_actions || []).length)) +
           fieldBlock('Support Bundles', String(bundles.length)) +
      '  </section>' +
      '</div>' +
      '<section class="detail-card action-card"><h3>Actions</h3><div class="btn-row">' +
           actionButton('installer-prep', 'Prepare Installer', 'primary') +
           actionButton('download-linux', 'Linux Installer', 'ghost') +
           actionButton('download-windows', 'Windows Installer', 'ghost') +
           actionButton('usb-refresh', 'USB Refresh', 'ghost') +
           actionButton('healthcheck', 'Healthcheck', 'ghost') +
           actionButton('support-bundle', 'Support Bundle', 'ghost') +
           actionButton('restart-session', 'Restart Session', 'ghost') +
           actionButton('restart-runtime', 'Restart Runtime', 'ghost') +
      '</div></section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="usb">' +
      '  <section class="detail-section"><h3>USB</h3>' +
           fieldBlock('Tunnel', usb.tunnel_state || 'n/a') +
           fieldBlock('Tunnel Host', usb.tunnel_host || 'n/a') +
           fieldBlock('Tunnel Port', String(usb.tunnel_port || '')) +
           fieldBlock('Exportable Devices', String(usb.device_count || 0)) +
           fieldBlock('Guest Attachments', String(usb.attached_count || 0)) +
      '  </section>' +
      '<section class="detail-section"><h3>USB Devices from Endpoint</h3><div class="bundle-list">' + usbDevicesHtml + '</div></section>' +
      '<section class="detail-section"><h3>USB Devices in VM</h3><div class="bundle-list">' + attachedDevicesHtml + '</div></section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="credentials">' +
      '  <section class="detail-section"><h3>Credentials</h3>' +
           fieldBlock('Thin Client User', credentials.thinclient_username) +
           fieldBlock('Thin Client Password', credentials.thinclient_password) +
           fieldBlock('Sunshine User', credentials.sunshine_username) +
           fieldBlock('Sunshine Password', credentials.sunshine_password) +
           fieldBlock('Sunshine PIN', credentials.sunshine_pin) +
      '  </section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="bundles">' +
      '<section class="detail-section"><h3>Support Bundles</h3><div class="bundle-list">' +
        (bundles.length ? bundles.map(function (bundle) {
          return '<div class="bundle-row"><strong>' + escapeHtml(bundle.stored_filename || bundle.bundle_id || 'bundle') + '</strong><span>' + escapeHtml(formatDate(bundle.generated_at || bundle.stored_at)) + '</span></div>';
        }).join('') : '<div class="empty-card">No bundles available.</div>') +
      '</div></section>' +
      '</div>' +
      '<div class="detail-panel" data-detail-panel="config">' +
      '<div class="banner banner-info">Klicke auf "Config" um die VM-Konfiguration zu laden.</div>' +
      '</div>';
    setActiveDetailPanel(state.activeDetailPanel);
  }

  function loadDetail(vmid) {
    var numericVmid = Number(vmid);
    state.selectedVmid = numericVmid;
    setActivePanel('inventory');
    renderInventory();
    setBanner('Loading details for VM' + numericVmid + ' ...', 'info');
    return Promise.all([
      request('/vms/' + numericVmid),
      request('/vms/' + numericVmid + '/state'),
      request('/vms/' + numericVmid + '/credentials'),
      request('/vms/' + numericVmid + '/actions'),
      request('/vms/' + numericVmid + '/installer-prep'),
      request('/vms/' + numericVmid + '/support-bundles'),
      request('/vms/' + numericVmid + '/usb')
    ]).then(function (results) {
      var detail = {
        profile: results[0].profile || {},
        state: results[1] || {},
        credentials: results[2].credentials || {},
        actions: results[3] || {},
        installerPrep: results[4].installer_prep || {},
        supportBundles: results[5].support_bundles || []
      };
      if (!detail.state.usb && results[6] && results[6].usb) {
        detail.state.usb = results[6].usb;
      }
      state.detailCache[numericVmid] = detail;
      renderDetail(detail);
      setBanner('Details for VM' + numericVmid + ' loaded.', 'ok');
      return detail;
    }).catch(function (error) {
      setBanner('Failed to load VM details:' + error.message, 'warn');
    });
  }

  function saveToken() {
    var input = qs('api-token');
    state.token = input ? String(input.value || '').trim() : '';
    if (state.token) {
      writeStoredToken(state.token);
    } else {
      clearStoredToken();
    }
  }

  function selectedVmidsFromInventory() {
    return state.selectedVmids.slice().sort(function (left, right) {
      return Number(left) - Number(right);
    });
  }

  function bulkAction(action) {
    var vmids = selectedVmidsFromInventory();
    if (!vmids.length) {
      setBanner('No VMs selected for bulk action.', 'warn');
      return;
    }
    setBanner('Bulk action' + action + ' for' + vmids.length + ' VM(s) queuing...', 'info');
    postJson('/actions/bulk', {
      vmids: vmids,
      action: action
    }).then(function (payload) {
      var queued = payload && payload.queued_count != null ? payload.queued_count : vmids.length;
      setBanner('Bulk action' + action + ' queued:' + queued + ' VM(s).', 'ok');
      return loadDashboard();
    }).catch(function (error) {
      setBanner('Bulk actionfehlgeschlagen: ' + error.message, 'warn');
    });
  }

  function parseJsonField(id, label) {
    var raw = String(qs(id) ? qs(id).value : '').trim();
    if (!raw) {
      return {};
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      throw new Error(label + ' is not valid JSON');
    }
  }

  function savePolicy() {
    var name = String(qs('policy-name') ? qs('policy-name').value : '').trim();
    var payload;
    if (!name) {
      setBanner('Policy name is required.', 'warn');
      return;
    }
    try {
      payload = {
        name: name,
        priority: Number(qs('policy-priority') ? qs('policy-priority').value : '100') || 0,
        enabled: Boolean(qs('policy-enabled') && qs('policy-enabled').checked),
        selector: parseJsonField('policy-selector', 'Selector'),
        profile: parseJsonField('policy-profile', 'Profile')
      };
    } catch (error) {
      setBanner(error.message, 'warn');
      return;
    }

    var updateExisting = Boolean(state.selectedPolicyName && state.selectedPolicyName === name);
    var path = updateExisting ? '/policies/' + encodeURIComponent(name) : '/policies';
    var method = updateExisting ? 'PUT' : 'POST';
    setBanner('Policy ' + name + ' saving...', 'info');
    request(path, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      state.selectedPolicyName = name;
      return loadDashboard();
    }).then(function () {
      loadPolicyIntoEditor(name);
      setBanner('Policy ' + name + ' saved.', 'ok');
    }).catch(function (error) {
      setBanner('Failed to save policy:' + error.message, 'warn');
    });
  }

  function deleteSelectedPolicy() {
    var name = String(qs('policy-name') ? qs('policy-name').value : '').trim() || state.selectedPolicyName;
    if (!name) {
      setBanner('No policy selected.', 'warn');
      return;
    }
    setBanner('Policy ' + name + ' deleting...', 'info');
    request('/policies/' + encodeURIComponent(name), {
      method: 'DELETE'
    }).then(function () {
      resetPolicyEditor();
      return loadDashboard();
    }).then(function () {
      setBanner('Policy ' + name + ' deleted.', 'ok');
    }).catch(function (error) {
      setBanner('Failed to delete policy:' + error.message, 'warn');
    });
  }

  function loadDashboard() {
    if (!state.token) {
      setAuthMode(false);
      setBanner('No API token set.', 'warn');
      return Promise.resolve();
    }
    setBanner('Loading Beagle Manager...', 'info');
    return Promise.all([
      request('/health'),
      request('/vms'),
      request('/policies'),
      request('/virtualization/overview')
    ]).then(function (results) {
      var health = results[0] || {};
      state.inventory = (results[1] && results[1].vms) || [];
      state.policies = (results[2] && results[2].policies) || [];
      state.virtualizationOverview = results[3] || null;
      setAuthMode(true);
      statCardFromHealth(health, state.virtualizationOverview);
      renderInventory();
      renderPolicies();
      renderVirtualizationPanel();
      setBanner('Connected. Inventory and policies up to date.', 'ok');
      if (state.selectedVmid) {
        return loadDetail(state.selectedVmid);
      }
      if (filteredInventory().length) {
        return loadDetail(profileOf(filteredInventory()[0]).vmid);
      }
      return null;
    }).catch(function (error) {
      setAuthMode(false);
      text('stat-manager', 'Error');
      text('stat-manager-meta', error.message);
      setBanner('Connection failed:' + error.message, 'warn');
    });
  }

  function postJson(path, payload) {
    return request(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload || {})
    });
  }

  function executeAction(action, sourceButton) {
    var vmid = state.selectedVmid;
    if (!vmid) {
      return;
    }
    if (action === 'refresh-detail') {
      loadDetail(vmid);
      return;
    }
    if (action === 'download-linux') {
      blobRequest('/vms/' + vmid + '/installer.sh', 'pve-thin-client-usb-installer-vm-' + vmid + '.sh').catch(function (error) {
        setBanner('Linux-Installer Download failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'download-windows') {
      blobRequest('/vms/' + vmid + '/installer.ps1', 'pve-thin-client-usb-installer-vm-' + vmid + '.ps1').catch(function (error) {
        setBanner('Windows-Installer Download failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'usb-refresh') {
      setBanner('Refreshing USB inventory for VM ' + vmid + '...', 'info');
      postJson('/vms/' + vmid + '/usb/refresh', {}).then(function () {
        return loadDetail(vmid);
      }).catch(function (error) {
        setBanner('USB-Refresh failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'usb-attach') {
      setBanner('Attaching USB device to VM ' + vmid + '...', 'info');
      postJson('/vms/' + vmid + '/usb/attach', {
        busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || ''
      }).then(function () {
        return loadDetail(vmid);
      }).catch(function (error) {
        setBanner('USB-Attach failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'usb-detach') {
      setBanner('Detaching USB device from VM ' + vmid + '...', 'info');
      postJson('/vms/' + vmid + '/usb/detach', {
        busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || '',
        port: sourceButton && sourceButton.getAttribute('data-usb-port') || ''
      }).then(function () {
        return loadDetail(vmid);
      }).catch(function (error) {
        setBanner('USB-Detach failed:' + error.message, 'warn');
      });
      return;
    }
    if (action === 'installer-prep') {
      setBanner('Preparing installer for VM ' + vmid + '...', 'info');
      postJson('/vms/' + vmid + '/installer-prep', {}).then(function () {
        return loadDetail(vmid);
      }).catch(function (error) {
        setBanner('Installer preparation failed: ' + error.message, 'warn');
      });
      return;
    }
    if (action === 'sunshine-ui') {
      postJson('/vms/' + vmid + '/sunshine-access', {}).then(function (payload) {
        var url = payload && payload.sunshine_access ? payload.sunshine_access.url : '';
        if (!url) {
          throw new Error('No Sunshine URL received');
        }
        window.open(url, '_blank', 'noopener');
      }).catch(function (error) {
        setBanner('Sunshine access failed: ' + error.message, 'warn');
      });
      return;
    }
    setBanner('Queuing action ' + action + ' for VM ' + vmid + '...', 'info');
    postJson('/vms/' + vmid + '/actions', { action: action }).then(function () {
      setBanner('Action ' + action + ' queued for VM ' + vmid + '.', 'ok');
      return loadDetail(vmid);
    }).catch(function (error) {
      setBanner('Action failed: ' + error.message, 'warn');
    });
  }

  function bindEvents() {
    var tokenField = qs('api-token');
    if (tokenField) {
      tokenField.value = state.token;
      tokenField.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          saveToken();
          loadDashboard();
        }
      });
    }
    qs('web-ui-url').value = webUiUrl();
    qs('api-base').value = apiBase();
    qs('connect-button').addEventListener('click', function () {
      saveToken();
      loadDashboard();
    });
    if (qs('open-connect-modal')) {
      qs('open-connect-modal').addEventListener('click', openAuthModal);
    }
    if (qs('open-connect-menu')) {
      qs('open-connect-menu').addEventListener('click', function () {
        closeAccountMenu();
        openAuthModal();
      });
    }
    if (qs('close-auth-modal')) {
      qs('close-auth-modal').addEventListener('click', closeAuthModal);
    }
    if (qs('avatar-toggle')) {
      qs('avatar-toggle').addEventListener('click', function () {
        var shell = accountShell();
        if (shell) {
          shell.classList.toggle('menu-open');
        }
      });
    }
    document.addEventListener('click', function (event) {
      var shell = accountShell();
      if (shell && !shell.contains(event.target)) {
        shell.classList.remove('menu-open');
      }
    });
    if (qs('sidebar-nav')) {
      qs('sidebar-nav').addEventListener('click', function (event) {
        var trigger = event.target.closest('[data-panel]');
        if (!trigger) {
          return;
        }
        setActivePanel(trigger.getAttribute('data-panel'));
      });
    }
    qs('clear-token').addEventListener('click', function () {
      state.token = '';
      clearStoredToken();
      if (tokenField) {
        tokenField.value = '';
      }
      state.inventory = [];
      state.selectedVmid = null;
      state.selectedVmids = [];
      renderInventory();
      setBanner('API-Token deleted.', 'info');
      setAuthMode(false);
      closeAccountMenu();
    });
    if (qs('clear-token-menu')) {
      qs('clear-token-menu').addEventListener('click', function () {
        if (qs('clear-token')) {
          qs('clear-token').click();
        }
      });
    }
    qs('refresh-all').addEventListener('click', function () {
      loadDashboard();
    });
    if (qs('refresh-virt')) {
      qs('refresh-virt').addEventListener('click', function () {
        loadDashboard();
      });
    }
    qs('search-input').addEventListener('input', renderInventory);
    qs('role-filter').addEventListener('change', renderInventory);
    qs('eligible-only').addEventListener('change', renderInventory);
    qs('inventory-select-all').addEventListener('change', function (event) {
      var vmids = filteredInventory().map(function (vm) {
        return profileOf(vm).vmid;
      });
      if (event.target.checked) {
        state.selectedVmids = Array.from(new Set(state.selectedVmids.concat(vmids)));
      } else {
        state.selectedVmids = state.selectedVmids.filter(function (vmid) {
          return vmids.indexOf(vmid) === -1;
        });
      }
      renderInventory();
    });
    qs('bulk-healthcheck').addEventListener('click', function () {
      bulkAction('healthcheck');
    });
    qs('bulk-support-bundle').addEventListener('click', function () {
      bulkAction('support-bundle');
    });
    qs('bulk-restart-session').addEventListener('click', function () {
      bulkAction('restart-session');
    });
    qs('bulk-restart-runtime').addEventListener('click', function () {
      bulkAction('restart-runtime');
    });
    qs('inventory-body').addEventListener('click', function (event) {
      var select = event.target.closest('input[data-select-vmid]');
      if (select) {
        var selectedVmid = Number(select.getAttribute('data-select-vmid'));
        if (select.checked) {
          if (state.selectedVmids.indexOf(selectedVmid) === -1) {
            state.selectedVmids.push(selectedVmid);
          }
        } else {
          state.selectedVmids = state.selectedVmids.filter(function (vmid) {
            return vmid !== selectedVmid;
          });
        }
        renderInventory();
        return;
      }
      var row = event.target.closest('tr[data-vmid]');
      if (!row) {
        return;
      }
      loadDetail(row.getAttribute('data-vmid'));
    });
    if (qs('detail-tabbar')) {
      qs('detail-tabbar').addEventListener('click', function(event) {
        var trigger = event.target.closest('[data-detail-panel]');
        if (!trigger) {
          return;
        }
        var panelName = trigger.getAttribute('data-detail-panel');
        setActiveDetailPanel(panelName);
        if (panelName === 'config' && state.selectedVmid) {
          loadVmConfig(state.selectedVmid);
        }
      });
    }
    qs('detail-stack').addEventListener('click', function (event) {
      var button = event.target.closest('button[data-action]');
      if (!button) {
        return;
      }
      executeAction(button.getAttribute('data-action'), button);
    });
    qs('detail-actions').addEventListener('click', function (event) {
      var button = event.target.closest('button[data-action]');
      if (!button) {
        return;
      }
      executeAction(button.getAttribute('data-action'), button);
    });
    qs('policies-list').addEventListener('click', function (event) {
      var card = event.target.closest('[data-policy-name]');
      if (!card) {
        return;
      }
      loadPolicyIntoEditor(card.getAttribute('data-policy-name'));
    });
    qs('policy-save').addEventListener('click', savePolicy);
    qs('policy-new').addEventListener('click', function () {
      resetPolicyEditor();
      setBanner('Policy editor reset.', 'info');
    });
    qs('policy-delete').addEventListener('click', deleteSelectedPolicy);
  }

  applyTitle();
  consumeTokenFromLocation();
  bindEvents();
  resetPolicyEditor();
  (function bootstrapHashState() {
    var hashState = parseAppHash();
    if (hashState.panel) {
      state.activePanel = hashState.panel;
    }
    if (hashState.detail) {
      state.activeDetailPanel = hashState.detail;
    }
    if (hashState.vmid && /^\\d+$/.test(hashState.vmid)) {
      state.selectedVmid = Number(hashState.vmid);
    }
  })();
  setActivePanel(state.activePanel);
  setAuthMode(Boolean(state.token));
  updateSessionChrome();
  loadDashboard();
  window.addEventListener('hashchange', function() {
    var hashState = parseAppHash();
    if (hashState.panel && hashState.panel !== state.activePanel) {
      setActivePanel(hashState.panel);
    }
    if (hashState.detail && hashState.detail !== state.activeDetailPanel) {
      setActiveDetailPanel(hashState.detail);
    }
    if (hashState.vmid && /^\\d+$/.test(hashState.vmid) && Number(hashState.vmid) !== state.selectedVmid) {
      loadDetail(hashState.vmid);
    }
  });
  window.setInterval(loadDashboard, 30000);
})();

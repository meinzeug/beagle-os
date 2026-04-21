import {
  POLICY_NAME_PATTERN,
  state
} from './state.js';
import { chip, escapeHtml, fieldBlock, qs } from './dom.js';
import { request, runSingleFlight } from './api.js';
import { sanitizeIdentifier } from './auth.js';

const policyHooks = {
  setBanner() {},
  addToActivityLog() {},
  loadDashboard() {
    return Promise.resolve();
  },
  requestConfirm() {
    return Promise.resolve(true);
  }
};

export function configurePolicies(nextHooks) {
  Object.assign(policyHooks, nextHooks || {});
}

export function renderPolicies() {
  const node = qs('policies-list');
  if (!node) {
    return;
  }
  if (!state.policies.length) {
    node.innerHTML = '<div class="empty-card">No policies found.</div>';
    return;
  }
  node.innerHTML = state.policies.map((policy) => {
    const selector = policy.selector || {};
    const profile = policy.profile || {};
    return '<article class="policy-card' + (state.selectedPolicyName === policy.name ? ' active' : '') + '" data-policy-name="' + escapeHtml(policy.name || '') + '">' +
      '<div class="policy-head"><strong>' + escapeHtml(policy.name || 'policy') + '</strong>' + chip('prio ' + String(policy.priority || 0), 'muted') + '</div>' +
      '<div class="policy-grid">' +
      fieldBlock('Selector', JSON.stringify(selector), 'mono') +
      fieldBlock('Profile', JSON.stringify(profile), 'mono') +
      '</div>' +
      '</article>';
  }).join('');
}

export function resetPolicyEditor() {
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

export function loadPolicyIntoEditor(name) {
  const policy = state.policies.find((item) => item.name === name);
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

export function parseJsonField(id, label) {
  const raw = String(qs(id) ? qs(id).value : '').trim();
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    throw new Error(label + ' is not valid JSON');
  }
}

export function savePolicy() {
  let name = String(qs('policy-name') ? qs('policy-name').value : '').trim();
  let payload;
  try {
    name = sanitizeIdentifier(name, 'Policy-Name', POLICY_NAME_PATTERN, 2, 80);
  } catch (error) {
    policyHooks.setBanner(error.message, 'warn');
    return;
  }
  try {
    payload = {
      name,
      priority: Number(qs('policy-priority') ? qs('policy-priority').value : '100') || 0,
      enabled: Boolean(qs('policy-enabled') && qs('policy-enabled').checked),
      selector: parseJsonField('policy-selector', 'Selector'),
      profile: parseJsonField('policy-profile', 'Profile')
    };
  } catch (error) {
    policyHooks.setBanner(error.message, 'warn');
    return;
  }
  const updateExisting = Boolean(state.selectedPolicyName && state.selectedPolicyName === name);
  const path = updateExisting ? '/policies/' + encodeURIComponent(name) : '/policies';
  const method = updateExisting ? 'PUT' : 'POST';
  runSingleFlight('policy-save:' + name, () => {
    policyHooks.setBanner('Policy ' + name + ' saving...', 'info');
    return request(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(() => {
      state.selectedPolicyName = name;
      return policyHooks.loadDashboard();
    }).then(() => {
      loadPolicyIntoEditor(name);
      policyHooks.setBanner('Policy ' + name + ' saved.', 'ok');
    }).catch((error) => {
      policyHooks.setBanner('Failed to save policy:' + error.message, 'warn');
    });
  });
}

export function deleteSelectedPolicy() {
  const name = String(qs('policy-name') ? qs('policy-name').value : '').trim() || state.selectedPolicyName;
  if (!name) {
    policyHooks.setBanner('No policy selected.', 'warn');
    return;
  }
  policyHooks.requestConfirm({
    title: 'Policy loeschen?',
    message: 'Policy "' + name + '" wirklich loeschen?',
    confirmLabel: 'Loeschen',
    danger: true
  }).then((ok) => {
    if (!ok) {
      return;
    }
    runSingleFlight('policy-delete:' + name, () => {
      policyHooks.setBanner('Policy ' + name + ' deleting...', 'info');
      return request('/policies/' + encodeURIComponent(name), {
        method: 'DELETE'
      }).then(() => {
        policyHooks.addToActivityLog('policy-delete', null, 'ok', name);
        resetPolicyEditor();
        return policyHooks.loadDashboard();
      }).then(() => {
        policyHooks.setBanner('Policy ' + name + ' deleted.', 'ok');
      }).catch((error) => {
        policyHooks.addToActivityLog('policy-delete', null, 'warn', error.message);
        policyHooks.setBanner('Failed to delete policy:' + error.message, 'warn');
      });
    });
  });
}
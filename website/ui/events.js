import { qs, readSecretValue } from './dom.js';
import {
  clearSessionState,
  loginWithCredentials,
  logoutSession,
  markSessionActivity,
  saveToken,
  sanitizeIdentifier,
  sanitizePassword,
  updateConnectButton
} from './auth.js';
import { toggleDarkMode } from './theme.js';
import { toggleAutoRefresh, renderActivityLog } from './activity.js';
import {
  accountShell,
  closeAccountMenu,
  closeAuthModal,
  completeOnboarding,
  openAuthModal,
  openOnboardingModal,
  setActiveDetailPanel,
  setActivePanel
} from './panels.js';
import {
  bulkAction,
  bulkVmPowerAction,
  exportEndpointsJson,
  exportInventoryCsv,
  exportInventoryJson,
  filteredInventory,
  profileOf,
  renderInventory,
  resetInventoryFilters,
  runVmPowerAction
} from './inventory.js';
import { executeAction } from './actions.js';
import {
  createProvisionedVm,
  createProvisionedVmWithPrefix,
  closeProvisionModal,
  closeProvisionProgressModal,
  loadProvisioningCatalog,
  openProvisioningWorkspace,
  renderProvisioningWorkspace
} from './provisioning.js';
import {
  closeTemplateBuilderModal,
  closeTemplateBuilderProgressModal,
  createTemplateFromModal
} from './template_builder.js';
import {
  createPoolFromWizard,
  deleteSelectedPolicy,
  loadPolicyIntoEditor,
  nextPoolWizardStep,
  prevPoolWizardStep,
  renderPoolGpuClassOptions,
  refreshGamingMetricsDashboard,
  refreshSessionHandoverDashboard,
  refreshPoolData,
  refreshPoolOverview,
  refreshSelectedPoolEntitlements,
  mutateSelectedPoolEntitlements,
  useSelectedTemplate,
  rebuildSelectedTemplate,
  deleteSelectedTemplate,
  deleteSelectedPool,
  scaleSelectedPool,
  recycleSelectedPoolVm,
  resetPolicyEditor,
  syncPolicyProfilePreview,
  resetPoolWizard,
  setPoolWizardStep,
  selectPool,
  savePolicy
} from './policies.js';
import {
  deleteIamRole,
  deleteIamUser,
  loadIamRoleIntoEditor,
  loadIamSessions,
  loadIamUserIntoEditor,
  refreshIamData,
  renderIamRoleDiff,
  renderIamRoles,
  renderIamUsers,
  renderPermissionTagEditor,
  resetIamRoleEditor,
  resetIamUserEditor,
  revokeIamUserSessions,
  saveIamRole,
  saveIamUser
} from './iam.js';
import {
  loadVirtualizationInspector,
  loadVmConfig,
  createIpamZoneForBridge,
  openStoragePoolDetail,
  openVirtualizationBridgeDetail,
  openVirtualizationNodeDetail,
  setStoragePoolQuota,
  setVirtualizationNodeFilter,
  assignGpuToVm,
  releaseGpuFromVm,
  loadMdevTypes,
  createMdevInstance,
  assignMdevToVm,
  deleteMdevInstance,
  loadSriovDevices,
  loadSriovVfs,
  setSriovVfCount
} from './virtualization.js';
import { loadDashboard } from './dashboard.js';
import { MAX_USERNAME_LEN, USERNAME_PATTERN, state } from './state.js';

const eventHooks = {
  loadDetail() {
    return Promise.resolve();
  },
  closeDetail() {},
  setBanner() {},
  loadAuditReport() {
    return Promise.resolve();
  },
  resetAuditFilters() {},
  exportAuditCsv() {
    return Promise.resolve();
  },
  onAuditRangeChanged() {},
  loadAuditExportTargets() {
    return Promise.resolve();
  },
  loadAuditFailureQueue() {
    return Promise.resolve();
  },
  replayAuditFailures() {
    return Promise.resolve();
  },
  runAuditReportBuilder() {
    return Promise.resolve();
  },
  testAuditExportTarget() {
    return Promise.resolve();
  },
  openProvisionModal() {
    openProvisioningWorkspace();
  },
  onDetailPanelChange(_panelName) {}
};

export function configureEvents(nextHooks) {
  Object.assign(eventHooks, nextHooks || {});
}

export function bindEvents() {
  // Back button on VM detail page
  if (qs('vdp-back')) {
    qs('vdp-back').addEventListener('click', () => {
      eventHooks.closeDetail();
    });
  }

  // View toggle (list / grid)
  const viewToggle = document.getElementById('inv-view-toggle');
  if (viewToggle) {
    viewToggle.addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-view]');
      if (!btn) return;
      const view = btn.getAttribute('data-view');
      const body = document.getElementById('inventory-body');
      if (!body) return;
      body.classList.toggle('vm-body-list', view === 'list');
      body.classList.toggle('vm-body-grid', view === 'grid');
      viewToggle.querySelectorAll('.inv-view-btn').forEach((b) => {
        b.classList.toggle('inv-view-btn-active', b === btn);
      });
    });
  }

  if (qs('toggle-dark-mode')) {
    qs('toggle-dark-mode').addEventListener('click', toggleDarkMode);
  }
  if (qs('toggle-auto-refresh')) {
    qs('toggle-auto-refresh').addEventListener('click', toggleAutoRefresh);
  }
  if (qs('clear-activity-log')) {
    qs('clear-activity-log').addEventListener('click', () => {
      renderActivityLog();
      eventHooks.setBanner('Aktivitaetslog geleert.', 'info');
    });
  }

  const tokenField = qs('api-token');
  const usernameField = qs('auth-username');
  const passwordField = qs('auth-password');
  const authForm = qs('auth-form');
  const onboardingPasswordField = qs('onboarding-password');
  const onboardingPasswordConfirmField = qs('onboarding-password-confirm');

  function submitAuthLogin() {
    markSessionActivity();
    if (state.onboarding && state.onboarding.pending) {
      openOnboardingModal();
      return Promise.resolve();
    }
    const username = String(usernameField ? usernameField.value : '').trim();
    const password = String(passwordField ? passwordField.value : '');
    if (username || password) {
      if (!username || !password) {
        eventHooks.setBanner('Benutzername und Passwort erforderlich.', 'warn');
        return Promise.resolve();
      }
      return loginWithCredentials(username, password)
        .then(() => {
          return loadDashboard().catch((error) => {
            eventHooks.setBanner('Anmeldung erfolgreich, aber das Dashboard konnte nicht geladen werden: ' + error.message, 'warn');
          });
        })
        .catch((error) => {
          eventHooks.setBanner('Login fehlgeschlagen: ' + error.message, 'warn');
        });
    }
    saveToken();
    return loadDashboard().catch((error) => {
      eventHooks.setBanner('Token gespeichert, aber das Dashboard konnte nicht geladen werden: ' + error.message, 'warn');
    });
  }

  if (tokenField) {
    tokenField.value = state.token;
    tokenField.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        saveToken();
        loadDashboard();
      }
    });
  }

  if (authForm) {
    authForm.addEventListener('submit', (event) => {
      event.preventDefault();
      void submitAuthLogin();
    });
  }

  if (qs('connect-button')) {
    qs('connect-button').addEventListener('click', (event) => {
      event.preventDefault();
      void submitAuthLogin();
    });
  }

  if (qs('open-connect-modal')) {
    qs('open-connect-modal').addEventListener('click', () => {
      if (state.token) {
        logoutSession().finally(() => {
          clearSessionState('Abgemeldet.', 'info');
        });
      } else {
        openAuthModal();
      }
    });
  }
  if (qs('open-connect-menu')) {
    qs('open-connect-menu').addEventListener('click', () => {
      closeAccountMenu();
      openAuthModal();
    });
  }
  if (qs('close-auth-modal')) {
    qs('close-auth-modal').addEventListener('click', closeAuthModal);
  }

  if (qs('onboarding-complete')) {
    qs('onboarding-complete').addEventListener('click', () => {
      Promise.resolve().then(() => {
        try {
          const onboardingUser = sanitizeIdentifier(
            String(qs('onboarding-username') ? qs('onboarding-username').value : ''),
            'Onboarding-Benutzername',
            USERNAME_PATTERN,
            1,
            MAX_USERNAME_LEN
          );
          const onboardingPw = sanitizePassword(String(qs('onboarding-password') ? qs('onboarding-password').value : ''), 'Onboarding-Passwort');
          if (qs('onboarding-username')) {
            qs('onboarding-username').value = onboardingUser;
          }
          if (qs('onboarding-password')) {
            qs('onboarding-password').value = onboardingPw;
          }
        } catch (error) {
          eventHooks.setBanner(error.message, 'warn');
          throw error;
        }
      }).then(() => completeOnboarding()).then(() => {
        if (state.onboarding && !state.onboarding.pending) {
          openAuthModal();
        }
      }).catch(() => null);
    });
  }

  [onboardingPasswordField, onboardingPasswordConfirmField].forEach((field) => {
    if (field) {
      field.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && qs('onboarding-complete')) {
          qs('onboarding-complete').click();
        }
      });
    }
  });

  if (qs('avatar-toggle')) {
    qs('avatar-toggle').addEventListener('click', () => {
      const shell = accountShell();
      if (shell) {
        shell.classList.toggle('menu-open');
      }
    });
  }

  document.addEventListener('click', (event) => {
    const shell = accountShell();
    if (shell && !shell.contains(event.target)) {
      shell.classList.remove('menu-open');
    }
  });

  if (qs('sidebar-nav')) {
    qs('sidebar-nav').addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-panel]');
      if (!trigger) {
        return;
      }
      const panelName = String(trigger.getAttribute('data-panel') || '').trim();
      markSessionActivity();
      if (panelName === 'provisioning') {
        openProvisioningWorkspace();
        closeMobileSidebar();
        return;
      }
      setActivePanel(panelName);
      closeMobileSidebar();
    });
  }

  function openMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = qs('sidebar-backdrop');
    if (sidebar) {
      sidebar.classList.add('mobile-open');
    }
    if (backdrop) {
      backdrop.classList.add('active');
    }
    document.body.classList.add('mobile-menu-open');
  }

  function closeMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const backdrop = qs('sidebar-backdrop');
    if (sidebar) {
      sidebar.classList.remove('mobile-open');
    }
    if (backdrop) {
      backdrop.classList.remove('active');
    }
    document.body.classList.remove('mobile-menu-open');
  }

  if (qs('mobile-menu-toggle')) {
    qs('mobile-menu-toggle').addEventListener('click', openMobileSidebar);
  }
  if (qs('sidebar-close')) {
    qs('sidebar-close').addEventListener('click', closeMobileSidebar);
  }
  if (qs('sidebar-backdrop')) {
    qs('sidebar-backdrop').addEventListener('click', closeMobileSidebar);
  }

  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) {
      return;
    }
    const target = event.target;
    const tag = target && target.tagName ? String(target.tagName).toLowerCase() : '';
    if (tag === 'input' || tag === 'textarea' || (target && target.isContentEditable)) {
      return;
    }
    if (qs('search-input')) {
      event.preventDefault();
      qs('search-input').focus();
    }
  });

  if (qs('clear-token')) {
    qs('clear-token').addEventListener('click', () => {
      logoutSession().finally(() => {
        clearSessionState('Anmeldedaten geloescht.', 'info');
      });
      if (usernameField) {
        usernameField.value = '';
      }
      if (passwordField) {
        passwordField.value = '';
      }
      if (tokenField) {
        tokenField.value = '';
      }
      closeAccountMenu();
    });
  }
  if (qs('clear-token-menu')) {
    qs('clear-token-menu').addEventListener('click', () => {
      if (qs('clear-token')) {
        qs('clear-token').click();
      }
    });
  }

  if (qs('refresh-all')) {
    qs('refresh-all').addEventListener('click', () => {
      markSessionActivity();
      if (state.activePanel === 'audit') {
        eventHooks.loadAuditReport();
        return;
      }
      loadDashboard();
    });
  }
  if (qs('audit-refresh')) {
    qs('audit-refresh').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.loadAuditReport();
    });
  }
  if (qs('audit-reset')) {
    qs('audit-reset').addEventListener('click', () => {
      eventHooks.resetAuditFilters();
      eventHooks.loadAuditReport();
    });
  }
  if (qs('audit-export-csv')) {
    qs('audit-export-csv').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.exportAuditCsv();
    });
  }
  if (qs('audit-apply')) {
    qs('audit-apply').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.loadAuditReport();
    });
  }
  if (qs('audit-filter-range')) {
    qs('audit-filter-range').addEventListener('change', () => {
      eventHooks.onAuditRangeChanged();
    });
  }
  if (qs('audit-targets-refresh')) {
    qs('audit-targets-refresh').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.loadAuditExportTargets();
    });
  }
  if (qs('audit-failures-refresh')) {
    qs('audit-failures-refresh').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.loadAuditFailureQueue();
    });
  }
  if (qs('audit-failures-replay')) {
    qs('audit-failures-replay').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.replayAuditFailures();
    });
  }
  if (qs('audit-builder-run')) {
    qs('audit-builder-run').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.runAuditReportBuilder();
    });
  }
  if (qs('audit-export-targets')) {
    qs('audit-export-targets').addEventListener('click', (event) => {
      const button = event.target.closest('[data-audit-target-test]');
      if (!button) return;
      markSessionActivity();
      eventHooks.testAuditExportTarget(button.getAttribute('data-audit-target-test'));
    });
  }
  if (qs('open-provision-create')) {
    qs('open-provision-create').addEventListener('click', () => {
      markSessionActivity();
      eventHooks.openProvisionModal();
    });
  }
  if (qs('refresh-virt')) {
    qs('refresh-virt').addEventListener('click', () => {
      markSessionActivity();
      loadDashboard();
    });
  }
  if (qs('refresh-endpoints')) {
    qs('refresh-endpoints').addEventListener('click', () => {
      markSessionActivity();
      loadDashboard();
    });
  }

  if (qs('export-inventory-json')) {
    qs('export-inventory-json').addEventListener('click', exportInventoryJson);
  }
  if (qs('export-inventory-csv')) {
    qs('export-inventory-csv').addEventListener('click', exportInventoryCsv);
  }
  if (qs('export-endpoints-json')) {
    qs('export-endpoints-json').addEventListener('click', exportEndpointsJson);
  }

  if (qs('search-input')) {
    qs('search-input').addEventListener('input', renderInventory);
  }
  if (qs('role-filter')) {
    qs('role-filter').addEventListener('change', renderInventory);
  }
  if (qs('eligible-only')) {
    qs('eligible-only').addEventListener('change', renderInventory);
  }
  if (qs('clear-filters')) {
    qs('clear-filters').addEventListener('click', () => {
      resetInventoryFilters();
      eventHooks.setBanner('Filter zurueckgesetzt.', 'info');
    });
  }
  if (qs('inventory-select-all')) {
    qs('inventory-select-all').addEventListener('change', (event) => {
      const vmids = filteredInventory().map((vm) => profileOf(vm).vmid);
      if (event.target.checked) {
        state.selectedVmids = Array.from(new Set(state.selectedVmids.concat(vmids)));
      } else {
        state.selectedVmids = state.selectedVmids.filter((vmid) => vmids.indexOf(vmid) === -1);
      }
      renderInventory();
    });
  }

  const bulkButtons = {
    'bulk-healthcheck': () => bulkAction('healthcheck'),
    'bulk-support-bundle': () => bulkAction('support-bundle'),
    'bulk-restart-session': () => bulkAction('restart-session'),
    'bulk-restart-runtime': () => bulkAction('restart-runtime'),
    'bulk-update-scan': () => bulkAction('os-update-scan'),
    'bulk-update-download': () => bulkAction('os-update-download'),
    'bulk-vm-start': () => bulkVmPowerAction('start'),
    'bulk-vm-stop': () => bulkVmPowerAction('stop'),
    'bulk-vm-reboot': () => bulkVmPowerAction('reboot')
  };
  Object.keys(bulkButtons).forEach((id) => {
    if (qs(id)) {
      qs(id).addEventListener('click', bulkButtons[id]);
    }
  });

  if (qs('inventory-body')) {
    qs('inventory-body').addEventListener('click', (event) => {
      const powerButton = event.target.closest('button[data-vm-power]');
      if (powerButton) {
        const actionName = powerButton.getAttribute('data-vm-power');
        const actionVmid = Number(powerButton.getAttribute('data-vmid') || '0');
        runVmPowerAction(actionVmid, actionName);
        return;
      }
      const consoleButton = event.target.closest('button[data-vm-console]');
      if (consoleButton) {
        const consoleName = String(consoleButton.getAttribute('data-vm-console') || '').trim().toLowerCase();
        const consoleVmid = Number(consoleButton.getAttribute('data-vmid') || '0');
        if (consoleName === 'novnc' && consoleVmid > 0) {
          const previousVmid = state.selectedVmid;
          state.selectedVmid = consoleVmid;
          executeAction('novnc-ui', consoleButton);
          state.selectedVmid = previousVmid;
        }
        return;
      }
      const select = event.target.closest('input[data-select-vmid]');
      if (select) {
        const selectedVmid = Number(select.getAttribute('data-select-vmid'));
        if (select.checked) {
          if (state.selectedVmids.indexOf(selectedVmid) === -1) {
            state.selectedVmids.push(selectedVmid);
          }
        } else {
          state.selectedVmids = state.selectedVmids.filter((vmid) => vmid !== selectedVmid);
        }
        renderInventory();
        return;
      }
      // "Details" button on a VM card
      const detailButton = event.target.closest('button[data-vm-detail]');
      if (detailButton) {
        eventHooks.loadDetail(detailButton.getAttribute('data-vm-detail'));
        return;
      }
      // Click anywhere on the VM card itself (not on buttons/checkboxes/action area)
      const card = event.target.closest('.vm-card[data-vmid]');
      if (card) {
        // Don't navigate when clicking inside the actions area or checkbox label
        if (event.target.closest('.vm-card-actions') || event.target.closest('.vm-card-check')) {
          return;
        }
        eventHooks.loadDetail(card.getAttribute('data-vmid'));
      }
    });
  }

  if (qs('detail-tabbar')) {
    qs('detail-tabbar').addEventListener('click', (event) => {
      const trigger = event.target.closest('[data-detail-panel]');
      if (!trigger) {
        return;
      }
      const panelName = trigger.getAttribute('data-detail-panel');
      setActiveDetailPanel(panelName);
      eventHooks.onDetailPanelChange(panelName);
      if (panelName === 'config' && state.selectedVmid) {
        loadVmConfig(state.selectedVmid);
      }
    });
  }

  if (qs('detail-stack')) {
    qs('detail-stack').addEventListener('click', (event) => {
      const revealBtn = event.target.closest('button[data-reveal-id]');
      if (revealBtn) {
        const targetId = revealBtn.getAttribute('data-reveal-id');
        const secretSpan = document.getElementById(targetId);
        if (secretSpan) {
          const visible = secretSpan.getAttribute('data-visible') === '1';
          if (visible) {
            secretSpan.textContent = '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022';
            secretSpan.setAttribute('data-visible', '0');
            revealBtn.textContent = 'Anzeigen';
          } else {
            secretSpan.textContent = readSecretValue(targetId);
            secretSpan.setAttribute('data-visible', '1');
            revealBtn.textContent = 'Verbergen';
          }
        }
        return;
      }
      const button = event.target.closest('button[data-action]');
      if (button) {
        executeAction(button.getAttribute('data-action'), button);
      }
    });
  }

  if (qs('detail-actions')) {
    qs('detail-actions').addEventListener('click', (event) => {
      const button = event.target.closest('button[data-action]');
      if (button) {
        executeAction(button.getAttribute('data-action'), button);
      }
    });
  }

  if (qs('policies-list')) {
    qs('policies-list').addEventListener('click', (event) => {
      const card = event.target.closest('[data-policy-name]');
      if (card) {
        loadPolicyIntoEditor(card.getAttribute('data-policy-name'));
      }
    });
  }
  if (qs('policy-save')) {
    qs('policy-save').addEventListener('click', savePolicy);
  }
  if (qs('policy-new')) {
    qs('policy-new').addEventListener('click', () => {
      resetPolicyEditor();
      eventHooks.setBanner('Policy editor reset.', 'info');
    });
  }
  if (qs('policy-delete')) {
    qs('policy-delete').addEventListener('click', deleteSelectedPolicy);
  }
  if (qs('policy-structured-grid')) {
    qs('policy-structured-grid').addEventListener('input', syncPolicyProfilePreview);
    qs('policy-structured-grid').addEventListener('change', syncPolicyProfilePreview);
  }
  if (qs('pool-create')) {
    qs('pool-create').addEventListener('click', createPoolFromWizard);
  }
  if (qs('pool-wizard-next')) {
    qs('pool-wizard-next').addEventListener('click', nextPoolWizardStep);
  }
  if (qs('pool-wizard-prev')) {
    qs('pool-wizard-prev').addEventListener('click', prevPoolWizardStep);
  }
  if (qs('pool-wizard-reset')) {
    qs('pool-wizard-reset').addEventListener('click', () => {
      resetPoolWizard();
      eventHooks.setBanner('Pool-Wizard zurueckgesetzt.', 'info');
    });
  }
  if (qs('pool-wizard-steps')) {
    qs('pool-wizard-steps').addEventListener('click', (event) => {
      const button = event.target.closest('[data-pool-step-target]');
      if (!button) {
        return;
      }
      const step = Number(button.getAttribute('data-pool-step-target') || 1);
      setPoolWizardStep(step);
    });
  }
  if (qs('pool-data-refresh')) {
    qs('pool-data-refresh').addEventListener('click', () => {
      refreshPoolData().catch((error) => {
        eventHooks.setBanner('Pool-Daten konnten nicht geladen werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-type')) {
    qs('pool-type').addEventListener('change', () => {
      renderPoolGpuClassOptions();
    });
  }
  if (qs('pool-overview-refresh')) {
    qs('pool-overview-refresh').addEventListener('click', () => {
      refreshPoolOverview().catch((error) => {
        eventHooks.setBanner('Pool-Status konnte nicht geladen werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-overview-select')) {
    qs('pool-overview-select').addEventListener('change', (event) => {
      selectPool(event.target.value);
    });
  }
  if (qs('pool-scale-apply')) {
    qs('pool-scale-apply').addEventListener('click', () => {
      scaleSelectedPool().catch((error) => {
        eventHooks.setBanner('Pool konnte nicht skaliert werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-overview-body')) {
    qs('pool-overview-body').addEventListener('click', (event) => {
      const recycleButton = event.target.closest('[data-pool-vm-recycle]');
      if (!recycleButton) {
        return;
      }
      recycleSelectedPoolVm(recycleButton.getAttribute('data-pool-vm-recycle')).catch((error) => {
        eventHooks.setBanner('VM konnte nicht recycelt werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-entitlement-refresh')) {
    qs('pool-entitlement-refresh').addEventListener('click', () => {
      refreshSelectedPoolEntitlements().catch((error) => {
        eventHooks.setBanner('Pool-Entitlements konnten nicht geladen werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-entitlement-user-add')) {
    qs('pool-entitlement-user-add').addEventListener('click', () => {
      mutateSelectedPoolEntitlements('user', 'add').catch((error) => {
        eventHooks.setBanner('Pool-Entitlement konnte nicht gespeichert werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-entitlement-group-add')) {
    qs('pool-entitlement-group-add').addEventListener('click', () => {
      mutateSelectedPoolEntitlements('group', 'add').catch((error) => {
        eventHooks.setBanner('Pool-Entitlement konnte nicht gespeichert werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-entitlement-users')) {
    qs('pool-entitlement-users').addEventListener('click', (event) => {
      const button = event.target.closest('[data-pool-entitlement-remove-user]');
      if (!button) {
        return;
      }
      const value = String(button.getAttribute('data-pool-entitlement-remove-user') || '').trim();
      if (!value) {
        return;
      }
      if (qs('pool-entitlement-user-input')) {
        qs('pool-entitlement-user-input').value = value;
      }
      mutateSelectedPoolEntitlements('user', 'remove').catch((error) => {
        eventHooks.setBanner('Pool-Entitlement konnte nicht entfernt werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pool-entitlement-groups')) {
    qs('pool-entitlement-groups').addEventListener('click', (event) => {
      const button = event.target.closest('[data-pool-entitlement-remove-group]');
      if (!button) {
        return;
      }
      const value = String(button.getAttribute('data-pool-entitlement-remove-group') || '').trim();
      if (!value) {
        return;
      }
      if (qs('pool-entitlement-group-input')) {
        qs('pool-entitlement-group-input').value = value;
      }
      mutateSelectedPoolEntitlements('group', 'remove').catch((error) => {
        eventHooks.setBanner('Pool-Entitlement konnte nicht entfernt werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('pools-list')) {
    qs('pools-list').addEventListener('click', (event) => {
      const focusButton = event.target.closest('[data-pool-focus]');
      if (focusButton) {
        selectPool(focusButton.getAttribute('data-pool-focus'));
        return;
      }
      const deleteButton = event.target.closest('[data-pool-delete]');
      if (deleteButton) {
        deleteSelectedPool(deleteButton.getAttribute('data-pool-delete')).catch((error) => {
          eventHooks.setBanner('Pool konnte nicht geloescht werden: ' + error.message, 'warn');
        });
        return;
      }
      const card = event.target.closest('[data-pool-id]');
      if (!card) {
        return;
      }
      selectPool(card.getAttribute('data-pool-id'));
    });
  }
  if (qs('gaming-metrics-refresh')) {
    qs('gaming-metrics-refresh').addEventListener('click', () => {
      refreshGamingMetricsDashboard(true).catch((error) => {
        eventHooks.setBanner('Gaming-Metriken konnten nicht geladen werden: ' + error.message, 'warn');
      });
    });
  }
  if (qs('session-handover-refresh')) {
    qs('session-handover-refresh').addEventListener('click', () => {
      refreshSessionHandoverDashboard(true).catch((error) => {
        eventHooks.setBanner('Session-Handover-Daten konnten nicht geladen werden: ' + error.message, 'warn');
      });
    });
  }

  if (qs('iam-refresh')) {
    qs('iam-refresh').addEventListener('click', refreshIamData);
  }
  if (qs('iam-user-save')) {
    qs('iam-user-save').addEventListener('click', saveIamUser);
  }
  if (qs('iam-user-new')) {
    qs('iam-user-new').addEventListener('click', () => {
      resetIamUserEditor();
      eventHooks.setBanner('User-Editor zurueckgesetzt.', 'info');
    });
  }
  if (qs('iam-user-delete')) {
    qs('iam-user-delete').addEventListener('click', deleteIamUser);
  }
  if (qs('iam-user-revoke')) {
    qs('iam-user-revoke').addEventListener('click', revokeIamUserSessions);
  }
  if (qs('iam-role-save')) {
    qs('iam-role-save').addEventListener('click', saveIamRole);
  }
  if (qs('iam-role-new')) {
    qs('iam-role-new').addEventListener('click', () => {
      resetIamRoleEditor();
      eventHooks.setBanner('Rollen-Editor zurueckgesetzt.', 'info');
    });
  }
  if (qs('iam-role-delete')) {
    qs('iam-role-delete').addEventListener('click', deleteIamRole);
  }
  if (qs('iam-role-permission-search')) {
    qs('iam-role-permission-search').addEventListener('input', () => {
      const role = state.authRoles.find((entry) => entry.name === state.selectedAuthRole);
      renderPermissionTagEditor(role && Array.isArray(role.permissions) ? role.permissions : []);
    });
  }
  if (qs('iam-role-permissions-grid')) {
    qs('iam-role-permissions-grid').addEventListener('change', (event) => {
      if (event.target && event.target.classList && event.target.classList.contains('perm-tag-cb')) {
        renderIamRoleDiff();
      }
    });
  }

  if (qs('template-library-list')) {
    qs('template-library-list').addEventListener('click', (event) => {
      const useBtn = event.target.closest('[data-template-use]');
      if (useBtn) {
        useSelectedTemplate(useBtn.getAttribute('data-template-use'));
        return;
      }
      const rebuildBtn = event.target.closest('[data-template-rebuild]');
      if (rebuildBtn) {
        rebuildSelectedTemplate(rebuildBtn.getAttribute('data-template-rebuild'));
        return;
      }
      const deleteBtn = event.target.closest('[data-template-delete]');
      if (deleteBtn) {
        deleteSelectedTemplate(deleteBtn.getAttribute('data-template-delete'));
      }
    });
  }
  const iamSessionsReload = document.getElementById('iam-sessions-reload');
  if (iamSessionsReload) {
    iamSessionsReload.addEventListener('click', loadIamSessions);
  }
  if (qs('iam-users-body')) {
    qs('iam-users-body').addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-iam-user]');
      if (row) {
        loadIamUserIntoEditor(row.getAttribute('data-iam-user'));
        renderIamUsers();
      }
    });
  }
  if (qs('iam-roles-body')) {
    qs('iam-roles-body').addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-iam-role]');
      if (row) {
        loadIamRoleIntoEditor(row.getAttribute('data-iam-role'));
        renderIamRoles();
      }
    });
  }

  if (qs('provision-create')) {
    qs('provision-create').addEventListener('click', createProvisionedVm);
  }
  if (qs('provision-reset')) {
    qs('provision-reset').addEventListener('click', () => {
      renderProvisioningWorkspace();
      eventHooks.setBanner('Provisioning-Defaults geladen.', 'info');
    });
  }
  if (qs('provision-modal-create')) {
    qs('provision-modal-create').addEventListener('click', () => {
      createProvisionedVmWithPrefix('prov-modal-');
    });
  }
  if (qs('close-template-builder-modal')) {
    qs('close-template-builder-modal').addEventListener('click', closeTemplateBuilderModal);
  }
  if (qs('template-builder-cancel')) {
    qs('template-builder-cancel').addEventListener('click', closeTemplateBuilderModal);
  }
  if (qs('template-builder-create')) {
    qs('template-builder-create').addEventListener('click', createTemplateFromModal);
  }
  if (qs('template-builder-progress-close')) {
    qs('template-builder-progress-close').addEventListener('click', closeTemplateBuilderProgressModal);
  }
  if (qs('close-provision-modal')) {
    qs('close-provision-modal').addEventListener('click', closeProvisionModal);
  }
  if (qs('provision-modal-cancel')) {
    qs('provision-modal-cancel').addEventListener('click', closeProvisionModal);
  }
  if (qs('provision-modal-reset')) {
    qs('provision-modal-reset').addEventListener('click', () => {
      loadProvisioningCatalog('prov-modal-');
      eventHooks.setBanner('Modal-Defaults geladen.', 'info');
    });
  }
  if (qs('provision-progress-close')) {
    qs('provision-progress-close').addEventListener('click', () => {
      closeProvisionProgressModal(false);
    });
  }
  if (qs('provision-progress-open-vm')) {
    qs('provision-progress-open-vm').addEventListener('click', () => {
      closeProvisionProgressModal(true);
    });
  }
  if (qs('refresh-catalog')) {
    qs('refresh-catalog').addEventListener('click', () => {
      markSessionActivity();
      loadDashboard();
    });
  }
  if (qs('provision-recent-body')) {
    qs('provision-recent-body').addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-vmid]');
      if (row) {
        const vmid = Number(row.getAttribute('data-vmid') || '0');
        if (vmid > 0) {
          eventHooks.loadDetail(vmid);
        }
      }
    });
  }

  if (qs('virtualization-nodes-body')) {
    qs('virtualization-nodes-body').addEventListener('click', (event) => {
      const row = event.target.closest('tr[data-node]');
      if (row) {
        setVirtualizationNodeFilter(row.getAttribute('data-node'));
      }
    });
  }
  if (qs('virtualization-bridge-cards')) {
    qs('virtualization-bridge-cards').addEventListener('click', (event) => {
      const detailBtn = event.target.closest('button[data-virt-bridge-detail]');
      if (detailBtn) {
        openVirtualizationBridgeDetail(String(detailBtn.getAttribute('data-virt-bridge-detail') || '').trim());
        return;
      }
      const ipamBtn = event.target.closest('button[data-virt-bridge-ipam]');
      if (ipamBtn) {
        createIpamZoneForBridge(
          String(ipamBtn.getAttribute('data-virt-bridge-ipam') || '').trim(),
          String(ipamBtn.getAttribute('data-virt-bridge-cidr') || '').trim()
        );
        return;
      }
      const filterBtn = event.target.closest('button[data-virt-node-filter]');
      if (filterBtn) {
        setVirtualizationNodeFilter(String(filterBtn.getAttribute('data-virt-node-filter') || '').trim());
        return;
      }
      const card = event.target.closest('[data-node]');
      if (card) {
        setVirtualizationNodeFilter(card.getAttribute('data-node'));
      }
    });
  }
  if (qs('virtualization-gpu-cards')) {
    qs('virtualization-gpu-cards').addEventListener('click', (event) => {
      const assignBtn = event.target.closest('button[data-gpu-assign]');
      if (assignBtn) {
        assignGpuToVm(assignBtn.getAttribute('data-gpu-pci'));
        return;
      }
      const releaseBtn = event.target.closest('button[data-gpu-release]');
      if (releaseBtn) {
        releaseGpuFromVm(releaseBtn.getAttribute('data-gpu-pci'));
        return;
      }
      const detailBtn = event.target.closest('button[data-virt-node-detail]');
      if (detailBtn) {
        openVirtualizationNodeDetail(String(detailBtn.getAttribute('data-virt-node-detail') || '').trim());
        return;
      }
      const card = event.target.closest('[data-node]');
      if (card) {
        setVirtualizationNodeFilter(card.getAttribute('data-node'));
      }
    });
  }
  if (qs('clear-virt-node-filter')) {
    qs('clear-virt-node-filter').addEventListener('click', () => {
      setVirtualizationNodeFilter('');
    });
  }
  if (qs('nodes-grid')) {
    qs('nodes-grid').addEventListener('click', (event) => {
      const detailBtn = event.target.closest('button[data-virt-node-detail]');
      if (detailBtn) {
        openVirtualizationNodeDetail(String(detailBtn.getAttribute('data-virt-node-detail') || '').trim());
        return;
      }
      const filterBtn = event.target.closest('button[data-virt-node-filter]');
      if (filterBtn) {
        setVirtualizationNodeFilter(String(filterBtn.getAttribute('data-virt-node-filter') || '').trim());
        return;
      }
      const preflightBtn = event.target.closest('button[data-virt-local-preflight]');
      if (preflightBtn) {
        const nodeName = String(preflightBtn.getAttribute('data-virt-local-preflight') || '').trim();
        preflightBtn.disabled = true;
        import('./api.js').then(({ request: req }) => req('/cluster/local-preflight')).then((data) => {
          const checks = Array.isArray(data && data.checks) ? data.checks : [];
          const lines = checks.map((c) => String(c.status || '?').toUpperCase() + ' ' + String(c.name || '') + ': ' + String(c.message || '')).join('\n');
          import('./error-handler.js').then(({ showInfo }) => showInfo('Preflight ' + nodeName + ': ' + (lines || 'Keine Daten.')));
        }).catch((err) => {
          import('./error-handler.js').then(({ showError }) => showError(err, { context: 'Preflight fehlgeschlagen' }));
        }).finally(() => {
          preflightBtn.disabled = false;
        });
      }
    });
  }
  if (qs('vgpu-refresh')) {
    qs('vgpu-refresh').addEventListener('click', () => {
      loadMdevTypes();
    });
  }
  if (qs('vgpu-types-body')) {
    qs('vgpu-types-body').addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-mdev-create]');
      if (btn) {
        createMdevInstance(btn.getAttribute('data-mdev-pci'), btn.getAttribute('data-mdev-type'));
      }
    });
  }
  if (qs('vgpu-instances-body')) {
    qs('vgpu-instances-body').addEventListener('click', (event) => {
      const assignBtn = event.target.closest('button[data-mdev-assign]');
      if (assignBtn) {
        assignMdevToVm(assignBtn.getAttribute('data-mdev-uuid'));
        return;
      }
      const deleteBtn = event.target.closest('button[data-mdev-delete]');
      if (deleteBtn) {
        deleteMdevInstance(deleteBtn.getAttribute('data-mdev-uuid'));
      }
    });
  }
  if (qs('sriov-refresh')) {
    qs('sriov-refresh').addEventListener('click', () => {
      loadSriovDevices();
    });
  }
  if (qs('sriov-devices-body')) {
    qs('sriov-devices-body').addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-sriov-set]');
      if (btn) {
        setSriovVfCount(btn.getAttribute('data-sriov-pci'), btn.getAttribute('data-sriov-total'));
        return;
      }
      const vfsBtn = event.target.closest('button[data-sriov-vfs]');
      if (vfsBtn) {
        loadSriovVfs(vfsBtn.getAttribute('data-sriov-pci'));
      }
    });
  }
  if (qs('storage-body')) {
    qs('storage-body').addEventListener('click', (event) => {
      const detailTrigger = event.target.closest('button[data-storage-detail]');
      if (detailTrigger) {
        openStoragePoolDetail(String(detailTrigger.getAttribute('data-storage-detail') || '').trim());
        return;
      }
      const trigger = event.target.closest('button[data-storage-quota-set]');
      if (!trigger) {
        return;
      }
      const poolName = String(trigger.getAttribute('data-storage-pool') || '').trim();
      const quotaBytes = Number(trigger.getAttribute('data-storage-quota-bytes') || '0');
      setStoragePoolQuota(poolName, quotaBytes);
    });
  }
  if (qs('virtualization-storage-cards')) {
    qs('virtualization-storage-cards').addEventListener('click', (event) => {
      const detailBtn = event.target.closest('button[data-storage-detail]');
      if (detailBtn) {
        openStoragePoolDetail(String(detailBtn.getAttribute('data-storage-detail') || '').trim());
        return;
      }
      const quotaBtn = event.target.closest('button[data-storage-quota-set]');
      if (quotaBtn) {
        const poolName = String(quotaBtn.getAttribute('data-storage-pool') || '').trim();
        const quotaBytes = Number(quotaBtn.getAttribute('data-storage-quota-bytes') || '0');
        setStoragePoolQuota(poolName, quotaBytes);
        return;
      }
      const healthBtn = event.target.closest('button[data-storage-health-node]');
      if (healthBtn) {
        openVirtualizationNodeDetail(String(healthBtn.getAttribute('data-storage-health-node') || '').trim());
      }
    });
  }
  if (qs('virt-inspector-load')) {
    qs('virt-inspector-load').addEventListener('click', () => {
      loadVirtualizationInspector(String(qs('virt-inspector-vmid') ? qs('virt-inspector-vmid').value : ''));
    });
  }
  if (qs('virt-inspector-vmid')) {
    qs('virt-inspector-vmid').addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        loadVirtualizationInspector(String(event.target.value || ''));
      }
    });
  }
  if (qs('virt-inspector-use-selected')) {
    qs('virt-inspector-use-selected').addEventListener('click', () => {
      if (!state.selectedVmid) {
        eventHooks.setBanner('Keine VM aus Inventar ausgewaehlt.', 'warn');
        return;
      }
      if (qs('virt-inspector-vmid')) {
        qs('virt-inspector-vmid').value = String(state.selectedVmid);
      }
      loadVirtualizationInspector(state.selectedVmid);
    });
  }
  if (qs('virt-inspector-use-last')) {
    qs('virt-inspector-use-last').addEventListener('click', () => {
      const lastVmid = Number((state.virtualizationInspector || {}).lastVmid || 0);
      if (!Number.isFinite(lastVmid) || lastVmid <= 0) {
        eventHooks.setBanner('Noch keine zuletzt geladene VM vorhanden.', 'warn');
        return;
      }
      if (qs('virt-inspector-vmid')) {
        qs('virt-inspector-vmid').value = String(lastVmid);
      }
      loadVirtualizationInspector(lastVmid);
    });
  }
  if (qs('virt-inspector-recent')) {
    qs('virt-inspector-recent').addEventListener('click', (event) => {
      const btn = event.target.closest('button[data-virt-inspector-recent]');
      if (!btn) {
        return;
      }
      const vmid = Number(btn.getAttribute('data-virt-inspector-recent') || '0');
      if (!Number.isFinite(vmid) || vmid <= 0) {
        return;
      }
      if (qs('virt-inspector-vmid')) {
        qs('virt-inspector-vmid').value = String(vmid);
      }
      loadVirtualizationInspector(vmid);
    });
  }

  ['click', 'keydown', 'mousemove', 'touchstart'].forEach((eventName) => {
    document.addEventListener(eventName, markSessionActivity, { passive: true });
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      return;
    }
    updateConnectButton();
  });
}

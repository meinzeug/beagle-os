import { state } from './state.js';
import { blobRequest, isSafeExternalUrl, postJson, request, runSingleFlight } from './api.js';

const actionHooks = {
  setBanner() {},
  addToActivityLog() {},
  runVmPowerAction() {
    return Promise.resolve();
  },
  requestConfirm() {
    return Promise.resolve(true);
  },
  loadDetail() {
    return Promise.resolve();
  },
  loadDashboard() {
    return Promise.resolve();
  },
  openTemplateBuilderModal() {
    return null;
  },
  openMigrateModal() {
    return Promise.resolve();
  },
};

export function configureActions(nextHooks) {
  Object.assign(actionHooks, nextHooks || {});
}

export function executeAction(action, sourceButton) {
  const vmid = state.selectedVmid;
  if (!vmid) {
    return;
  }
  const selectedVm = Array.isArray(state.inventory)
    ? state.inventory.find((vm) => Number((vm && vm.vmid) || 0) === Number(vmid))
    : null;
  const selectedProfile = selectedVm && selectedVm.profile ? selectedVm.profile : (selectedVm || null);
  if (action === 'refresh-detail') {
    actionHooks.loadDetail(vmid);
    return;
  }
  if (action === 'open-template-builder') {
    actionHooks.openTemplateBuilderModal(vmid);
    return;
  }
  if (action === 'download-linux') {
    blobRequest('/vms/' + vmid + '/installer.sh', 'pve-thin-client-usb-installer-vm-' + vmid + '.sh').catch((error) => {
      actionHooks.setBanner('Linux-Installer Download failed:' + error.message, 'warn');
    });
    return;
  }
  if (action === 'download-windows') {
    blobRequest('/vms/' + vmid + '/installer.ps1', 'pve-thin-client-usb-installer-vm-' + vmid + '.ps1').catch((error) => {
      actionHooks.setBanner('Windows-Installer Download failed:' + error.message, 'warn');
    });
    return;
  }
  if (action === 'download-live-usb') {
    blobRequest('/vms/' + vmid + '/live-usb.sh', 'pve-thin-client-live-usb-vm-' + vmid + '.sh').catch((error) => {
      actionHooks.setBanner('Live-USB Download failed:' + error.message, 'warn');
    });
    return;
  }
  if (action === 'download-live-usb-windows') {
    blobRequest('/vms/' + vmid + '/live-usb.ps1', 'pve-thin-client-live-usb-vm-' + vmid + '.ps1').catch((error) => {
      actionHooks.setBanner('Windows Live-USB Download failed:' + error.message, 'warn');
    });
    return;
  }
  if (action === 'usb-refresh') {
    runSingleFlight('vm-action:' + vmid + ':usb-refresh', () => {
      actionHooks.setBanner('Refreshing USB inventory for VM ' + vmid + '...', 'info');
      return postJson('/vms/' + vmid + '/usb/refresh', {}).then(() => {
        return actionHooks.loadDetail(vmid);
      }).catch((error) => {
        actionHooks.setBanner('USB-Refresh failed:' + error.message, 'warn');
      });
    });
    return;
  }
  if (action === 'usb-attach') {
    runSingleFlight('vm-action:' + vmid + ':usb-attach', () => {
      actionHooks.setBanner('Attaching USB device to VM ' + vmid + '...', 'info');
      return postJson('/vms/' + vmid + '/usb/attach', {
        busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || ''
      }).then(() => {
        return actionHooks.loadDetail(vmid);
      }).catch((error) => {
        actionHooks.setBanner('USB-Attach failed:' + error.message, 'warn');
      });
    });
    return;
  }
  if (action === 'usb-detach') {
    runSingleFlight('vm-action:' + vmid + ':usb-detach', () => {
      actionHooks.setBanner('Detaching USB device from VM ' + vmid + '...', 'info');
      return postJson('/vms/' + vmid + '/usb/detach', {
        busid: sourceButton && sourceButton.getAttribute('data-usb-busid') || '',
        port: sourceButton && sourceButton.getAttribute('data-usb-port') || ''
      }).then(() => {
        return actionHooks.loadDetail(vmid);
      }).catch((error) => {
        actionHooks.setBanner('USB-Detach failed:' + error.message, 'warn');
      });
    });
    return;
  }
  if (action === 'installer-prep') {
    runSingleFlight('vm-action:' + vmid + ':installer-prep', () => {
      actionHooks.setBanner('Preparing installer for VM ' + vmid + '...', 'info');
      return postJson('/vms/' + vmid + '/installer-prep', {}).then(() => {
        actionHooks.addToActivityLog('installer-prep', vmid, 'ok', 'Installer vorbereitet');
        return actionHooks.loadDetail(vmid);
      }).catch((error) => {
        actionHooks.addToActivityLog('installer-prep', vmid, 'warn', error.message);
        actionHooks.setBanner('Installer preparation failed: ' + error.message, 'warn');
      });
    });
    return;
  }
  if (action === 'beagle-stream-server-ui') {
    postJson('/vms/' + vmid + '/beagle-stream-server-access', {}).then((payload) => {
      const url = payload && payload.beagle_stream_server_access ? payload.beagle_stream_server_access.url : '';
      if (!url) {
        throw new Error('No Beagle Stream Server URL received');
      }
      if (!isSafeExternalUrl(url)) {
        throw new Error('Unsafe Beagle Stream Server URL blocked');
      }
      window.open(url, '_blank', 'noopener');
    }).catch((error) => {
      actionHooks.setBanner('Beagle Stream Server access failed: ' + error.message, 'warn');
    });
    return;
  }
  if (action === 'novnc-ui') {
    request('/vms/' + vmid + '/novnc-access', { __suppressAuthLock: true }).then((payload) => {
      const access = payload && payload.novnc_access ? payload.novnc_access : {};
      const url = String(access.url || '').trim();
      if (!access.available) {
        throw new Error(String(access.reason || 'noVNC ist fuer diese VM nicht verfuegbar.'));
      }
      if (!url) {
        throw new Error('Keine noVNC URL erhalten.');
      }
      if (!isSafeExternalUrl(url)) {
        throw new Error('Unsichere noVNC URL blockiert.');
      }
      window.open(url, '_blank', 'noopener');
    }).catch((error) => {
      actionHooks.setBanner('noVNC Zugriff fehlgeschlagen: ' + error.message, 'warn');
    });
    return;
  }
  if (action.indexOf('update-') === 0) {
    const operation = action.replace('update-', '');
    runSingleFlight('vm-action:' + vmid + ':update:' + operation, () => {
      actionHooks.setBanner('Update-Aktion ' + action + ' fuer VM ' + vmid + ' wird gestartet ...', 'info');
      return postJson('/vms/' + vmid + '/update/' + operation, {}).then(() => {
        actionHooks.setBanner('Update-Aktion ' + action + ' gestartet.', 'ok');
        return actionHooks.loadDetail(vmid);
      }).catch((error) => {
        actionHooks.setBanner('Update-Aktion fehlgeschlagen: ' + error.message, 'warn');
      });
    });
    return;
  }
  if (action === 'vm-start' || action === 'vm-stop' || action === 'vm-reboot') {
    const powerAction = action === 'vm-start' ? 'start' : action === 'vm-stop' ? 'stop' : 'reboot';
    actionHooks.runVmPowerAction(vmid, powerAction);
    return;
  }
  if (action === 'vm-migrate') {
    const currentNode = String((selectedProfile && selectedProfile.node) || '').trim();

    const buildTargets = (nodesArr) => (nodesArr || [])
      .map((node) => ({
        name: String((node && (node.name || node.node)) || '').trim(),
        status: String((node && node.status) || '').trim().toLowerCase(),
        vm_count: node && node.vm_count,
        maxmem: node && node.maxmem,
        cpu: node && node.cpu,
      }))
      .filter((node) => node.name);

    const openModal = (targets) => {
      if (!targets.some((n) => n.name !== currentNode && n.status === 'online')) {
        actionHooks.setBanner('Keine online Migration-Zielknoten verfuegbar.', 'warn');
        return;
      }
      actionHooks.openMigrateModal({
        vmid: vmid,
        vmName: selectedProfile && selectedProfile.name,
        currentNode: currentNode,
        nodes: targets,
        onMigrate(targetNode, live, copyStorage) {
          return runSingleFlight('vm-action:' + vmid + ':migrate:' + targetNode, () => {
            return postJson('/vms/' + vmid + '/migrate', {
              target_node: targetNode,
              live: Boolean(live),
              copy_storage: Boolean(copyStorage),
            }).then(() => {
              actionHooks.addToActivityLog('vm-migrate', vmid, 'ok', 'VM nach ' + targetNode + ' migriert');
              return actionHooks.loadDashboard({ force: true }).then(() => actionHooks.loadDetail(vmid));
            }).then(() => {
              actionHooks.setBanner('VM ' + vmid + ' wurde nach ' + targetNode + ' verschoben.', 'ok');
            }).catch((error) => {
              actionHooks.addToActivityLog('vm-migrate', vmid, 'warn', error.message);
              throw error;
            });
          });
        },
      });
    };

    if (state.virtualizationOverview && Array.isArray(state.virtualizationOverview.nodes)) {
      openModal(buildTargets(state.virtualizationOverview.nodes));
    } else {
      request('/virtualization/overview').then((data) => {
        const nodes = data && Array.isArray(data.nodes) ? data.nodes : [];
        openModal(buildTargets(nodes));
      }).catch(() => {
        actionHooks.setBanner('Cluster-Status konnte nicht geladen werden.', 'warn');
      });
    }
    return;
  }
  if (action === 'vm-delete') {
    actionHooks.requestConfirm({
      title: 'VM ' + vmid + ' loeschen?',
      message: 'Diese Aktion kann nicht rueckgaengig gemacht werden. Die VM wird endgueltig entfernt.',
      confirmLabel: 'Endgueltig loeschen',
      danger: true
    }).then((ok) => {
      if (!ok) {
        return;
      }
      runSingleFlight('vm-action:' + vmid + ':delete', () => {
        actionHooks.setBanner('Loesche VM ' + vmid + ' ...', 'info');
        return request('/provisioning/vms/' + vmid, { method: 'DELETE' }).then(() => {
          actionHooks.addToActivityLog('vm-delete', vmid, 'ok', 'VM geloescht');
          state.selectedVmids = state.selectedVmids.filter((item) => Number(item) !== Number(vmid));
          delete state.detailCache[vmid];
          state.selectedVmid = null;
          return actionHooks.loadDashboard({ force: true });
        }).then(() => {
          actionHooks.setBanner('VM ' + vmid + ' geloescht.', 'ok');
        }).catch((error) => {
          actionHooks.addToActivityLog('vm-delete', vmid, 'warn', error.message);
          actionHooks.setBanner('VM konnte nicht geloescht werden: ' + error.message, 'warn');
        });
      });
    });
    return;
  }
  runSingleFlight('vm-action:' + vmid + ':generic:' + action, () => {
    actionHooks.setBanner('Queuing action ' + action + ' for VM ' + vmid + '...', 'info');
    return postJson('/vms/' + vmid + '/actions', { action }).then(() => {
      actionHooks.addToActivityLog(action, vmid, 'ok', 'Action queued');
      actionHooks.setBanner('Action ' + action + ' queued for VM ' + vmid + '.', 'ok');
      return actionHooks.loadDetail(vmid);
    }).catch((error) => {
      actionHooks.addToActivityLog(action, vmid, 'warn', error.message);
      actionHooks.setBanner('Action failed: ' + error.message, 'warn');
    });
  });
}

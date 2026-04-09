(function() {
  "use strict";

  var renderHelpers = window.BeagleUiRenderHelpers;

  if (!renderHelpers) {
    throw new Error("BeagleUiRenderHelpers must be loaded before BeagleUiProfileModal");
  }

  function fallbackCopyText(showError, showToast, text, successMessage) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    try {
      document.execCommand("copy");
      showToast(successMessage || "In die Zwischenablage kopiert.");
    } catch (_error) {
      showError("Kopieren fehlgeschlagen.");
    } finally {
      textarea.remove();
    }
  }

  function copyText(showError, showToast, text, successMessage) {
    var value = String(text || "");
    if (!value) {
      showError("Keine Daten zum Kopieren vorhanden.");
      return;
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).then(function() {
        showToast(successMessage || "In die Zwischenablage kopiert.");
      }).catch(function() {
        fallbackCopyText(showError, showToast, value, successMessage);
      });
      return;
    }

    fallbackCopyText(showError, showToast, value, successMessage);
  }

  function maskSecret(value) {
    if (!value) {
      return "nicht gesetzt";
    }
    if (value.length <= 4) {
      return "****";
    }
    return value.slice(0, 2) + "***" + value.slice(-2);
  }

  function formatActionState(ok) {
    if (ok === true) {
      return "ok";
    }
    if (ok === false) {
      return "error";
    }
    return "pending";
  }

  function buildEndpointEnv(profile) {
    var endpointProfileName = profile.expectedProfileName || ("vm-" + profile.vmid);
    var lines = [
      "PVE_THIN_CLIENT_MODE=\"MOONLIGHT\"",
      "PVE_THIN_CLIENT_PROFILE_NAME=\"" + endpointProfileName + "\"",
      "PVE_THIN_CLIENT_AUTOSTART=\"1\"",
      "PVE_THIN_CLIENT_PROXMOX_HOST=\"" + (profile.proxmoxHost || window.location.hostname) + "\"",
      "PVE_THIN_CLIENT_PROXMOX_PORT=\"8006\"",
      "PVE_THIN_CLIENT_PROXMOX_NODE=\"" + (profile.node || "") + "\"",
      "PVE_THIN_CLIENT_PROXMOX_VMID=\"" + String(profile.vmid || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_URL=\"" + (profile.managerUrl || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY=\"" + (profile.managerPinnedPubkey || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_HOST=\"" + (profile.streamHost || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_PORT=\"" + (profile.moonlightPort || "") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_APP=\"" + (profile.app || "Desktop") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_RESOLUTION=\"" + (profile.resolution || "auto") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_FPS=\"" + (profile.fps || "60") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_BITRATE=\"" + (profile.bitrate || "20000") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_VIDEO_CODEC=\"" + (profile.codec || "H.264") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_VIDEO_DECODER=\"" + (profile.decoder || "auto") + "\"",
      "PVE_THIN_CLIENT_MOONLIGHT_AUDIO_CONFIG=\"" + (profile.audio || "stereo") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_API_URL=\"" + (profile.sunshineApiUrl || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_USERNAME=\"" + (profile.sunshineUsername || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_PASSWORD=\"" + (profile.sunshinePassword || "") + "\"",
      "PVE_THIN_CLIENT_SUNSHINE_PIN=\"" + (profile.sunshinePin || "") + "\""
    ];
    return lines.join("\n") + "\n";
  }

  function buildNotes(profile) {
    var notes = [];
    if (!profile.streamHost) {
      notes.push("Kein Moonlight-/Sunshine-Ziel in der VM-Metadatenbeschreibung gefunden.");
    }
    if (!profile.sunshineApiUrl) {
      notes.push("Keine Sunshine API URL gesetzt. Pairing und Healthchecks koennen nicht vorab validiert werden.");
    }
    if (!profile.sunshinePassword) {
      notes.push("Kein Sunshine-Passwort hinterlegt. Fuer direkte API-Aktionen ist dann ein vorregistriertes Zertifikat oder manuelles Pairing noetig.");
    }
    if (!profile.guestIp) {
      notes.push("Keine Guest-Agent-IPv4 erkannt. Beagle kann dann nur mit Metadaten arbeiten.");
    }
    if (!notes.length) {
      notes.push("VM-Profil ist vollstaendig genug fuer einen vorkonfigurierten Beagle-Endpoint mit Moonlight-Autostart.");
    }
    if (profile.assignedTarget) {
      notes.push("Endpoint ist auf Ziel-VM " + profile.assignedTarget.name + " (#" + profile.assignedTarget.vmid + ") zugewiesen.");
    }
    if (profile.appliedPolicy && profile.appliedPolicy.name) {
      notes.push("Manager-Policy aktiv: " + profile.appliedPolicy.name + ".");
    }
    if (profile.compliance && profile.compliance.status === "drifted") {
      notes.push("Endpoint driftet vom gewuenschten Profil ab (" + String(profile.compliance.drift_count || 0) + " Abweichungen).");
    }
    if (profile.compliance && profile.compliance.status === "degraded") {
      notes.push("Endpoint ist konfigurationsgleich, aber betrieblich degradiert (" + String(profile.compliance.alert_count || 0) + " Warnungen).");
    }
    if (Number(profile.pendingActionCount || 0) > 0) {
      notes.push("Fuer diesen Endpoint warten " + String(profile.pendingActionCount) + " Beagle-Aktion(en) auf Ausfuehrung.");
    }
    if (profile.lastAction && profile.lastAction.action) {
      notes.push("Letzte Endpoint-Aktion: " + profile.lastAction.action + " (" + formatActionState(profile.lastAction.ok) + ").");
    }
    if (profile.lastAction && profile.lastAction.stored_artifact_path) {
      notes.push("Diagnoseartefakt ist zentral auf dem Beagle-Manager gespeichert.");
    }
    if (profile.installerPrep && profile.installerPrep.status === "ready") {
      notes.push("Installer-Vorbereitung ist bereits abgeschlossen. Der USB-Installer ist sofort freigegeben.");
    }
    return notes;
  }

  async function prepareInstallerDownload(runtime, profile, overlay, artifactKey, actionName, loadingLabel, successMessage, filenameOverride) {
    var downloadButton = overlay.querySelector('[data-beagle-action="' + actionName + '"]');
    var originalText = downloadButton ? downloadButton.textContent : "USB Installer";
    var state = null;
    var attempt;
    var artifactUrl = profile && profile[artifactKey] ? String(profile[artifactKey]) : "";
    var filename = filenameOverride || (artifactKey === "installerWindowsUrl"
      ? ("pve-thin-client-usb-installer-vm-" + profile.vmid + ".ps1")
      : ("pve-thin-client-usb-installer-vm-" + profile.vmid + ".sh"));
    var requiresProtectedDownload = /^\/beagle-api\//.test(artifactUrl);

    if (profile && profile.installerTargetEligible === false) {
      runtime.applyInstallerPrepState(overlay, profile.installerPrep || {});
      return;
    }

    if (downloadButton) {
      downloadButton.disabled = true;
      downloadButton.textContent = loadingLabel;
    }

    try {
      state = await runtime.apiGetInstallerPrep(profile.vmid).catch(function() {
        return profile.installerPrep || null;
      });
      if (state) {
        runtime.applyInstallerPrepState(overlay, state);
      }
      if (state && String(state && state.status || "").toLowerCase() === "ready") {
        if (requiresProtectedDownload) {
          await runtime.downloadProtectedFile(runtime.normalizeBeagleApiPath(profile[artifactKey]), filename);
        } else {
          runtime.triggerDownload(profile[artifactKey]);
        }
        runtime.showToast(successMessage);
        return;
      }
      if (!runtime.shouldReuseInstallerPrepState(state)) {
        state = await runtime.apiStartInstallerPrep(profile.vmid);
        runtime.applyInstallerPrepState(overlay, state);
      }
      for (attempt = 0; attempt < 180; attempt += 1) {
        if (String(state && state.status || "").toLowerCase() === "ready") {
          if (requiresProtectedDownload) {
            await runtime.downloadProtectedFile(runtime.normalizeBeagleApiPath(profile[artifactKey]), filename);
          } else {
            runtime.triggerDownload(profile[artifactKey]);
          }
          runtime.showToast(successMessage);
          return;
        }
        if (String(state && state.status || "").toLowerCase() === "error") {
          throw new Error(String(state && state.message || "Installer-Vorbereitung fehlgeschlagen."));
        }
        await runtime.sleep(2000);
        state = await runtime.apiGetInstallerPrep(profile.vmid);
        runtime.applyInstallerPrepState(overlay, state);
      }
      throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
    } catch (error) {
      runtime.applyInstallerPrepState(overlay, {
        status: "error",
        phase: "failed",
        progress: 100,
        message: error && error.message ? error.message : "Installer-Vorbereitung fehlgeschlagen.",
        sunshine_status: state && state.sunshine_status || null
      });
      runtime.showError("Installer konnte nicht vorbereitet werden: " + (error && error.message ? error.message : error));
    } finally {
      if (downloadButton) {
        downloadButton.disabled = false;
        downloadButton.textContent = originalText;
      }
    }
  }

  function renderProfileModal(options) {
    var profile = options.profile;
    var overlayId = options.overlayId;
    var removeOverlay = options.removeOverlay;
    var withNoCache = options.withNoCache;
    var webUiUrlWithToken = options.webUiUrlWithToken;
    var openUrl = options.openUrl;
    var showError = options.showError;
    var showToast = options.showToast;
    var showProfileModal = options.showProfileModal;
    var showUbuntuBeagleCreateModal = options.showUbuntuBeagleCreateModal;
    var apiCreateSunshineAccess = options.apiCreateSunshineAccess;
    var platformService = options.platformService;
    var apiGetInstallerPrep = options.apiGetInstallerPrep;
    var apiStartInstallerPrep = options.apiStartInstallerPrep;
    var downloadProtectedFile = options.downloadProtectedFile;
    var normalizeBeagleApiPath = options.normalizeBeagleApiPath;
    var triggerDownload = options.triggerDownload;
    var sleep = options.sleep;
    var syncInstallerButtons = options.syncInstallerButtons;
    var applyInstallerPrepState = options.applyInstallerPrepState;
    var installerTargetState = options.installerTargetState;
    var shouldReuseInstallerPrepState = options.shouldReuseInstallerPrepState;
    var overlay = document.createElement("div");
    var usbState = profile.usbState || {};
    var usbDevices = Array.isArray(usbState.devices) ? usbState.devices : [];
    var usbAttached = Array.isArray(usbState.attached) ? usbState.attached : [];
    var notesHtml = profile.notes.map(function(note) {
      return "<li>" + renderHelpers.escapeHtml(note) + "</li>";
    }).join("");
    var installerPrep = profile.installerPrep || {
      status: "idle",
      phase: "inspect",
      progress: 0,
      message: "Download startet zuerst die Sunshine-Pruefung und die Stream-Vorbereitung fuer diese VM.",
      sunshine_status: { binary: false, service: false, process: false }
    };
    var profileJson = JSON.stringify({
      vmid: profile.vmid,
      node: profile.node,
      name: profile.name,
      status: profile.status,
      stream_host: profile.streamHost,
      sunshine_api_url: profile.sunshineApiUrl,
      sunshine_username: profile.sunshineUsername,
      sunshine_password_configured: Boolean(profile.sunshinePassword),
      sunshine_pin: profile.sunshinePin,
      guest_user: profile.guestUser,
      desktop_id: profile.desktopId,
      desktop_label: profile.desktopLabel,
      desktop_session: profile.desktopSession,
      package_presets: profile.packagePresets,
      extra_packages: profile.extraPackages,
      software_packages: profile.softwarePackages,
      identity_locale: profile.identityLocale,
      identity_keymap: profile.identityKeymap,
      moonlight_app: profile.app,
      moonlight_resolution: profile.resolution,
      moonlight_fps: profile.fps,
      moonlight_bitrate: profile.bitrate,
      moonlight_video_codec: profile.codec,
      moonlight_video_decoder: profile.decoder,
      moonlight_audio_config: profile.audio,
      manager_url: profile.managerUrl,
      installer_url: profile.installerUrl,
      live_usb_url: profile.liveUsbUrl,
      installer_windows_url: profile.installerWindowsUrl,
      installer_iso_url: profile.installerIsoUrl,
      control_plane_health_url: profile.controlPlaneHealthUrl,
      assigned_target: profile.assignedTarget,
      assignment_source: profile.assignmentSource,
      applied_policy: profile.appliedPolicy,
      expected_profile_name: profile.expectedProfileName,
      endpoint_summary: profile.endpointSummary,
      compliance: profile.compliance,
      last_action: profile.lastAction,
      pending_action_count: profile.pendingActionCount,
      installer_prep: installerPrep,
      installer_target_eligible: profile.installerTargetEligible,
      installer_target_message: profile.installerTargetMessage,
      usb_state: usbState
    }, null, 2);
    var usbDevicesHtml = usbDevices.length ? usbDevices.map(function(device) {
      var busid = String(device.busid || "");
      return '<div class="beagle-kv-row"><strong>' + renderHelpers.escapeHtml(busid) + '</strong><span>' + renderHelpers.escapeHtml(device.description || "") + '</span><span>' +
        '<button type="button" class="beagle-mini-btn" data-beagle-action="usb-attach" data-beagle-usb-busid="' + renderHelpers.escapeHtml(busid) + '">Attach</button>' +
        (device.bound ? ' <span class="beagle-muted">exported</span>' : '') +
      '</span></div>';
    }).join("") : '<div class="beagle-kv-row"><strong>USB</strong><span class="beagle-muted">Keine exportierbaren USB-Geraete gemeldet.</span></div>';
    var usbAttachedHtml = usbAttached.length ? usbAttached.map(function(item) {
      var busid = String(item.busid || "");
      var port = String(item.port || "");
      return '<div class="beagle-kv-row"><strong>Port ' + renderHelpers.escapeHtml(port) + '</strong><span>' + renderHelpers.escapeHtml(busid || item.device || "") + '</span><span>' +
        '<button type="button" class="beagle-mini-btn" data-beagle-action="usb-detach" data-beagle-usb-busid="' + renderHelpers.escapeHtml(busid) + '" data-beagle-usb-port="' + renderHelpers.escapeHtml(port) + '">Detach</button>' +
      '</span></div>';
    }).join("") : '<div class="beagle-kv-row"><strong>USB</strong><span class="beagle-muted">Keine USB-Geraete in der VM angehaengt.</span></div>';
    var runtime = {
      apiGetInstallerPrep: apiGetInstallerPrep,
      apiStartInstallerPrep: apiStartInstallerPrep,
      applyInstallerPrepState: applyInstallerPrepState,
      downloadProtectedFile: downloadProtectedFile,
      normalizeBeagleApiPath: normalizeBeagleApiPath,
      shouldReuseInstallerPrepState: shouldReuseInstallerPrepState,
      showError: showError,
      showToast: showToast,
      sleep: sleep,
      triggerDownload: triggerDownload
    };

    overlay.id = overlayId;
    overlay.innerHTML = '' +
      '<div class="beagle-modal" role="dialog" aria-modal="true" aria-label="Beagle OS Profil">' +
      '  <div class="beagle-header">' +
      '    <div>' +
      '      <h2 class="beagle-title">Beagle Profil fuer VM ' + renderHelpers.escapeHtml(profile.name) + ' (#' + String(profile.vmid) + ')</h2>' +
      '      <p class="beagle-subtitle">Moonlight-Endpunkt, Sunshine-Ziel und Proxmox-Bereitstellung in einer Sicht.</p>' +
      '    </div>' +
      '    <button type="button" class="beagle-close" aria-label="Schliessen">×</button>' +
      '  </div>' +
      '  <div class="beagle-body">' +
      '    <div class="beagle-banner ' + (profile.streamHost ? 'info' : 'warn') + '">' + renderHelpers.escapeHtml(profile.streamHost ? 'Streaming-Ziel erkannt: ' + profile.streamHost : 'Streaming-Ziel fehlt in den VM-Metadaten.') + '</div>' +
      '    <div class="beagle-banner ' + installerTargetState(profile, installerPrep).bannerClass + '" data-beagle-download-banner><strong data-beagle-download-state>' + renderHelpers.escapeHtml(installerTargetState(profile, installerPrep).label) + '</strong>: <span data-beagle-download-message>' + renderHelpers.escapeHtml(installerTargetState(profile, installerPrep).message) + '</span></div>' +
      '    <div class="beagle-actions">' +
      (String(profile.beagleRole || "").toLowerCase() === 'desktop' ? '      <button type="button" class="beagle-btn primary" data-beagle-action="edit-desktop">Desktop bearbeiten</button>' : '') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn primary" data-beagle-action="download">USB Installer Skript</button>') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-live">Live USB Skript</button>') +
      (profile.installerTargetEligible === false ? '' : '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-windows">Windows USB Installer</button>') +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="download-iso">ISO Download</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-web-ui">Open Web UI</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="copy-json">Profil JSON kopieren</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="copy-env">Endpoint Env kopieren</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-sunshine">Sunshine Web UI</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="usb-refresh">USB Refresh</button>' +
      '      <button type="button" class="beagle-btn secondary" data-beagle-action="open-health">Control Plane Status</button>' +
      '    </div>' +
      '    <div class="beagle-grid">' +
      '      <section class="beagle-card"><h3>VM</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Name', renderHelpers.escapeHtml(profile.name)) +
                renderHelpers.kvRow('VMID', renderHelpers.escapeHtml(String(profile.vmid))) +
                renderHelpers.kvRow('Node', renderHelpers.escapeHtml(profile.node)) +
                renderHelpers.kvRow('Status', renderHelpers.escapeHtml(profile.status)) +
                renderHelpers.kvRow('Guest IP', renderHelpers.escapeHtml(profile.guestIp || '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Desktop</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Desktop', renderHelpers.escapeHtml(profile.desktopLabel || profile.desktopId || '')) +
                renderHelpers.kvRow('Session', renderHelpers.escapeHtml(profile.desktopSession || '')) +
                renderHelpers.kvRow('Gast-User', renderHelpers.escapeHtml(profile.guestUser || '')) +
                renderHelpers.kvRow('Locale', renderHelpers.escapeHtml(profile.identityLocale || '')) +
                renderHelpers.kvRow('Keymap', renderHelpers.escapeHtml(profile.identityKeymap || '')) +
                renderHelpers.kvRow('Paket-Presets', renderHelpers.escapeHtml((profile.packagePresets || []).join(', '))) +
                renderHelpers.kvRow('Weitere Pakete', renderHelpers.escapeHtml((profile.extraPackages || []).join(', '))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Streaming</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Stream Host', renderHelpers.escapeHtml(profile.streamHost || '')) +
                renderHelpers.kvRow('Moonlight Port', renderHelpers.escapeHtml(profile.moonlightPort || 'default')) +
                renderHelpers.kvRow('Sunshine API', renderHelpers.escapeHtml(profile.sunshineApiUrl || '')) +
                renderHelpers.kvRow('App', renderHelpers.escapeHtml(profile.app)) +
                renderHelpers.kvRow('Manager', renderHelpers.escapeHtml(profile.managerUrl || '')) +
                renderHelpers.kvRow('Assigned Target', renderHelpers.escapeHtml(profile.assignedTarget ? (profile.assignedTarget.name + " (#" + profile.assignedTarget.vmid + ")") : '')) +
                renderHelpers.kvRow('Assignment Source', renderHelpers.escapeHtml(profile.assignmentSource || '')) +
                renderHelpers.kvRow('Applied Policy', renderHelpers.escapeHtml(profile.appliedPolicy && profile.appliedPolicy.name || '')) +
                renderHelpers.kvRow('USB Script', renderHelpers.escapeHtml(profile.installerUrl)) +
                renderHelpers.kvRow('Live USB Script', renderHelpers.escapeHtml(profile.liveUsbUrl)) +
                renderHelpers.kvRow('Windows USB Script', renderHelpers.escapeHtml(profile.installerWindowsUrl)) +
                renderHelpers.kvRow('Installer ISO', renderHelpers.escapeHtml(profile.installerIsoUrl)) +
                renderHelpers.kvRow('Health', renderHelpers.escapeHtml(profile.controlPlaneHealthUrl)) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Endpoint Defaults</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Resolution', renderHelpers.escapeHtml(profile.resolution)) +
                renderHelpers.kvRow('FPS', renderHelpers.escapeHtml(profile.fps)) +
                renderHelpers.kvRow('Bitrate', renderHelpers.escapeHtml(profile.bitrate)) +
                renderHelpers.kvRow('Codec', renderHelpers.escapeHtml(profile.codec)) +
                renderHelpers.kvRow('Decoder', renderHelpers.escapeHtml(profile.decoder)) +
                renderHelpers.kvRow('Audio', renderHelpers.escapeHtml(profile.audio)) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Credentials</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Thin Client User', renderHelpers.escapeHtml(profile.thinclientUsername || 'thinclient')) +
                renderHelpers.kvRow('Thin Client Password', renderHelpers.escapeHtml(profile.thinclientPassword || '')) +
                renderHelpers.kvRow('Sunshine User', renderHelpers.escapeHtml(profile.sunshineUsername || '')) +
                renderHelpers.kvRow('Sunshine Password', renderHelpers.escapeHtml(maskSecret(profile.sunshinePassword || ''))) +
                renderHelpers.kvRow('Pairing PIN', renderHelpers.escapeHtml(profile.sunshinePin || '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Endpoint State</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Compliance', renderHelpers.escapeHtml(profile.compliance && profile.compliance.status || '')) +
                renderHelpers.kvRow('Drift Count', renderHelpers.escapeHtml(profile.compliance ? String(profile.compliance.drift_count || 0) : '')) +
                renderHelpers.kvRow('Alert Count', renderHelpers.escapeHtml(profile.compliance ? String(profile.compliance.alert_count || 0) : '')) +
                renderHelpers.kvRow('Pending Actions', renderHelpers.escapeHtml(String(profile.pendingActionCount || 0))) +
                renderHelpers.kvRow('Last Seen', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.reported_at || '')) +
                renderHelpers.kvRow('Target Reachable', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.moonlight_target_reachable || '')) +
                renderHelpers.kvRow('Sunshine Reachable', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.sunshine_api_reachable || '')) +
                renderHelpers.kvRow('Prepare', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.prepare_state || '')) +
                renderHelpers.kvRow('Last Launch', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_mode || '')) +
                renderHelpers.kvRow('Launch Target', renderHelpers.escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_target || '')) +
                renderHelpers.kvRow('Last Action', renderHelpers.escapeHtml(profile.lastAction && profile.lastAction.action || '')) +
                renderHelpers.kvRow('Action Result', renderHelpers.escapeHtml(formatActionState(profile.lastAction && profile.lastAction.ok))) +
                renderHelpers.kvRow('Action Time', renderHelpers.escapeHtml(profile.lastAction && profile.lastAction.completed_at || '')) +
                renderHelpers.kvRow('Action Message', renderHelpers.escapeHtml(profile.lastAction && profile.lastAction.message || '')) +
                renderHelpers.kvRow('Stored Artifact', renderHelpers.escapeHtml(profile.lastAction && profile.lastAction.stored_artifact_path || '')) +
                renderHelpers.kvRow('Artifact Size', renderHelpers.escapeHtml(profile.lastAction ? String(profile.lastAction.stored_artifact_size || 0) : '')) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>USB Tunnel</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Tunnel State', renderHelpers.escapeHtml(usbState.tunnel_state || '')) +
                renderHelpers.kvRow('Tunnel Host', renderHelpers.escapeHtml(usbState.tunnel_host || '')) +
                renderHelpers.kvRow('Tunnel Port', renderHelpers.escapeHtml(String(usbState.tunnel_port || ''))) +
                renderHelpers.kvRow('Exportable', renderHelpers.escapeHtml(String(usbState.device_count || 0))) +
                renderHelpers.kvRow('Attached in VM', renderHelpers.escapeHtml(String(usbState.attached_count || 0))) +
      '      </div></section>' +
      '      <section class="beagle-card"><h3>Installer Readiness</h3><div class="beagle-kv">' +
                renderHelpers.kvRow('Status', '<span data-beagle-installer-status>' + renderHelpers.escapeHtml(installerPrep.status || 'idle') + '</span>') +
                renderHelpers.kvRow('Zielstatus', '<span data-beagle-download-state>' + renderHelpers.escapeHtml(installerTargetState(profile, installerPrep).label) + '</span>') +
                renderHelpers.kvRow('Phase', '<span data-beagle-installer-phase>' + renderHelpers.escapeHtml(installerPrep.phase || 'inspect') + '</span>') +
                renderHelpers.kvRow('Progress', '<span data-beagle-installer-progress>' + renderHelpers.escapeHtml(String(installerPrep.progress || 0)) + '%</span>') +
                renderHelpers.kvRow('Message', '<span data-beagle-installer-message>' + renderHelpers.escapeHtml(installerPrep.message || '') + '</span>') +
                renderHelpers.kvRow('Sunshine Binary', '<span data-beagle-installer-binary>' + renderHelpers.escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.binary ? 'ok' : 'missing') + '</span>') +
                renderHelpers.kvRow('Sunshine Service', '<span data-beagle-installer-service>' + renderHelpers.escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.service ? 'active' : 'inactive') + '</span>') +
                renderHelpers.kvRow('Sunshine Process', '<span data-beagle-installer-process>' + renderHelpers.escapeHtml(installerPrep.sunshine_status && installerPrep.sunshine_status.process ? 'running' : 'stopped') + '</span>') +
      '      </div></section>' +
      '    </div>' +
      '    <section class="beagle-card"><h3>USB-Geraete vom Thin Client</h3><div class="beagle-kv">' + usbDevicesHtml + '</div></section>' +
      '    <section class="beagle-card"><h3>USB-Geraete in der VM</h3><div class="beagle-kv">' + usbAttachedHtml + '</div></section>' +
      '    <section class="beagle-card"><h3>Operator Notes</h3><ul class="beagle-notes">' + notesHtml + '</ul></section>' +
      '    <section class="beagle-card"><h3>Beagle Endpoint Env</h3><textarea class="beagle-code" readonly>' + renderHelpers.escapeHtml(profile.endpointEnv) + '</textarea></section>' +
      '    <section class="beagle-card"><h3>Profile JSON</h3><textarea class="beagle-code" readonly>' + renderHelpers.escapeHtml(profileJson) + '</textarea></section>' +
      '  </div>' +
      '</div>';

    overlay.__beagleProfile = profile;
    syncInstallerButtons(overlay, installerPrep);

    overlay.addEventListener("click", function(event) {
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
        return;
      }

      if (!(event.target instanceof HTMLElement)) {
        return;
      }

      switch (event.target.getAttribute("data-beagle-action")) {
        case "edit-desktop":
          removeOverlay();
          showUbuntuBeagleCreateModal({ profile: profile, node: profile.node });
          break;
        case "download":
          prepareInstallerDownload(runtime, profile, overlay, "installerUrl", "download", "Installer wird vorbereitet", "Beagle USB Installer Skript wird heruntergeladen.");
          break;
        case "download-live":
          prepareInstallerDownload(runtime, profile, overlay, "liveUsbUrl", "download-live", "Live USB wird vorbereitet", "Beagle Live USB Skript wird heruntergeladen.", "pve-thin-client-live-usb-vm-" + profile.vmid + ".sh");
          break;
        case "download-windows":
          prepareInstallerDownload(runtime, profile, overlay, "installerWindowsUrl", "download-windows", "Windows Installer wird vorbereitet", "Beagle Windows USB Installer wird heruntergeladen.");
          break;
        case "download-iso":
          openUrl(withNoCache(profile.installerIsoUrl));
          break;
        case "open-web-ui":
          openUrl(webUiUrlWithToken(true));
          break;
        case "copy-json":
          copyText(showError, showToast, profileJson, "Beagle Profil als JSON kopiert.");
          break;
        case "copy-env":
          copyText(showError, showToast, profile.endpointEnv, "Beagle Endpoint-Umgebung kopiert.");
          break;
        case "open-sunshine":
          apiCreateSunshineAccess(profile.vmid).then(function(access) {
            openUrl(access && access.url ? access.url : profile.sunshineApiUrl);
          }).catch(function(error) {
            showError("Sunshine Web UI konnte nicht geoeffnet werden: " + (error && error.message ? error.message : error));
          });
          break;
        case "usb-refresh":
          platformService.refreshVmUsb(profile.vmid).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Refresh fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case "usb-attach":
          platformService.attachUsb(profile.vmid, event.target.getAttribute("data-beagle-usb-busid")).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Attach fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case "usb-detach":
          platformService.detachUsb(profile.vmid, event.target.getAttribute("data-beagle-usb-busid"), event.target.getAttribute("data-beagle-usb-port")).then(function() {
            removeOverlay();
            showProfileModal({ node: profile.node, vmid: profile.vmid });
          }).catch(function(error) {
            showError("USB-Detach fehlgeschlagen: " + (error && error.message ? error.message : error));
          });
          break;
        case "open-health":
          openUrl(profile.controlPlaneHealthUrl);
          break;
        default:
          break;
      }
    });

    document.body.appendChild(overlay);
    applyInstallerPrepState(overlay, installerPrep);
    if (options.autoPrepareDownload) {
      prepareInstallerDownload(runtime, profile, overlay, "installerUrl", "download", "Installer wird vorbereitet", "Beagle USB Installer Skript wird heruntergeladen.");
    }
  }

  window.BeagleUiProfileModal = {
    buildEndpointEnv: buildEndpointEnv,
    buildNotes: buildNotes,
    copyText: copyText,
    formatActionState: formatActionState,
    renderProfileModal: renderProfileModal
  };
})();

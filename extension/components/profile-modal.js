(function() {
  "use strict";

  function renderProfileModal(options) {
    var profile = options.profile;
    var overlayId = options.overlayId;
    var removeOverlay = options.removeOverlay;
    var escapeHtml = options.escapeHtml;
    var maskSecret = options.maskSecret;
    var copyText = options.copyText;
    var platformService = options.platformService;
    var profileService = options.profileService;
    var sleep = options.sleep;
    var overlay = document.createElement("div");
    var notesHtml = profile.notes.map(function(note) {
      return "<li>" + escapeHtml(note) + "</li>";
    }).join("");
    var installerState = profileService.installerTargetState(profile, profile.installerPrep);
    var profileJson = JSON.stringify(
      {
        vmid: profile.vmid,
        node: profile.node,
        name: profile.name,
        status: profile.status,
        stream_host: profile.streamHost,
        beagle_stream_server_api_url: profile.beagle-stream-serverApiUrl,
        beagle_stream_server_username: profile.beagle-stream-serverUsername,
        beagle_stream_server_password_configured: Boolean(profile.beagle-stream-serverPassword),
        beagle_stream_server_pin: profile.beagle-stream-serverPin,
        beagle_stream_client_app: profile.app,
        beagle_stream_client_resolution: profile.resolution,
        beagle_stream_client_fps: profile.fps,
        beagle_stream_client_bitrate: profile.bitrate,
        beagle_stream_client_video_codec: profile.codec,
        beagle_stream_client_video_decoder: profile.decoder,
        beagle_stream_client_audio_config: profile.audio,
        manager_url: profile.managerUrl,
        installer_url: profile.installerUrl,
        installer_windows_url: profile.installerWindowsUrl,
        installer_iso_url: profile.installerIsoUrl,
        control_plane_health_url: profile.controlPlaneHealthUrl,
        control_plane_contract_version: profile.controlPlaneContractVersion,
        assigned_target: profile.assignedTarget,
        assignment_source: profile.assignmentSource,
        applied_policy: profile.appliedPolicy,
        expected_profile_name: profile.expectedProfileName,
        endpoint_summary: profile.endpointSummary,
        compliance: profile.compliance,
        last_action: profile.lastAction,
        pending_action_count: profile.pendingActionCount
      },
      null,
      2
    );

    function kvRow(label, value) {
      return '<div class="beagle-kv-row"><strong>' + label + "</strong><span>" + (value || '<span class="beagle-muted">nicht gesetzt</span>') + "</span></div>";
    }

    overlay.id = overlayId;
    overlay.innerHTML = '\
      <div class="beagle-modal" role="dialog" aria-modal="true" aria-label="Beagle OS Profil">\
        <div class="beagle-header">\
          <div>\
            <h2 class="beagle-title">Beagle Profil fuer VM ' + escapeHtml(profile.name) + " (#" + String(profile.vmid) + ')</h2>\
            <p class="beagle-subtitle">Beagle Stream Client-Endpunkt, Beagle Stream Server-Ziel und Beagle-Bereitstellung in einer Sicht.</p>\
          </div>\
          <button type="button" class="beagle-close" aria-label="Schliessen">×</button>\
        </div>\
        <div class="beagle-body">\
          <div class="beagle-banner ' + (profile.streamHost ? "info" : "warn") + '">' + escapeHtml(profile.streamHost ? "Streaming-Ziel erkannt: " + profile.streamHost : "Streaming-Ziel fehlt in den VM-Metadaten.") + '</div>\
          <div class="beagle-banner ' + (profile.installerTargetEligible === false ? "warn" : "info") + '"><strong>' + escapeHtml(installerState.label) + "</strong>: " + escapeHtml(installerState.message) + '</div>\
          <div class="beagle-actions">\
            ' + (profile.installerTargetEligible === false ? "" : '<button type="button" class="beagle-btn primary" data-beagle-action="download">USB Installer Skript</button>') + '\
            ' + (profile.installerTargetEligible === false ? "" : '<button type="button" class="beagle-btn secondary" data-beagle-action="download-windows">Windows USB Installer</button>') + '\
            <button type="button" class="beagle-btn secondary" data-beagle-action="download-iso">ISO Download</button>\
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-web-ui">Open Web UI</button>\
            <button type="button" class="beagle-btn secondary" data-beagle-action="copy-json">Profil JSON kopieren</button>\
            <button type="button" class="beagle-btn secondary" data-beagle-action="copy-env">Endpoint Env kopieren</button>\
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-beagle-stream-server">Beagle Stream Server Web UI</button>\
            <button type="button" class="beagle-btn secondary" data-beagle-action="open-health">Control Plane Status</button>\
          </div>\
          <div class="beagle-grid">\
            <section class="beagle-card"><h3>VM</h3><div class="beagle-kv">\
              ' + kvRow("Name", escapeHtml(profile.name)) + '\
              ' + kvRow("VMID", escapeHtml(String(profile.vmid))) + '\
              ' + kvRow("Node", escapeHtml(profile.node)) + '\
              ' + kvRow("Status", escapeHtml(profile.status)) + '\
              ' + kvRow("Guest IP", escapeHtml(profile.guestIp || "")) + '\
            </div></section>\
            <section class="beagle-card"><h3>Streaming</h3><div class="beagle-kv">\
              ' + kvRow("Stream Host", escapeHtml(profile.streamHost || "")) + '\
              ' + kvRow("Beagle Stream Client Port", escapeHtml(profile.beagle-stream-clientPort || "default")) + '\
              ' + kvRow("Beagle Stream Server API", escapeHtml(profile.beagle-stream-serverApiUrl || "")) + '\
              ' + kvRow("App", escapeHtml(profile.app)) + '\
              ' + kvRow("Manager", escapeHtml(profile.managerUrl || "")) + '\
              ' + kvRow("Assigned Target", escapeHtml(profile.assignedTarget ? profile.assignedTarget.name + " (#" + profile.assignedTarget.vmid + ")" : "")) + '\
              ' + kvRow("Assignment Source", escapeHtml(profile.assignmentSource || "")) + '\
              ' + kvRow("Applied Policy", escapeHtml(profile.appliedPolicy && profile.appliedPolicy.name || "")) + '\
              ' + kvRow("USB Script", escapeHtml(profile.installerUrl)) + '\
              ' + kvRow("Windows USB Script", escapeHtml(profile.installerWindowsUrl)) + '\
              ' + kvRow("Installer ISO", escapeHtml(profile.installerIsoUrl)) + '\
              ' + kvRow("Health", escapeHtml(profile.controlPlaneHealthUrl)) + '\
            </div></section>\
            <section class="beagle-card"><h3>Endpoint Defaults</h3><div class="beagle-kv">\
              ' + kvRow("Resolution", escapeHtml(profile.resolution)) + '\
              ' + kvRow("FPS", escapeHtml(profile.fps)) + '\
              ' + kvRow("Bitrate", escapeHtml(profile.bitrate)) + '\
              ' + kvRow("Codec", escapeHtml(profile.codec)) + '\
              ' + kvRow("Decoder", escapeHtml(profile.decoder)) + '\
              ' + kvRow("Audio", escapeHtml(profile.audio)) + '\
            </div></section>\
            <section class="beagle-card"><h3>Pairing</h3><div class="beagle-kv">\
              ' + kvRow("Beagle Stream Server User", escapeHtml(profile.beagle-stream-serverUsername || "")) + '\
              ' + kvRow("Beagle Stream Server Password", escapeHtml(maskSecret(profile.beagle-stream-serverPassword))) + '\
              ' + kvRow("Pairing PIN", escapeHtml(profile.beagle-stream-serverPin || "")) + '\
            </div></section>\
            <section class="beagle-card"><h3>Endpoint State</h3><div class="beagle-kv">\
              ' + kvRow("Compliance", escapeHtml(profile.compliance && profile.compliance.status || "")) + '\
              ' + kvRow("Drift Count", escapeHtml(String(profile.compliance && profile.compliance.drift_count || 0))) + '\
              ' + kvRow("Alert Count", escapeHtml(String(profile.compliance && profile.compliance.alert_count || 0))) + '\
              ' + kvRow("Pending Actions", escapeHtml(String(profile.pendingActionCount || 0))) + '\
              ' + kvRow("Last Seen", escapeHtml(profile.endpointSummary && profile.endpointSummary.reported_at || "")) + '\
              ' + kvRow("Target Reachable", escapeHtml(profile.endpointSummary && profile.endpointSummary.beagle_stream_client_target_reachable || "")) + '\
              ' + kvRow("Beagle Stream Server Reachable", escapeHtml(profile.endpointSummary && profile.endpointSummary.beagle_stream_server_api_reachable || "")) + '\
              ' + kvRow("Prepare", escapeHtml(profile.endpointSummary && profile.endpointSummary.prepare_state || "")) + '\
              ' + kvRow("Last Launch", escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_mode || "")) + '\
              ' + kvRow("Launch Target", escapeHtml(profile.endpointSummary && profile.endpointSummary.last_launch_target || "")) + '\
              ' + kvRow("Last Action", escapeHtml(profile.lastAction && profile.lastAction.action || "")) + '\
              ' + kvRow("Action Result", escapeHtml(profileService.formatActionState(profile.lastAction && profile.lastAction.ok))) + '\
              ' + kvRow("Action Time", escapeHtml(profile.lastAction && profile.lastAction.completed_at || "")) + '\
              ' + kvRow("Action Message", escapeHtml(profile.lastAction && profile.lastAction.message || "")) + '\
              ' + kvRow("Stored Artifact", escapeHtml(profile.lastAction && profile.lastAction.stored_artifact_path || "")) + '\
              ' + kvRow("Artifact Size", escapeHtml(String(profile.lastAction && profile.lastAction.stored_artifact_size || 0))) + '\
            </div></section>\
            <section class="beagle-card"><h3>Installer Readiness</h3><div class="beagle-kv">\
              ' + kvRow("Zielstatus", escapeHtml(installerState.label)) + '\
              ' + kvRow("Prepare", escapeHtml(profile.installerPrep && profile.installerPrep.status || "idle")) + '\
              ' + kvRow("Phase", escapeHtml(profile.installerPrep && profile.installerPrep.phase || "inspect")) + '\
              ' + kvRow("Progress", escapeHtml(String(profile.installerPrep && profile.installerPrep.progress || 0) + "%")) + '\
              ' + kvRow("Message", escapeHtml(profile.installerPrep && profile.installerPrep.message || profile.installerTargetMessage || "")) + '\
            </div></section>\
          </div>\
          <section class="beagle-card"><h3>Operator Notes</h3><ul class="beagle-notes">' + notesHtml + '</ul></section>\
          <section class="beagle-card"><h3>Beagle Endpoint Env</h3><textarea class="beagle-code" readonly>' + escapeHtml(profile.endpointEnv) + '</textarea></section>\
          <section class="beagle-card"><h3>Profile JSON</h3><textarea class="beagle-code" readonly>' + escapeHtml(profileJson) + '</textarea></section>\
        </div>\
      </div>';

    overlay.addEventListener("click", async function(event) {
      if (event.target === overlay || event.target.closest(".beagle-close")) {
        removeOverlay();
        return;
      }
      if (!(event.target instanceof HTMLElement)) {
        return;
      }
      switch (event.target.getAttribute("data-beagle-action")) {
        case "download":
          if (profile.installerTargetEligible === false) {
            break;
          }
          try {
            var state = await platformService.fetchInstallerPreparation(profile.vmid).catch(function() {
              return profile.installerPrep || null;
            });
            if (String(state && state.status || "").toLowerCase() === "ready") {
              await platformService.downloadUrl(profile.installerUrl);
              return;
            }
            if (!profileService.shouldReuseInstallerPrepState(state)) {
              state = await platformService.prepareInstallerTarget(profile.vmid);
            }
            for (var attempt = 0; attempt < 180; attempt += 1) {
              if (String(state && state.status || "").toLowerCase() === "ready") {
                await platformService.downloadUrl(profile.installerUrl);
                return;
              }
              if (String(state && state.status || "").toLowerCase() === "error") {
                throw new Error(state && state.message || "Installer-Vorbereitung fehlgeschlagen.");
              }
              await sleep(2000);
              state = await platformService.fetchInstallerPreparation(profile.vmid);
            }
            throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
          } catch (error) {
            window.alert("USB Installer konnte nicht vorbereitet werden: " + (error && error.message || error));
          }
          break;
        case "download-windows":
          if (profile.installerTargetEligible === false) {
            break;
          }
          try {
            var windowsState = await platformService.fetchInstallerPreparation(profile.vmid).catch(function() {
              return profile.installerPrep || null;
            });
            if (String(windowsState && windowsState.status || "").toLowerCase() === "ready") {
              await platformService.downloadUrl(profile.installerWindowsUrl);
              return;
            }
            if (!profileService.shouldReuseInstallerPrepState(windowsState)) {
              windowsState = await platformService.prepareInstallerTarget(profile.vmid);
            }
            for (var windowsAttempt = 0; windowsAttempt < 180; windowsAttempt += 1) {
              if (String(windowsState && windowsState.status || "").toLowerCase() === "ready") {
                await platformService.downloadUrl(profile.installerWindowsUrl);
                return;
              }
              if (String(windowsState && windowsState.status || "").toLowerCase() === "error") {
                throw new Error(windowsState && windowsState.message || "Installer-Vorbereitung fehlgeschlagen.");
              }
              await sleep(2000);
              windowsState = await platformService.fetchInstallerPreparation(profile.vmid);
            }
            throw new Error("Installer-Vorbereitung hat das Zeitlimit ueberschritten.");
          } catch (error2) {
            window.alert("Windows USB Installer konnte nicht vorbereitet werden: " + (error2 && error2.message || error2));
          }
          break;
        case "download-iso":
          await platformService.downloadUrl(profile.installerIsoUrl);
          break;
        case "open-web-ui":
          window.open(await platformService.webUiUrlWithToken(true), "_blank", "noopener,noreferrer");
          break;
        case "copy-json":
          await copyText(profileJson, "Beagle Profil als JSON kopiert.");
          break;
        case "copy-env":
          await copyText(profile.endpointEnv, "Beagle Endpoint-Umgebung kopiert.");
          break;
        case "open-beagle-stream-server":
          try {
            var access = await platformService.createBeagle Stream ServerAccess(profile.vmid);
            window.open(access && access.url || profile.beagle-stream-serverApiUrl, "_blank", "noopener,noreferrer");
          } catch (error3) {
            window.alert("Beagle Stream Server Web UI konnte nicht geoeffnet werden: " + (error3 && error3.message || error3));
          }
          break;
        case "open-health":
          window.open(profile.controlPlaneHealthUrl, "_blank", "noopener,noreferrer");
          break;
        default:
          break;
      }
    });

    document.body.appendChild(overlay);
  }

  window.BeagleExtensionProfileModal = {
    renderProfileModal: renderProfileModal
  };
})();

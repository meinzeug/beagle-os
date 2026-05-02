(function() {
  "use strict";

  function formatActionState(ok) {
    if (ok === true) {
      return "ok";
    }
    if (ok === false) {
      return "error";
    }
    return "pending";
  }

  function buildEndpointEnv(profile, options) {
    var settings = options || {};
    var endpointProfileName = profile.expectedProfileName || ("vm-" + profile.vmid);
    var lines = [
      "PVE_THIN_CLIENT_MODE=\"BEAGLE_STREAM_CLIENT\"",
      "PVE_THIN_CLIENT_PROFILE_NAME=\"" + endpointProfileName + "\"",
      "PVE_THIN_CLIENT_AUTOSTART=\"1\"",
      "PVE_THIN_CLIENT_BEAGLE_HOST=\"" + (profile.beagleHost || window.location.hostname) + "\"",
      "PVE_THIN_CLIENT_BEAGLE_PORT=\"8006\"",
      "PVE_THIN_CLIENT_BEAGLE_NODE=\"" + (profile.node || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_VMID=\"" + String(profile.vmid || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_URL=\"" + (profile.managerUrl || "") + "\""
    ];

    if (settings.includeManagerPinnedPubkey) {
      lines.push("PVE_THIN_CLIENT_BEAGLE_MANAGER_PINNED_PUBKEY=\"" + (profile.managerPinnedPubkey || "") + "\"");
    }

    lines.push(
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_HOST=\"" + (profile.streamHost || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PORT=\"" + (profile.beagle-stream-clientPort || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_APP=\"" + (profile.app || "Desktop") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION=\"" + (profile.resolution || "auto") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS=\"" + (profile.fps || "60") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE=\"" + (profile.bitrate || "20000") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_CODEC=\"" + (profile.codec || "H.264") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER=\"" + (profile.decoder || "auto") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_CONFIG=\"" + (profile.audio || "stereo") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_API_URL=\"" + (profile.beagle-stream-serverApiUrl || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_USERNAME=\"" + (profile.beagle-stream-serverUsername || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PASSWORD=\"" + (profile.beagle-stream-serverPassword || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN=\"" + (profile.beagle-stream-serverPin || "") + "\""
    );

    return lines.join("\n") + "\n";
  }

  function buildNotes(profile, options) {
    var settings = options || {};
    var notes = [];

    if (!profile.streamHost) {
      notes.push("Kein Beagle Stream Client-/Beagle Stream Server-Ziel in der VM-Metadatenbeschreibung gefunden.");
    }
    if (!profile.beagle-stream-serverApiUrl) {
      notes.push("Keine Beagle Stream Server API URL gesetzt. Pairing und Healthchecks koennen nicht vorab validiert werden.");
    }
    if (!profile.beagle-stream-serverPassword) {
      notes.push("Kein Beagle Stream Server-Passwort hinterlegt. Fuer direkte API-Aktionen ist dann ein vorregistriertes Zertifikat oder manuelles Pairing noetig.");
    }
    if (!profile.guestIp) {
      notes.push("Keine Guest-Agent-IPv4 erkannt. Beagle kann dann nur mit Metadaten arbeiten.");
    }
    if (!notes.length) {
      notes.push("VM-Profil ist vollstaendig genug fuer einen vorkonfigurierten Beagle-Endpoint mit Beagle Stream Client-Autostart.");
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
    if (settings.includeInstallerReadyNote && profile.installerPrep && profile.installerPrep.status === "ready") {
      notes.push("Installer-Vorbereitung ist bereits abgeschlossen. Der USB-Installer ist sofort freigegeben.");
    }
    if (settings.includeNoEndpointSummaryNote && !profile.endpointSummary) {
      notes.push("Endpoint hat noch keinen Check-in an die Beagle Control Plane geliefert.");
    }

    return notes;
  }

  window.BeagleBrowserVmProfileHelpers = {
    buildEndpointEnv: buildEndpointEnv,
    buildNotes: buildNotes,
    formatActionState: formatActionState
  };
})();

(function() {
  "use strict";

  var common = window.BeagleExtensionCommon;
  var virtualizationService = window.BeagleExtensionVirtualizationService;
  var platformService = window.BeagleExtensionPlatformService;

  if (!common) {
    throw new Error("BeagleExtensionCommon must be loaded before BeagleExtensionProfileService");
  }
  if (!virtualizationService) {
    throw new Error("BeagleExtensionVirtualizationService must be loaded before BeagleExtensionProfileService");
  }
  if (!platformService) {
    throw new Error("BeagleExtensionPlatformService must be loaded before BeagleExtensionProfileService");
  }

  function parseDescriptionMeta(description) {
    var meta = {};
    String(description || "")
      .replace(/\\r\\n/g, "\n")
      .replace(/\\n/g, "\n")
      .split("\n")
      .forEach(function(rawLine) {
        var line = rawLine.trim();
        var index = line.indexOf(":");
        var key;
        var value;
        if (index <= 0) {
          return;
        }
        key = line.slice(0, index).trim().toLowerCase();
        value = line.slice(index + 1).trim();
        if (key && !(key in meta)) {
          meta[key] = value;
        }
      });
    return meta;
  }

  function firstGuestIpv4(interfaces) {
    var list = Array.isArray(interfaces) ? interfaces : [];
    var iface;
    var addresses;
    var i;
    var j;
    var address;
    for (i = 0; i < list.length; i += 1) {
      iface = list[i] || {};
      addresses = Array.isArray(iface["ip-addresses"]) ? iface["ip-addresses"] : [];
      for (j = 0; j < addresses.length; j += 1) {
        address = addresses[j] || {};
        if (address["ip-address-type"] !== "ipv4") {
          continue;
        }
        if (!address["ip-address"] || /^127\./.test(address["ip-address"]) || /^169\.254\./.test(address["ip-address"])) {
          continue;
        }
        return address["ip-address"];
      }
    }
    return "";
  }

  function buildEndpointEnv(profile) {
    var endpointProfileName = profile.expectedProfileName || ("vm-" + profile.vmid);
    return [
      "PVE_THIN_CLIENT_MODE=\"MOONLIGHT\"",
      "PVE_THIN_CLIENT_PROFILE_NAME=\"" + endpointProfileName + "\"",
      "PVE_THIN_CLIENT_AUTOSTART=\"1\"",
      "PVE_THIN_CLIENT_PROXMOX_HOST=\"" + (profile.proxmoxHost || window.location.hostname) + "\"",
      "PVE_THIN_CLIENT_PROXMOX_PORT=\"8006\"",
      "PVE_THIN_CLIENT_PROXMOX_NODE=\"" + (profile.node || "") + "\"",
      "PVE_THIN_CLIENT_PROXMOX_VMID=\"" + String(profile.vmid || "") + "\"",
      "PVE_THIN_CLIENT_BEAGLE_MANAGER_URL=\"" + (profile.managerUrl || "") + "\"",
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
    ].join("\n") + "\n";
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
    return notes;
  }

  function installerTargetState(profile, state) {
    if (profile && profile.installerTargetEligible === false) {
      return {
        label: "Ziel ungeeignet",
        message: profile.installerTargetMessage || "Diese VM wird nicht als Streaming-Ziel angeboten.",
        unsupported: true
      };
    }
    if (String(state && state.status || "").toLowerCase() === "ready") {
      return {
        label: "USB Installer bereit",
        message: state && state.message || "Das VM-spezifische USB-Installer-Skript kann direkt geladen werden.",
        unsupported: false
      };
    }
    return {
      label: "Sunshine wird vorbereitet",
      message: state && state.message || "Die VM wird fuer Sunshine und den Internet-Stream vorbereitet.",
      unsupported: false
    };
  }

  function shouldReuseInstallerPrepState(state) {
    var status = String(state && state.status || "").toLowerCase();
    if (!state) {
      return false;
    }
    if (state.ready) {
      return true;
    }
    return Boolean(status) && ["idle", "error", "failed"].indexOf(status) === -1;
  }

  async function resolveVmProfile(ctx) {
    var results = await Promise.all([
      virtualizationService.getVmConfig(ctx),
      virtualizationService.listVms().catch(function() { return []; }),
      virtualizationService.getVmGuestInterfaces(ctx).catch(function() { return []; }),
      platformService.resolveUsbInstallerUrl(ctx),
      platformService.resolveInstallerIsoUrl(ctx),
      platformService.resolveControlPlaneHealthUrl(),
      platformService.fetchPublicVmState(ctx.vmid),
      platformService.fetchInstallerPreparation(ctx.vmid).catch(function() { return null; })
    ]);
    var config = results[0] || {};
    var resources = Array.isArray(results[1]) ? results[1] : [];
    var guestInterfaces = Array.isArray(results[2]) ? results[2] : [];
    var installerUrl = results[3] || "";
    var installerIsoUrl = results[4] || "";
    var controlPlaneHealthUrl = results[5] || "";
    var endpointPayload = results[6] || null;
    var installerPrep = results[7] || null;
    var resource = resources.find(function(item) {
      return item && item.type === "qemu" && Number(item.vmid) === Number(ctx.vmid);
    }) || {};
    var meta = parseDescriptionMeta(config.description || "");
    var guestIp = firstGuestIpv4(guestInterfaces);
    var controlPlaneProfile = endpointPayload && endpointPayload.profile ? endpointPayload.profile : null;
    var streamHost = controlPlaneProfile && controlPlaneProfile.stream_host || meta["moonlight-host"] || meta["sunshine-ip"] || meta["sunshine-host"] || guestIp || "";
    var moonlightPort = controlPlaneProfile && controlPlaneProfile.moonlight_port || meta["moonlight-port"] || meta["beagle-public-moonlight-port"] || "";
    var sunshineApiUrl = controlPlaneProfile && controlPlaneProfile.sunshine_api_url || meta["sunshine-api-url"] || (streamHost ? "https://" + streamHost + ":" + (moonlightPort ? Number(moonlightPort) + 1 : 47990) : "");
    var profile = {
      vmid: Number(ctx.vmid),
      node: ctx.node,
      name: config.name || resource.name || ("vm-" + ctx.vmid),
      status: resource.status || "unknown",
      guestIp: guestIp,
      streamHost: streamHost,
      moonlightPort: moonlightPort,
      sunshineApiUrl: sunshineApiUrl,
      sunshineUsername: controlPlaneProfile && controlPlaneProfile.sunshine_username || meta["sunshine-user"] || "",
      sunshinePassword: meta["sunshine-password"] || "",
      sunshinePin: meta["sunshine-pin"] || String(ctx.vmid % 10000).padStart(4, "0"),
      app: controlPlaneProfile && controlPlaneProfile.moonlight_app || meta["moonlight-app"] || meta["sunshine-app"] || "Desktop",
      resolution: controlPlaneProfile && controlPlaneProfile.moonlight_resolution || meta["moonlight-resolution"] || "auto",
      fps: controlPlaneProfile && controlPlaneProfile.moonlight_fps || meta["moonlight-fps"] || "60",
      bitrate: controlPlaneProfile && controlPlaneProfile.moonlight_bitrate || meta["moonlight-bitrate"] || "20000",
      codec: controlPlaneProfile && controlPlaneProfile.moonlight_video_codec || meta["moonlight-video-codec"] || "H.264",
      decoder: controlPlaneProfile && controlPlaneProfile.moonlight_video_decoder || meta["moonlight-video-decoder"] || "auto",
      audio: controlPlaneProfile && controlPlaneProfile.moonlight_audio_config || meta["moonlight-audio-config"] || "stereo",
      proxmoxHost: meta["proxmox-host"] || window.location.hostname,
      installerUrl: installerUrl,
      installerWindowsUrl: controlPlaneProfile && controlPlaneProfile.installer_windows_url || ("/beagle-api/api/v1/vms/" + encodeURIComponent(String(ctx.vmid)) + "/installer.ps1"),
      installerIsoUrl: controlPlaneProfile && controlPlaneProfile.installer_iso_url || installerIsoUrl,
      controlPlaneHealthUrl: controlPlaneHealthUrl,
      managerUrl: common.managerUrlFromHealthUrl(controlPlaneHealthUrl),
      endpointSummary: endpointPayload && endpointPayload.endpoint || null,
      compliance: endpointPayload && endpointPayload.compliance || null,
      lastAction: endpointPayload && endpointPayload.last_action || null,
      pendingActionCount: endpointPayload && endpointPayload.pending_action_count || 0,
      installerPrep: installerPrep,
      installerTargetEligible: controlPlaneProfile && typeof controlPlaneProfile.installer_target_eligible === "boolean" ? controlPlaneProfile.installer_target_eligible : Boolean(streamHost),
      installerTargetMessage: controlPlaneProfile && controlPlaneProfile.installer_target_message || "",
      assignedTarget: controlPlaneProfile && controlPlaneProfile.assigned_target || null,
      assignmentSource: controlPlaneProfile && controlPlaneProfile.assignment_source || "",
      appliedPolicy: controlPlaneProfile && controlPlaneProfile.applied_policy || null,
      expectedProfileName: controlPlaneProfile && controlPlaneProfile.expected_profile_name || ""
    };
    profile.notes = buildNotes(profile);
    if (!profile.endpointSummary) {
      profile.notes.push("Endpoint hat noch keinen Check-in an die Beagle Control Plane geliefert.");
    }
    profile.endpointEnv = buildEndpointEnv(profile);
    return profile;
  }

  window.BeagleExtensionProfileService = {
    buildEndpointEnv: buildEndpointEnv,
    buildNotes: buildNotes,
    formatActionState: formatActionState,
    installerTargetState: installerTargetState,
    resolveVmProfile: resolveVmProfile,
    shouldReuseInstallerPrepState: shouldReuseInstallerPrepState
  };
})();

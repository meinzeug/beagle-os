(function() {
  "use strict";

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

  function parseListText(value) {
    return String(value || "")
      .split(/[\n,]+/)
      .map(function(item) {
        return String(item || "").trim();
      })
      .filter(Boolean);
  }

  function findVmResource(resources, ctx) {
    return (Array.isArray(resources) ? resources : []).find(function(item) {
      return item && item.type === "qemu" && Number(item.vmid) === Number(ctx && ctx.vmid);
    }) || {};
  }

  function buildCommonProfile(options) {
    var ctx = options.ctx || {};
    var config = options.config || {};
    var endpointPayload = options.endpointPayload || null;
    var controlPlaneProfile = endpointPayload && endpointPayload.profile ? endpointPayload.profile : null;
    var endpointSummary = endpointPayload && endpointPayload.endpoint ? endpointPayload.endpoint : null;
    var compliance = endpointPayload && endpointPayload.compliance ? endpointPayload.compliance : null;
    var lastAction = endpointPayload && endpointPayload.last_action ? endpointPayload.last_action : null;
    var pendingActionCount = endpointPayload && endpointPayload.pending_action_count ? endpointPayload.pending_action_count : 0;
    var installerPrep = endpointPayload && endpointPayload.installer_prep ? endpointPayload.installer_prep : null;
    var meta = parseDescriptionMeta(config.description || "");
    var guestIp = firstGuestIpv4(options.guestInterfaces);
    var streamHost = controlPlaneProfile && controlPlaneProfile.stream_host || meta["moonlight-host"] || meta["sunshine-ip"] || meta["sunshine-host"] || guestIp || "";
    var moonlightPort = controlPlaneProfile && controlPlaneProfile.moonlight_port || meta["moonlight-port"] || meta["beagle-public-moonlight-port"] || "";
    var sunshineApiUrl = controlPlaneProfile && controlPlaneProfile.sunshine_api_url || meta["sunshine-api-url"] || (streamHost ? "https://" + streamHost + ":" + (moonlightPort ? String(Number(moonlightPort) + 1) : "47990") : "");
    var controlPlaneHealthUrl = options.controlPlaneHealthUrl || "";
    var managerUrl = options.managerUrl || "";
    var resource = findVmResource(options.resources, ctx);
    return {
      ctx: ctx,
      config: config,
      controlPlaneProfile: controlPlaneProfile,
      endpointSummary: endpointSummary,
      compliance: compliance,
      lastAction: lastAction,
      pendingActionCount: pendingActionCount,
      installerPrep: installerPrep,
      meta: meta,
      guestIp: guestIp,
      streamHost: streamHost,
      moonlightPort: moonlightPort,
      sunshineApiUrl: sunshineApiUrl,
      controlPlaneHealthUrl: controlPlaneHealthUrl,
      managerUrl: managerUrl,
      resource: resource
    };
  }

  function buildUiProfile(options) {
    var commonData = buildCommonProfile(options);
    var ctx = commonData.ctx;
    var config = commonData.config;
    var controlPlaneProfile = commonData.controlPlaneProfile;
    var credentials = options.credentials || null;
    var usbPayload = options.usbPayload || null;
    return {
      vmid: Number(ctx.vmid),
      node: ctx.node,
      name: config.name || commonData.resource.name || ("vm-" + ctx.vmid),
      status: commonData.resource.status || "unknown",
      guestIp: commonData.guestIp,
      streamHost: commonData.streamHost,
      moonlightPort: commonData.moonlightPort,
      sunshineApiUrl: commonData.sunshineApiUrl,
      sunshineUsername: credentials && credentials.sunshine_username || "",
      sunshinePassword: credentials && credentials.sunshine_password || "",
      sunshinePin: credentials && credentials.sunshine_pin || "",
      thinclientUsername: credentials && credentials.thinclient_username || "thinclient",
      thinclientPassword: credentials && credentials.thinclient_password || "",
      guestUser: controlPlaneProfile && controlPlaneProfile.guest_user || commonData.meta["sunshine-guest-user"] || "beagle",
      app: controlPlaneProfile && controlPlaneProfile.moonlight_app || commonData.meta["moonlight-app"] || commonData.meta["sunshine-app"] || "Desktop",
      resolution: controlPlaneProfile && controlPlaneProfile.moonlight_resolution || commonData.meta["moonlight-resolution"] || "auto",
      fps: controlPlaneProfile && controlPlaneProfile.moonlight_fps || commonData.meta["moonlight-fps"] || "60",
      bitrate: controlPlaneProfile && controlPlaneProfile.moonlight_bitrate || commonData.meta["moonlight-bitrate"] || "20000",
      codec: controlPlaneProfile && controlPlaneProfile.moonlight_video_codec || commonData.meta["moonlight-video-codec"] || "H.264",
      decoder: controlPlaneProfile && controlPlaneProfile.moonlight_video_decoder || commonData.meta["moonlight-video-decoder"] || "auto",
      audio: controlPlaneProfile && controlPlaneProfile.moonlight_audio_config || commonData.meta["moonlight-audio-config"] || "stereo",
      identityHostname: controlPlaneProfile && controlPlaneProfile.identity_hostname || commonData.meta["beagle-identity-hostname"] || "",
      desktopId: controlPlaneProfile && controlPlaneProfile.desktop_id || commonData.meta["beagle-desktop-id"] || "",
      desktopLabel: controlPlaneProfile && controlPlaneProfile.desktop_label || commonData.meta["beagle-desktop"] || "",
      desktopSession: controlPlaneProfile && controlPlaneProfile.desktop_session || commonData.meta["beagle-desktop-session"] || "",
      packagePresets: controlPlaneProfile && controlPlaneProfile.package_presets || parseListText(commonData.meta["beagle-package-presets"] || ""),
      extraPackages: controlPlaneProfile && controlPlaneProfile.extra_packages || parseListText(commonData.meta["beagle-extra-packages"] || ""),
      softwarePackages: controlPlaneProfile && controlPlaneProfile.software_packages || [],
      proxmoxHost: commonData.meta["proxmox-host"] || options.host || window.location.hostname,
      managerPinnedPubkey: controlPlaneProfile && controlPlaneProfile.beagle_manager_pinned_pubkey || "",
      installerUrl: controlPlaneProfile && controlPlaneProfile.installer_url || options.installerUrl || "",
      liveUsbUrl: controlPlaneProfile && controlPlaneProfile.live_usb_url || options.liveUsbUrl || "",
      installerWindowsUrl: controlPlaneProfile && controlPlaneProfile.installer_windows_url || options.installerWindowsUrl || "",
      installerIsoUrl: controlPlaneProfile && controlPlaneProfile.installer_iso_url || options.installerIsoUrl || "",
      controlPlaneHealthUrl: commonData.controlPlaneHealthUrl,
      managerUrl: commonData.managerUrl,
      endpointSummary: commonData.endpointSummary,
      usbState: usbPayload && usbPayload.usb ? usbPayload.usb : null,
      compliance: commonData.compliance,
      lastAction: commonData.lastAction,
      pendingActionCount: commonData.pendingActionCount,
      installerPrep: commonData.installerPrep,
      installerTargetEligible: controlPlaneProfile && typeof controlPlaneProfile.installer_target_eligible === "boolean" ? controlPlaneProfile.installer_target_eligible : Boolean(commonData.streamHost),
      installerTargetMessage: controlPlaneProfile && controlPlaneProfile.installer_target_message || "",
      assignedTarget: controlPlaneProfile && controlPlaneProfile.assigned_target || null,
      assignmentSource: controlPlaneProfile && controlPlaneProfile.assignment_source || "",
      appliedPolicy: controlPlaneProfile && controlPlaneProfile.applied_policy || null,
      beagleRole: controlPlaneProfile && controlPlaneProfile.beagle_role || commonData.meta["beagle-role"] || "",
      expectedProfileName: controlPlaneProfile && controlPlaneProfile.expected_profile_name || "",
      controlPlaneContractVersion: controlPlaneProfile && controlPlaneProfile.contract_version || "",
      metadata: commonData.meta
    };
  }

  function buildExtensionProfile(options) {
    var commonData = buildCommonProfile(options);
    var ctx = commonData.ctx;
    var config = commonData.config;
    var controlPlaneProfile = commonData.controlPlaneProfile;
    return {
      vmid: Number(ctx.vmid),
      node: ctx.node,
      name: config.name || commonData.resource.name || ("vm-" + ctx.vmid),
      status: commonData.resource.status || "unknown",
      guestIp: commonData.guestIp,
      streamHost: commonData.streamHost,
      moonlightPort: commonData.moonlightPort,
      sunshineApiUrl: commonData.sunshineApiUrl,
      sunshineUsername: controlPlaneProfile && controlPlaneProfile.sunshine_username || commonData.meta["sunshine-user"] || "",
      sunshinePassword: commonData.meta["sunshine-password"] || "",
      sunshinePin: commonData.meta["sunshine-pin"] || String(Number(ctx.vmid) % 10000).padStart(4, "0"),
      app: controlPlaneProfile && controlPlaneProfile.moonlight_app || commonData.meta["moonlight-app"] || commonData.meta["sunshine-app"] || "Desktop",
      resolution: controlPlaneProfile && controlPlaneProfile.moonlight_resolution || commonData.meta["moonlight-resolution"] || "auto",
      fps: controlPlaneProfile && controlPlaneProfile.moonlight_fps || commonData.meta["moonlight-fps"] || "60",
      bitrate: controlPlaneProfile && controlPlaneProfile.moonlight_bitrate || commonData.meta["moonlight-bitrate"] || "20000",
      codec: controlPlaneProfile && controlPlaneProfile.moonlight_video_codec || commonData.meta["moonlight-video-codec"] || "H.264",
      decoder: controlPlaneProfile && controlPlaneProfile.moonlight_video_decoder || commonData.meta["moonlight-video-decoder"] || "auto",
      audio: controlPlaneProfile && controlPlaneProfile.moonlight_audio_config || commonData.meta["moonlight-audio-config"] || "stereo",
      proxmoxHost: commonData.meta["proxmox-host"] || options.host || window.location.hostname,
      installerUrl: options.installerUrl || "",
      installerWindowsUrl: controlPlaneProfile && controlPlaneProfile.installer_windows_url || options.installerWindowsUrl || "",
      installerIsoUrl: controlPlaneProfile && controlPlaneProfile.installer_iso_url || options.installerIsoUrl || "",
      controlPlaneHealthUrl: commonData.controlPlaneHealthUrl,
      managerUrl: commonData.managerUrl,
      endpointSummary: commonData.endpointSummary,
      compliance: commonData.compliance,
      lastAction: commonData.lastAction,
      pendingActionCount: commonData.pendingActionCount,
      installerPrep: options.installerPrepOverride || commonData.installerPrep,
      installerTargetEligible: controlPlaneProfile && typeof controlPlaneProfile.installer_target_eligible === "boolean" ? controlPlaneProfile.installer_target_eligible : Boolean(commonData.streamHost),
      installerTargetMessage: controlPlaneProfile && controlPlaneProfile.installer_target_message || "",
      assignedTarget: controlPlaneProfile && controlPlaneProfile.assigned_target || null,
      assignmentSource: controlPlaneProfile && controlPlaneProfile.assignment_source || "",
      appliedPolicy: controlPlaneProfile && controlPlaneProfile.applied_policy || null,
      expectedProfileName: controlPlaneProfile && controlPlaneProfile.expected_profile_name || "",
      controlPlaneContractVersion: controlPlaneProfile && controlPlaneProfile.contract_version || ""
    };
  }

  window.BeagleBrowserVmProfileMapper = {
    buildExtensionProfile: buildExtensionProfile,
    buildUiProfile: buildUiProfile
  };
})();

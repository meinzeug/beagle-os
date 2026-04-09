const common = window.BeagleExtensionCommon;

if (!common) {
  throw new Error("BeagleExtensionCommon must be loaded before extension/options.js");
}

function loadOptions() {
  common.getStoredOptions({
    usbInstallerUrl: common.defaultPublicUsbInstallerUrl(),
    controlPlaneHealthUrl: common.defaultControlPlaneHealthUrl()
  }).then((data) => {
    document.getElementById("usbInstallerUrl").value =
      data.usbInstallerUrl || common.defaultPublicUsbInstallerUrl();
    document.getElementById("controlPlaneHealthUrl").value =
      data.controlPlaneHealthUrl || common.defaultControlPlaneHealthUrl();
  });
}

function saveOptions() {
  const usbInstallerUrl =
    document.getElementById("usbInstallerUrl").value.trim() || common.defaultPublicUsbInstallerUrl();
  const controlPlaneHealthUrl =
    document.getElementById("controlPlaneHealthUrl").value.trim() || common.defaultControlPlaneHealthUrl();

  common.saveOptions({ usbInstallerUrl, controlPlaneHealthUrl }).then(() => {
    const status = document.getElementById("status");
    status.textContent = "Saved.";
    setTimeout(() => {
      status.textContent = "";
    }, 1500);
  });
}

document.getElementById("saveBtn").addEventListener("click", saveOptions);
loadOptions();

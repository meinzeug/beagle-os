// Beagle OS Gaming Kiosk - (c) Dennis Wicht / meinzeug - MIT Licensed
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('beagleKiosk', {
  bootstrap: () => ipcRenderer.invoke('kiosk:bootstrap'),
  startLogin: () => ipcRenderer.invoke('kiosk:start-login'),
  launchGame: (game) => ipcRenderer.invoke('kiosk:launch-game', game),
  refreshCatalog: () => ipcRenderer.invoke('kiosk:refresh-catalog'),
  openStore: (payload) => ipcRenderer.invoke('kiosk:open-store', payload),
  closeStore: () => ipcRenderer.invoke('kiosk:close-store'),
  openExternal: (url) => ipcRenderer.invoke('kiosk:open-external', url),
  onGfnStatus: (callback) => {
    ipcRenderer.on('kiosk:gfn-status', (_event, payload) => callback(payload));
  },
  onStateUpdate: (callback) => {
    ipcRenderer.on('kiosk:state-update', (_event, payload) => callback(payload));
  },
});

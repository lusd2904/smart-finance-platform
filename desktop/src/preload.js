const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('desktop', {
  loadConfig: () => ipcRenderer.invoke('gateway:load'),
  presets: () => ipcRenderer.invoke('gateway:presets'),
  probe: (url) => ipcRenderer.invoke('gateway:probe', url),
  enter: (payload) => ipcRenderer.invoke('gateway:enter', payload),
  onGatewayNotice: (cb) => ipcRenderer.on('gateway:notice', (_event, notice) => cb(notice)),
})

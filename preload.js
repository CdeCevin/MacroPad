const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    leerConfig: () => ipcRenderer.invoke('leer-config'),
    guardarConfig: (datos) => ipcRenderer.send('guardar-config', datos),
    
    // Las dos nuevas herramientas
    abrirExplorador: () => ipcRenderer.invoke('abrir-explorador'),
    obtenerIcono: (ruta) => ipcRenderer.invoke('obtener-icono', ruta),
    
    // Nueva herramienta para ejecutar la acción del botón desde el frontend
    ejecutarAccion: (tipo, valor) => ipcRenderer.send('ejecutar-accion', { tipo, valor })
});
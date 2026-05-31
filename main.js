const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

// ADVERTENCIA: Ajusta esta ruta a donde realmente está tu control.py y config.json
const RUTA_JSON = 'E:\\Descargas\\Arduino\\config.json';

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1100,
        height: 800,
        autoHideMenuBar: true,
        show: false, // Iniciar oculto para evitar destellos blancos y asegurar foco
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile('index.html');

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        mainWindow.focus();
        // Truco definitivo en Windows para forzar la ventana al primer plano
        mainWindow.setAlwaysOnTop(true);
        mainWindow.setAlwaysOnTop(false);
    });
}

app.whenReady().then(() => {
    createWindow();
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

// === COMUNICACIÓN CON EL FRONTEND ===
ipcMain.handle('leer-config', async () => {
    try {
        if (fs.existsSync(RUTA_JSON)) {
            return JSON.parse(fs.readFileSync(RUTA_JSON, 'utf-8'));
        }
        return {};
    } catch (error) {
        return {};
    }
});

ipcMain.on('guardar-config', (event, nuevaConfiguracion) => {
    try {
        fs.writeFileSync(RUTA_JSON, JSON.stringify(nuevaConfiguracion, null, 4), 'utf-8');
    } catch (error) {}
});

// NUEVO: Abrir el explorador de archivos nativo de Windows
ipcMain.handle('abrir-explorador', async () => {
    const result = await dialog.showOpenDialog({
        title: 'Selecciona un ejecutable',
        properties: ['openFile'],
        filters: [
            { name: 'Aplicaciones', extensions: ['exe', 'bat', 'cmd'] },
            { name: 'Todos los archivos', extensions: ['*'] }
        ]
    });

    if (result.canceled) return null;
    return result.filePaths[0]; 
});


ipcMain.handle('obtener-icono', async (event, rutaAbsoluta) => {
    try {
        // En Windows, 'large' obtiene una versión de mayor calidad (48x48 o más si está disponible)
        const icon = await app.getFileIcon(rutaAbsoluta, { size: 'large' });
        return icon.toDataURL(); 
    } catch (error) {
        console.error("No se pudo extraer el icono:", error);
        return null;
    }
});

// NUEVO: Ejecutar acción de botón desde la interfaz
ipcMain.on('ejecutar-accion', (event, { tipo, valor }) => {
    try {
        if (tipo === 'web' || tipo === 'web_edge') {
            let url = valor.trim();
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
            }
            if (tipo === 'web_edge') {
                const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
                if (fs.existsSync(EDGE)) {
                    const { exec } = require('child_process');
                    exec(`"${EDGE}" --profile-directory=Default "${url}"`);
                } else {
                    shell.openExternal(url);
                }
            } else {
                shell.openExternal(url);
            }
        } else if (tipo === 'app') {
            let rutaLimpia = valor.replace(/"/g, '').trim();
            shell.openPath(rutaLimpia).then(errorMessage => {
                if (errorMessage) {
                    console.error("Error al abrir con openPath, intentando exec:", errorMessage);
                    const { exec } = require('child_process');
                    exec(`explorer.exe "${rutaLimpia}"`);
                }
            });
        } else if (tipo === 'script') {
            const { exec } = require('child_process');
            if (valor === 'toggle_whatsapp') {
                shell.openExternal('whatsapp:');
            } else if (valor === 'toggle_steam') {
                shell.openExternal('steam://open/main');
            } else if (valor === 'mutear_discord') {
                exec(`powershell -Command "(New-Object -ComObject Wscript.Shell).SendKeys('{F7}')"`);
            } else if (valor === 'ensordecer_discord') {
                exec(`powershell -Command "(New-Object -ComObject Wscript.Shell).SendKeys('{F8}')"`);
            } else if (valor === 'abrir_discord') {
                const localAppData = process.env.LOCALAPPDATA;
                if (localAppData) {
                    const rutaDiscord = path.join(localAppData, 'Discord', 'Update.exe');
                    if (fs.existsSync(rutaDiscord)) {
                        exec(`"${rutaDiscord}" --processStart Discord.exe`);
                    } else {
                        shell.openExternal('discord://');
                    }
                } else {
                    shell.openExternal('discord://');
                }
            } else if (valor === 'toggle_editMacroPad') {
                const wins = BrowserWindow.getAllWindows();
                if (wins.length > 0) {
                    if (wins[0].isMinimized()) wins[0].restore();
                    wins[0].focus();
                }
            }
        }
    } catch (e) {
        console.error("Error ejecutando acción:", e);
    }
});
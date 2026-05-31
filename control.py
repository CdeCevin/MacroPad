import serial
import keyboard
import time
import webbrowser
import os
import sys
import atexit
import signal
import subprocess
import logging
import threading
import json
import ctypes
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Flags de Windows para suprimir ventanas y desacoplar procesos hijos
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

# Constantes Win32
SW_MINIMIZE    = 6
SW_SHOWDEFAULT = 10
user32         = ctypes.windll.user32

# ============================================================
# CONFIGURACIÓN
# ============================================================
PUERTO_SERIAL      = 'COM6' # Asegúrate de que coincida con el puerto de tu Arduino
BAUDRATE           = 9600
DEBOUNCE_SEG       = 0.4
REINTENTOS_MAX     = None
TIMEOUT_ZOMBIE_SEG = 20

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
BOTONES = {}
observador_global = None

# ============================================================
# LOGGING  (archivo + consola)
# ============================================================
LOG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"macro_pad_{datetime.now():%Y-%m-%d}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("MacroPad")

# ============================================================
# WIN32: buscar ventana por título parcial (sin pygetwindow)
# ============================================================
def _encontrar_ventana_win32(titulo_parcial: str, timeout_seg: float = 2.0) -> int:
    resultado = {"hwnd": 0}
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

    def _enum_callback(hwnd, _):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if titulo_parcial.lower() in buf.value.lower():
                resultado["hwnd"] = hwnd
                return False
        except Exception:
            pass
        return True

    cb = WNDENUMPROC(_enum_callback)
    t  = threading.Thread(target=lambda: user32.EnumWindows(cb, 0), daemon=True)
    t.start()
    t.join(timeout=timeout_seg)

    if t.is_alive():
        log.warning(f"_encontrar_ventana_win32('{titulo_parcial}') tardó más de {timeout_seg}s — abortado.")

    return resultado["hwnd"]

def _ventana_minimizada(hwnd: int) -> bool:
    return bool(user32.IsIconic(hwnd))

def _restaurar_ventana(hwnd: int):
    user32.ShowWindow(hwnd, SW_SHOWDEFAULT)
    user32.SetForegroundWindow(hwnd)

def _minimizar_ventana(hwnd: int):
    user32.ShowWindow(hwnd, SW_MINIMIZE)

# ============================================================
# UTILIDAD: comprobar proceso sin bloquear
# ============================================================
def proceso_corriendo(nombre_exe: str) -> bool:
    try:
        resultado = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {nombre_exe}"],
            capture_output=True, text=True, timeout=3,
            creationflags=CREATE_NO_WINDOW
        )
        return nombre_exe.lower() in resultado.stdout.lower()
    except subprocess.TimeoutExpired:
        log.warning(f"Timeout comprobando proceso '{nombre_exe}'.")
        return False
    except Exception as e:
        log.error(f"Error comprobando proceso '{nombre_exe}': {e}")
        return False

# ============================================================
# FUNCIONES DE ACCIÓN
# ============================================================
def mutear_discord():
    keyboard.send('F7')
    log.info("Discord muteado.")

def ensordecer_discord():
    keyboard.send('F8')
    log.info("Discord ensordecido.")

def toggle_steam():
    try:
        if not proceso_corriendo("steam.exe"):
            os.startfile("steam://open/main")
            log.info("Steam abierto.")
            return

        hwnd = _encontrar_ventana_win32("Steam")

        if not hwnd:
            os.startfile("steam://open/main")
            log.info("Steam restaurado desde bandeja.")
            return

        if _ventana_minimizada(hwnd):
            _restaurar_ventana(hwnd)
            log.info("Steam restaurado.")
        else:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
            log.info("Steam enviado a la bandeja (cerrado).")

    except Exception as e:
        log.error(f"Error al toggle Steam: {e}")

def toggle_editMacroPad(ruta_exe=None):
    try:
        if not ruta_exe:
            ruta_exe = r"E:\Descargas\Arduino\MacroPadConfig-win32-x64\MacroPadConfig.exe"
            
        titulo_ventana = "Configurador Macro Pad"

        if not os.path.exists(ruta_exe):
            log.error(f"No se encontró el exe. Verifica que esta ruta exista: {ruta_exe}")
            return

        if not proceso_corriendo("MacroPadConfig.exe"):
            # Lanzamos mediante explorer.exe para deselevarlo a usuario estándar.
            # Esto soluciona la restricción de Windows (UIPI) y permite hacer Drag & Drop desde el Explorador.
            subprocess.Popen(
                f'explorer.exe "{ruta_exe}"',
                shell=True,
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info("MacroPadConfig abierto sin privilegios de administrador.")
            return

        hwnd = _encontrar_ventana_win32(titulo_ventana)

        if not hwnd:
            subprocess.Popen(
                f'explorer.exe "{ruta_exe}"',
                shell=True,
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info("MacroPadConfig relanzado sin privilegios de administrador.")
            return

        if _ventana_minimizada(hwnd):
            _restaurar_ventana(hwnd)
            log.info("MacroPadConfig restaurado.")
        else:
            # Si ya está abierta, la cerramos directamente (Toggle clásico)
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  
            log.info("MacroPadConfig cerrado.")

    except Exception as e:
        log.error(f"Error al toggle MacroPadConfig: {e}")

def toggle_whatsapp():
    try:
        hwnd = _encontrar_ventana_win32("WhatsApp")

        if not hwnd:
            os.startfile("whatsapp:")
            log.info("WhatsApp abierto.")
            return

        # WhatsApp es una aplicación moderna UWP (Store). 
        # Minimizarla y restaurarla con llamadas Win32 forzadas causa pantallas grises y reescalados erróneos.
        # En su lugar, comprobamos si está en primer plano:
        foreground_hwnd = user32.GetForegroundWindow()

        if hwnd == foreground_hwnd:
            # Si ya está al frente, la cerramos usando el comando clásico WM_CLOSE (0x0010)
            # para que se envíe a la bandeja del sistema (system tray) según tu configuración.
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
            log.info("WhatsApp enviado a la bandeja (cerrado).")
        else:
            # Si está minimizada o en segundo plano, la traemos al frente usando su protocolo UWP nativo.
            # Windows restaura y reactiva la app suspendida de forma nativa sin lag de pantalla gris.
            os.startfile("whatsapp:")
            log.info("WhatsApp restaurado y enfocado en primer plano.")

    except Exception as e:
        log.error(f"Error al toggle WhatsApp: {e}")

def abrir_discord():
    ruta = os.path.expandvars(
        r"C:\Users\%USERNAME%\AppData\Local\Discord\Update.exe"
    )
    if os.path.exists(ruta):
        try:
            subprocess.Popen(
                [ruta, "--processStart", "Discord.exe"],
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info("Discord lanzado.")
        except Exception as e:
            log.error(f"Error al abrir Discord: {e}")
    else:
        log.warning(f"Discord no encontrado en: {ruta}")

def lanzar_app(comando: str):
    try:
        subprocess.Popen(
            f'explorer.exe {comando}',
            shell=True,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log.info(f"App lanzada: {comando}")
    except Exception as e:
        log.error(f"Error al lanzar '{comando}': {e}")

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def abrir_web(url: str):
    try:
        webbrowser.open(url)
        log.info(f"Web abierta: {url}")
    except Exception as e:
        log.error(f"Error al abrir web '{url}': {e}")

def abrir_web_edge(url: str):
    try:
        if os.path.exists(EDGE):
            subprocess.Popen(
                [EDGE, "--profile-directory=Default", url],
                creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info(f"Edge abierto: {url}")
        else:
            log.warning(f"Edge no encontrado en: {EDGE}. Abriendo con navegador predeterminado.")
            webbrowser.open(url)
    except Exception as e:
        log.error(f"Error al abrir Edge '{url}': {e}")

def media(tecla: str):
    try:
        keyboard.send(tecla)
    except Exception as e:
        log.error(f"Error al enviar tecla '{tecla}': {e}")

def ejecutar_en_hilo(fn, nombre):
    def _wrapper():
        try:
            fn()
        except Exception as e:
            log.error(f"Error en hilo '{nombre}': {e}")

    t = threading.Thread(target=_wrapper, name=nombre, daemon=True)
    t.start()

    def _watchdog():
        t.join(timeout=10)
        if t.is_alive():
            log.warning(f"[TIMEOUT] Hilo '{nombre}' lleva más de 10s — posible cuelgue")

    threading.Thread(target=_watchdog, daemon=True).start()

# ============================================================
# DICCIONARIO DINÁMICO (SISTEMA JSON)
# ============================================================
FUNCIONES_INTERNAS = {
    "mutear_discord":      mutear_discord,
    "ensordecer_discord":  ensordecer_discord,
    "toggle_steam":        toggle_steam,
    "toggle_whatsapp":     toggle_whatsapp,
    "abrir_discord":       abrir_discord,
    "toggle_editMacroPad": toggle_editMacroPad,
}

def cargar_configuracion():
    global BOTONES
    if not os.path.exists(CONFIG_FILE):
        log.warning(f"Archivo {CONFIG_FILE} no encontrado. Creando plantilla por defecto.")
        
        config_base = {
            "A": {"tipo": "script", "valor": "mutear_discord", "nombre": "Boton A: Mutear Discord"},
            "B": {"tipo": "script", "valor": "toggle_steam", "nombre": "Boton B: Toggle Steam"}
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config_base, f, indent=4)
        BOTONES = {}
        pass

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        nuevos_botones = {}
        for codigo, data in config.items():
            tipo   = data.get("tipo")
            valor  = data.get("valor")
            nombre = data.get("nombre", "Boton sin nombre")

            if tipo == "app":
                if "macropadconfig.exe" in valor.lower():
                    accion = lambda v=valor: toggle_editMacroPad(v)
                else:
                    accion = lambda v=valor: lanzar_app(v)
                hilo = True
            elif tipo == "web":
                accion = lambda v=valor: abrir_web(v)
                hilo = True
            elif tipo == "web_edge":
                accion = lambda v=valor: abrir_web_edge(v)
                hilo = True
            elif tipo == "tecla":
                accion = lambda v=valor: media(v)
                hilo = False
            elif tipo == "script":
                accion = FUNCIONES_INTERNAS.get(
                    valor,
                    lambda v=valor: log.error(f"Funcion script '{v}' no existe")
                )
                hilo = True
            else:
                log.warning(f"Tipo de accion '{tipo}' desconocido para el boton {codigo}.")
                continue

            nuevos_botones[codigo] = {"nombre": nombre, "hilo": hilo, "accion": accion}

        BOTONES = nuevos_botones
        log.info(f"Configuracion cargada: {len(BOTONES)} botones mapeados.")
    except json.JSONDecodeError:
        log.error("Error de sintaxis en config.json. Verifica el formato.")
    except Exception as e:
        log.error(f"Error inesperado al cargar config.json: {e}")

class ConfigHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.abspath(event.src_path) == os.path.abspath(CONFIG_FILE):
            log.info("Cambio detectado en config.json. Recargando...")
            time.sleep(0.1)
            cargar_configuracion()

# ============================================================
# CIERRE LIMPIO DEL PUERTO Y OBSERVADOR
# ============================================================
puerto_global = None

def cerrar_recursos():
    global puerto_global, observador_global

    if observador_global:
        try:
            observador_global.stop()
            observador_global.join(timeout=1)
            log.info("Observador de archivos detenido.")
        except Exception as e:
            log.warning(f"Error al detener observador: {e}")

    if puerto_global and puerto_global.is_open:
        try:
            time.sleep(0.3)
            puerto_global.cancel_read()
            puerto_global.close()
            log.info("Puerto serial cerrado correctamente.")
        except Exception as e:
            log.warning(f"Error al cerrar puerto: {e}")

atexit.register(cerrar_recursos)
signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
signal.signal(signal.SIGINT,  lambda sig, frame: sys.exit(0))

# ============================================================
# RESET DEL PUERTO COM
# ============================================================
def resetear_puerto_com(puerto: str = "COM3"):
    log.info(f"Reseteando {puerto} (deshabilitar -> esperar -> habilitar) ...")
    try:
        resultado = subprocess.run(
            ["pnputil", "/enum-devices", "/class", "Ports", "/connected"],
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW
        )

        bloque_actual = ""
        instance_id   = None
        for linea in resultado.stdout.splitlines():
            if "Instance ID" in linea or "Id. de instancia" in linea:
                bloque_actual = linea.split(":", 1)[-1].strip()
            if puerto.upper() in linea:
                instance_id = bloque_actual
                break

        if not instance_id:
            log.warning(f"No se encontro el Instance ID para {puerto}. Saltando reset.")
            return

        log.info(f"  Instance ID encontrado: {instance_id}")

        r = subprocess.run(
            ["pnputil", "/disable-device", instance_id],
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW
        )
        if r.returncode != 0:
            log.warning(f"  pnputil /disable-device salio con codigo {r.returncode}: {r.stderr.strip()}")

        time.sleep(1.5)

        r = subprocess.run(
            ["pnputil", "/enable-device", instance_id],
            capture_output=True, text=True, timeout=10,
            creationflags=CREATE_NO_WINDOW
        )
        if r.returncode != 0:
            log.warning(f"  pnputil /enable-device salio con codigo {r.returncode}: {r.stderr.strip()}")

        time.sleep(1.5)
        log.info(f"  {puerto} reseteado correctamente.")

    except FileNotFoundError:
        log.warning("pnputil no encontrado. ¿Estas en Windows?")
    except Exception as e:
        log.warning(f"No se pudo resetear {puerto}: {e}  (¿ejecutando como Administrador?)")

# ============================================================
# BUCLE PRINCIPAL
# ============================================================
def iniciar_macro_pad():
    global puerto_global
    intentos = 0

    resetear_puerto_com(PUERTO_SERIAL)

    while REINTENTOS_MAX is None or intentos < REINTENTOS_MAX:
        try:
            log.info(f"Intentando conectar a {PUERTO_SERIAL} ...")
            with serial.Serial(PUERTO_SERIAL, BAUDRATE, timeout=1) as arduino:
                puerto_global = arduino
                intentos = 0
                
                time.sleep(2)
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()
                
                log.info("[OK] Macro Pad conectado correctamente. Buffers limpios.")

                tiempo_ultima   = 0.0
                ultimo_contacto = time.time()
                buffer_rx       = b""

                while True:
                    ahora = time.time()

                    # Lectura NO-BLOQUEANTE
                    try:
                        bytes_disp = arduino.in_waiting
                    except (serial.SerialException, OSError) as e:
                        log.error(f"Error consultando in_waiting: {e}")
                        break

                    if bytes_disp > 0:
                        try:
                            buffer_rx += arduino.read(bytes_disp)
                        except (serial.SerialException, OSError) as e:
                            log.error(f"Error de lectura serial fisica: {e}")
                            break

                        # Procesar todas las líneas completas acumuladas en el buffer
                        while b"\n" in buffer_rx:
                            linea_raw, buffer_rx = buffer_rx.split(b"\n", 1)
                            linea = linea_raw.decode("utf-8", errors="ignore").strip()

                            if not linea:
                                continue

                            ultimo_contacto = ahora
                            log.info(f"[RX] {linea}")

                            if linea in ("PING", "INIT", "IR_RESET", "WATCHDOG_RESET"):
                                continue

                            codigo = linea.upper()
                        
                            # NUEVO FILTRO PARA MATRIZ: Las teclas son de 1 caracter.
                            if len(codigo) > 10 or len(codigo) < 1:
                                continue

                            if codigo in BOTONES:
                                if ahora - tiempo_ultima < DEBOUNCE_SEG:
                                    continue
                                tiempo_ultima = ahora

                                boton  = BOTONES[codigo]
                                nombre = boton["nombre"]
                                log.info(f"[BOTON] {codigo} -> {nombre}")
                                if boton["hilo"]:
                                    ejecutar_en_hilo(boton["accion"], nombre)
                                else:
                                    try:
                                        boton["accion"]()
                                    except Exception as e:
                                        log.error(f"Error ejecutando '{nombre}': {e}")
                            else:
                                log.info(f"[DESCONOCIDO] {codigo}")
                    else:
                        time.sleep(0.02)


        except serial.SerialException as e:
            intentos += 1
            log.warning(f"Puerto no disponible ({e}). Reintentando en 5 s... (intento {intentos})")
            if intentos % 3 == 0:
                resetear_puerto_com(PUERTO_SERIAL)
            time.sleep(5)
        except Exception as e:
            intentos += 1
            log.error(f"Error inesperado: {e}. Reintentando en 5 s...")
            time.sleep(5)

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    log.info("=== Macro Pad iniciado ===")
    try:
        cargar_configuracion()

        observador_global = Observer()
        directorio_config = os.path.dirname(CONFIG_FILE)
        if not directorio_config:
            directorio_config = "."

        observador_global.schedule(ConfigHandler(), path=directorio_config, recursive=False)
        observador_global.start()
        log.info(f"Observando cambios en: {CONFIG_FILE}")

        iniciar_macro_pad()

    except SystemExit:
        log.info("=== Macro Pad detenido por el usuario ===")
    except Exception as e:
        log.critical(f"Fallo critico no recuperable: {e}")
        sys.exit(1)
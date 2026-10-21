"""
Actuadores en Windows: simular el teclado y el mouse con SendInput (ctypes).
No necesita librerías extra. Las flechas se mandan como "teclas extendidas",
que es como las manda un teclado real; así el navegador las recibe bien.
"""
import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# nombre -> (código virtual, scan code, es_extendida)
TECLAS = {
    "up": (0x26, 0x48, True), "down": (0x28, 0x50, True),
    "left": (0x25, 0x4B, True), "right": (0x27, 0x4D, True),
    "w": (0x57, 0x11, False), "a": (0x41, 0x1E, False),
    "s": (0x53, 0x1F, False), "d": (0x44, 0x20, False),
    "space": (0x20, 0x39, False), "enter": (0x0D, 0x1C, False),
    "r": (0x52, 0x13, False),
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _UNION)]


def activar_dpi():
    """Para que las coordenadas de pantalla coincidan con los píxeles reales
    aunque Windows tenga escala (125%, 150%...)."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


KEYEVENTF_SCANCODE = 0x0008

# Formas de mandar una tecla. Cada juego/navegador puede aceptar unas y otras no;
# el agente prueba cuál mueve al personaje y la guarda en config.json.
METODOS = ("vk_scan", "scan", "vk")


def _tecla(nombre, soltar, metodo="vk_scan"):
    vk, scan, extendida = TECLAS[nombre]
    flags = (KEYEVENTF_EXTENDEDKEY if extendida else 0) | (KEYEVENTF_KEYUP if soltar else 0)
    if metodo == "scan":      # solo código de escaneo (como un teclado físico / DirectInput)
        vk, flags = 0, flags | KEYEVENTF_SCANCODE
    elif metodo == "vk":      # solo código virtual
        scan = 0
    entrada = INPUT(type=INPUT_KEYBOARD)
    entrada.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    if user32.SendInput(1, ctypes.byref(entrada), ctypes.sizeof(INPUT)) != 1:
        raise ctypes.WinError(ctypes.get_last_error())


def presionar(nombre, duracion=0.03, metodo="vk_scan"):
    _tecla(nombre, soltar=False, metodo=metodo)
    time.sleep(duracion)
    _tecla(nombre, soltar=True, metodo=metodo)


# Teclas globales (funcionan aunque la ventana activa sea el navegador)
VK_F8, VK_F9 = 0x77, 0x78


def tecla_global(vk):
    """True si la tecla `vk` se presionó desde la última consulta (en cualquier ventana)."""
    return bool(user32.GetAsyncKeyState(vk) & 0x0001)


def ventana_consola():
    """Devuelve la ventana de esta consola (cmd o Windows Terminal), o None.
    En la terminal de VS Code no se encuentra una ventana visible y no se toca nada."""
    try:
        h = ctypes.windll.kernel32.GetConsoleWindow()
        if not h:
            return None
        raiz = user32.GetAncestor(h, 3) or h  # GA_ROOTOWNER: en Windows Terminal es la ventana real
        return raiz if user32.IsWindowVisible(raiz) else None
    except Exception:
        return None


def minimizar(ventana):
    if ventana:
        user32.ShowWindow(ventana, 6)   # SW_MINIMIZE
        time.sleep(0.4)                 # esperar la animación de minimizar


def restaurar(ventana):
    if ventana:
        user32.ShowWindow(ventana, 9)   # SW_RESTORE
        try:
            user32.SetForegroundWindow(ventana)
        except Exception:
            pass


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.03)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def ancho_pantalla():
    try:
        return user32.GetSystemMetrics(0)
    except Exception:
        return 1920

"""
Actuadores en Linux: simular el teclado y el mouse con la extensión XTest de
X11, usando python-xlib (Python puro, no hay que compilar nada).

Funciona en sesiones **Xorg** (X11). En Wayland puro ningún programa puede
enviar teclas a otras ventanas ni capturar la pantalla: hay que entrar con
"Ubuntu en Xorg" (o similar) en la pantalla de inicio de sesión.

Si está instalado `xdotool`, se ofrece como segunda forma de enviar teclas.
"""
import os
import shutil
import subprocess
import time

try:
    from Xlib import X, XK
    from Xlib import display as xdisplay
    from Xlib.ext import xtest
    from Xlib.protocol import event as xevent
except ImportError:  # sin python-xlib: el agente puede leer y planificar, pero no jugar
    X = None

# nombre usado por el agente -> nombre de la tecla en X11 (keysym)
TECLAS = {
    "up": "Up", "down": "Down", "left": "Left", "right": "Right",
    "w": "w", "a": "a", "s": "s", "d": "d",
    "space": "space", "enter": "Return", "r": "r",
    "f8": "F8", "f9": "F9",
}

METODOS = ("xtest", "xdotool") if shutil.which("xdotool") else ("xtest",)
VK_F8, VK_F9 = "f8", "f9"

_pantalla = None


def _x():
    """Conexión con el servidor X (se abre la primera vez que se usa)."""
    global _pantalla
    if _pantalla is None:
        if X is None:
            raise RuntimeError("Falta python-xlib (pip install python-xlib).")
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("No hay servidor X (variable DISPLAY vacía). "
                               "En Wayland, entra con una sesión Xorg.")
        _pantalla = xdisplay.Display()
    return _pantalla


def _codigo(nombre):
    return _x().keysym_to_keycode(XK.string_to_keysym(TECLAS.get(nombre, nombre)))


def activar_dpi():
    """En X11 las coordenadas ya son píxeles reales: no hace falta nada."""


def ancho_pantalla():
    try:
        return _x().screen().width_in_pixels
    except Exception:
        return 1920


def presionar(nombre, duracion=0.03, metodo="xtest"):
    if metodo == "xdotool" and shutil.which("xdotool"):
        tecla = TECLAS.get(nombre, nombre)
        subprocess.run(["xdotool", "keydown", tecla], check=False)
        time.sleep(duracion)
        subprocess.run(["xdotool", "keyup", tecla], check=False)
        return
    d = _x()
    codigo = _codigo(nombre)
    xtest.fake_input(d, X.KeyPress, codigo)
    d.sync()
    time.sleep(duracion)
    xtest.fake_input(d, X.KeyRelease, codigo)
    d.sync()


_previas = {}


def tecla_global(nombre):
    """True si la tecla se presionó desde la última consulta, en cualquier
    ventana. Se consulta el mapa de teclas presionadas del servidor X."""
    d = _x()
    codigo = _codigo(nombre)
    mapa = d.query_keymap()
    abajo = bool(mapa[codigo // 8] & (1 << (codigo % 8)))
    antes = _previas.get(nombre, False)
    _previas[nombre] = abajo
    return abajo and not antes


def click(x, y):
    d = _x()
    xtest.fake_input(d, X.MotionNotify, x=int(x), y=int(y))
    d.sync()
    time.sleep(0.05)
    xtest.fake_input(d, X.ButtonPress, 1)
    d.sync()
    time.sleep(0.03)
    xtest.fake_input(d, X.ButtonRelease, 1)
    d.sync()


# Clases de ventana de las terminales más comunes (para no minimizar otra cosa)
_TERMINALES = ("term", "konsole", "kgx", "console", "alacritty", "kitty", "tilix", "wezterm", "guake")


def ventana_consola():
    """La ventana activa al arrancar, si es una terminal (si no, None)."""
    try:
        d = _x()
        raiz = d.screen().root
        activa = raiz.get_full_property(d.intern_atom("_NET_ACTIVE_WINDOW"), X.AnyPropertyType)
        if not activa or not activa.value[0]:
            return None
        ventana = d.create_resource_object("window", activa.value[0])
        clase = " ".join(ventana.get_wm_class() or ()).lower()
        return ventana if any(t in clase for t in _TERMINALES) else None
    except Exception:
        return None


def _mensaje(ventana, tipo, datos):
    d = _x()
    raiz = d.screen().root
    ev = xevent.ClientMessage(window=ventana, client_type=d.intern_atom(tipo), data=(32, datos + [0] * (5 - len(datos))))
    raiz.send_event(ev, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
    d.sync()


def minimizar(ventana):
    if ventana:
        try:
            _mensaje(ventana, "WM_CHANGE_STATE", [3])  # 3 = IconicState (minimizada)
            time.sleep(0.4)
        except Exception:
            pass


def restaurar(ventana):
    if ventana:
        try:
            _mensaje(ventana, "_NET_ACTIVE_WINDOW", [2, X.CurrentTime])
        except Exception:
            pass

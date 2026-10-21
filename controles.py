"""
Actuadores (teclado y mouse simulados), según el sistema operativo:

  * Windows -> controles_windows.py  (SendInput de la API de Windows)
  * Linux   -> controles_linux.py    (extensión XTest de X11, con python-xlib)

Los dos módulos ofrecen las mismas funciones, así el resto del agente no
necesita saber en qué sistema corre.
"""
import sys

if sys.platform == "win32":
    from controles_windows import (METODOS, TECLAS, VK_F8, VK_F9, activar_dpi, ancho_pantalla,  # noqa: F401
                                   click, minimizar, presionar, restaurar, tecla_global, ventana_consola)
else:
    from controles_linux import (METODOS, TECLAS, VK_F8, VK_F9, activar_dpi, ancho_pantalla,  # noqa: F401
                                 click, minimizar, presionar, restaurar, tecla_global, ventana_consola)

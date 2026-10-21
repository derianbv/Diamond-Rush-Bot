#!/usr/bin/env bash
# Agente Diamond Rush - arranque en Linux (equivalente a INICIAR.bat).
# Uso:  ./iniciar.sh     (o:  bash iniciar.sh)
cd "$(dirname "$0")" || exit 1

# El agente necesita X11 para capturar la pantalla y enviar teclas.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "AVISO: la sesión es Wayland. En Wayland ningún programa puede capturar la pantalla"
    echo "       ni enviar teclas a otras ventanas. Cierra sesión y entra con 'Ubuntu en Xorg'"
    echo "       (el ícono de engranaje en la pantalla de inicio de sesión)."
    echo
fi

# 1) Python 3.10 o más nuevo
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$c"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "No encontré Python 3.10 o más nuevo."
    echo "En Ubuntu/Debian:  sudo apt install python3 python3-venv"
    exit 1
fi

# 2) Si hay un entorno, comprobar que funciona en ESTE computador
#    (uno copiado desde otro PC, o desde Windows, no sirve y se vuelve a crear).
if [ -d .venv ] && ! .venv/bin/python -c "import numpy, mss, Xlib" >/dev/null 2>&1; then
    echo "El entorno de Python no funciona en este computador: lo vuelvo a crear..."
    rm -rf .venv
fi

# 3) Crear el entorno e instalar (primero sin internet, desde paquetes/)
if [ ! -x .venv/bin/python ]; then
    echo "Primera vez en este computador: creando el entorno de Python..."
    if ! "$PY" -m venv .venv; then
        rm -rf .venv
        echo "No se pudo crear el entorno. En Ubuntu/Debian:  sudo apt install python3-venv"
        exit 1
    fi
    echo "Instalando librerías desde la carpeta paquetes, sin internet..."
    if ! .venv/bin/python -m pip install -q --no-index --find-links paquetes -r requirements.txt; then
        echo "No se pudo sin internet. Intento descargarlas..."
        if ! .venv/bin/python -m pip install -q -r requirements.txt; then
            echo "Falló la instalación. Revisa la conexión a internet."
            exit 1
        fi
    fi
    echo "Listo."
fi

# 4) OpenCV necesita algunas librerías del sistema para abrir sus ventanas
if ! .venv/bin/python -c "import cv2" >/dev/null 2>&1; then
    echo "OpenCV no carga. Instala las librerías del sistema que necesita:"
    echo "    sudo apt install libgl1 libglib2.0-0"
    exit 1
fi

# 5) Abrir el menú (las ventanas de OpenCV usan Qt, que no trae fuentes: usar las del sistema)
for f in /usr/share/fonts/truetype/dejavu /usr/share/fonts/TTF /usr/share/fonts; do
    if [ -d "$f" ]; then export QT_QPA_FONTDIR="$f"; break; fi
done
exec .venv/bin/python asistente.py

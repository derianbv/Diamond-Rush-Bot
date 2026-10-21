#!/usr/bin/env bash
# Descarga a paquetes/ las librerías para instalar el agente SIN internet,
# para Windows y Linux (64 bits) y Python 3.10 a 3.13.
# Ejecutar en un computador CON internet y Python; luego copiar la carpeta completa.
cd "$(dirname "$0")" || exit 1
PY=$(command -v python3 || command -v python)
[ -z "$PY" ] && { echo "No encontré Python."; exit 1; }
for v in 3.10 3.11 3.12 3.13; do
    echo "Descargando para Python $v (Windows y Linux)..."
    "$PY" -m pip download -q -d paquetes --only-binary=:all: --platform win_amd64 \
        --python-version "$v" opencv-python numpy mss
    "$PY" -m pip download -q -d paquetes --only-binary=:all: \
        --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 \
        --python-version "$v" opencv-python numpy mss python-xlib
done
echo "Listo: librerías en la carpeta paquetes"

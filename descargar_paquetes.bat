@echo off
rem Descarga las librerías (OpenCV, NumPy, mss) a la carpeta paquetes\ para
rem poder instalar el agente en un computador SIN internet.
rem Ejecutar en un computador CON internet y Python; luego copiar la carpeta completa.
chcp 65001 >nul
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo No encontre Python.
    pause
    exit /b 1
)
for %%v in (3.10 3.11 3.12 3.13) do (
    echo Descargando para Python %%v...
    %PY% -m pip download -q -d paquetes --only-binary=:all: --platform win_amd64 --python-version %%v -r requirements.txt
)
echo Listo: librerias en la carpeta paquetes
pause

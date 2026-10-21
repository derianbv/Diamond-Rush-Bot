@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Agente Diamond Rush

rem 1) Si hay un entorno de Python, comprobar que funciona en ESTE computador
rem    (un entorno copiado desde otro PC no sirve y hay que crearlo de nuevo).
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import cv2, numpy, mss" >nul 2>&1
    if errorlevel 1 (
        echo El entorno de Python no funciona en este computador: lo vuelvo a crear...
        rmdir /s /q ".venv"
    )
)

rem 2) Crear el entorno si no existe
if not exist ".venv\Scripts\python.exe" (
    call :crear_entorno
    if errorlevel 1 (
        echo.
        pause
        exit /b 1
    )
)

rem 3) Abrir el menu
".venv\Scripts\python.exe" asistente.py
exit /b 0


:crear_entorno
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
    echo No encontre Python en este computador.
    echo Instala Python 3.10 o mas nuevo desde https://www.python.org/downloads/
    echo y marca la casilla "Add Python to PATH". No necesita permisos de administrador.
    exit /b 1
)
echo Primera vez en este computador: creando el entorno de Python...
%PY% -m venv .venv
if errorlevel 1 (
    echo No se pudo crear el entorno de Python.
    exit /b 1
)
echo Instalando librerias desde la carpeta paquetes, sin internet...
".venv\Scripts\python.exe" -m pip install -q --no-index --find-links paquetes -r requirements.txt
if errorlevel 1 (
    echo No se pudo sin internet. Si la carpeta esta en una ruta muy larga, conviene
    echo moverla a una ruta corta como C:\DiamondRush. Intento descargarlas...
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
    if errorlevel 1 (
        echo Fallo la instalacion. Revisa la conexion a internet.
        echo Si el error dice que el nombre es demasiado largo, mueve esta carpeta
        echo a una ruta corta, por ejemplo C:\DiamondRush, y vuelve a abrir INICIAR.bat
        exit /b 1
    )
)
echo Listo.
exit /b 0

# Agente inteligente para Diamond Rush

Agente que juega solo (en Windows o Linux) [Diamond Rush](https://www.minijuegos.com/juego/diamond-rush) en el navegador:
**mira la pantalla**, entiende el tablero, **calcula con A\*** la secuencia de movimientos y
**presiona las teclas**, verificando con la vista cada paso y re-planificando si algo sale distinto.

Proyecto del curso de Sistemas Inteligentes. Sin acceso al código del juego ni web scraping:
solo captura de pantalla y teclado simulado.

```
 pantalla ──► VISIÓN ──► MODELO DEL JUEGO ──► A* (en paralelo) ──► TECLADO
   ▲          (casilla   (Nivel + Estado,     (plan de             │
   │           por        reglas)              movimientos)        │
   └──────────── verificar cada paso y re-planificar ◄─────────────┘
```

## Resultados

Probado con los 20 niveles reales del juego (tableros extraídos del walkthrough en video):

- **20 de 20 niveles resueltos**, la mayoría en menos de 1 s, usando solo 3 procesos (como en un
  computador de 4 núcleos). El nivel 20 (puzzle de 21 rocas) sale con la heurística de agujeros.
- La visión lee el tablero en ~8 ms por captura.

## Inicio rápido

1. Instalar [Python 3.10 o más nuevo](https://www.python.org/downloads/) marcando *"Add Python to PATH"*.
2. Descargar este repositorio y hacer doble clic en **`INICIAR.bat`**. La primera vez instala todo
   **sin internet**: las librerías vienen en `paquetes/` y la visión ya viene entrenada (`plantillas/`).
3. Abrir el juego en el navegador y, en el menú, usar **6** (configuración completa) la primera vez:
   lo único obligatorio es **calibrar** dónde está el juego en esa pantalla.
4. Para jugar: **1**, ir al navegador y presionar **F8** con el nivel listo.

**En Linux** es igual, pero se arranca con `./iniciar.sh` desde una terminal, y el escritorio debe estar
en sesión **Xorg** (no Wayland). Detalles en la sección 1.4 de la guía.

La guía detallada está en [docs/Guia_de_configuracion.pdf](docs/Guia_de_configuracion.pdf).

## Documentación

| Documento | Contenido |
|---|---|
| [Guía de configuración (PDF)](docs/Guia_de_configuracion.pdf) | Paso a paso para instalar y configurar el agente en cualquier computador |
| [Documentación técnica (PDF)](docs/Documentacion_tecnica.pdf) | Cómo funciona por dentro: visión, modelo del juego, A*, heurísticas, ejecución, análisis del video |
| [docs/curso/](docs/curso/) | Enunciado, propuesta y explicación de los objetos del juego |

Los PDF se generan desde [docs/CONFIGURACION.md](docs/CONFIGURACION.md) y
[docs/FUNCIONAMIENTO.md](docs/FUNCIONAMIENTO.md) con `python docs/generar_pdfs.py`
(requiere `pip install markdown pypdf reportlab` y Microsoft Edge).

## Estructura

| Archivo / carpeta | Qué es |
|---|---|
| `INICIAR.bat` / `iniciar.sh` | Instala el entorno (si hace falta) y abre el menú, en Windows / Linux |
| `asistente.py` | Menú y asistentes de configuración |
| `agente.py` | Ciclo del agente: percibir → planificar → actuar → verificar |
| `vision.py` | Captura de pantalla y clasificación de casillas |
| `juego.py` | Modelo del juego: tablero, estado y reglas de movimiento |
| `solver.py` | Búsqueda A* (varias estrategias en paralelo) |
| `controles.py` | Teclado y mouse simulados: `controles_windows.py` (SendInput) o `controles_linux.py` (XTest) |
| `herramientas.py` | Ventanas de calibración, etiquetado y revisión de ejemplos |
| `objetos.py`, `objetos.json` | Objetos creados por el usuario en el etiquetador |
| `config.py` | Valores por defecto (cada computador guarda los suyos en `config.json`) |
| `plantillas/` | Ejemplos de cada objeto: el "entrenamiento" de la visión |
| `pruebas.py` | Pruebas de las reglas y del A* con niveles dibujados en texto |
| `pruebas_simulacion.py` | Pruebas del agente completo contra un juego simulado |
| `analisis_video/` | Herramientas usadas para estudiar el walkthrough y los 20 tableros de prueba |
| `paquetes/` | Librerías para Windows y Linux, Python 3.10–3.13: instalación sin internet |
| `descargar_paquetes.bat` / `.sh` | Vuelve a crear `paquetes/` si hiciera falta |
| `prototipos/` | Primeras versiones del código de captura |

## Pruebas

```powershell
.venv\Scripts\python pruebas.py                          # reglas y A*
.venv\Scripts\python pruebas_simulacion.py               # agente completo contra un juego simulado
.venv\Scripts\python analisis_video\resolver_niveles.py  # los 20 niveles reales
```

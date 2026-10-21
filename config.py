"""
Configuración del agente. Se guarda en config.json (lo crea `calibrar`).
Cualquier valor de POR_DEFECTO se puede sobreescribir editando config.json.
"""
import json
import os

CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(CARPETA, "config.json")

POR_DEFECTO = {
    # Tablero en pantalla: [x, y, ancho, alto] en píxeles absolutos. Lo fija `calibrar`.
    "roi": None,
    "monitor": 1,
    # Grilla completa en pantalla (incluye el HUD de arriba y los bordes)
    "filas": 15,
    "columnas": 10,
    # Tablero efectivo dentro de esa grilla: [fila inicial, columna inicial, filas, columnas].
    # Lo de afuera (título, botones y bordes) se toma como pared y no se analiza.
    # Son 8 x 12: la fila de arriba casi siempre es pared, pero en los niveles 8 y 20
    # tiene diamantes/rocas (medio tapados por el botón WALKTHROUGH).
    "area": [2, 1, 12, 8],

    # Visión
    "umbral_desconocido": 45.0,   # distancia por encima de la cual una casilla es "desconocido"

    # Teclado
    "teclas": {"arriba": "up", "abajo": "down", "izquierda": "left", "derecha": "right"},
    "tiempo_tecla": 0.03,          # cuánto se mantiene presionada cada tecla (s)
    "metodo_teclas": "vk_scan",    # forma de enviar teclas; el agente la ajusta solo si no funciona
    "pausa_extra": 0.02,           # espera adicional tras confirmar que el jugador llegó (s)
    "timeout_movimiento": 0.6,     # si en este tiempo el jugador no llega, se re-planifica (s)
    "click_para_foco": True,       # hacer clic en el tablero antes de jugar para darle foco

    # Planificación
    "tiempo_planificacion": 100.0, # límite del A* (el profesor da 2 minutos)
    "esperar_mejor_plan": 15.0,    # tras el primer plan, segundos extra buscando uno más corto (no cuentan en el torneo)
    "max_replanificaciones": 15,
    "reiniciar_si_falla": True,    # si se atasca, clic en el botón de reiniciar y volver a intentar
    "boton_reiniciar": [0.85, 0.10], # posición del botón reiniciar, relativa al tablero (x, y entre 0 y 1)

    # Reglas dudosas del juego (cambiarlas si se observa otra cosa)
    "entra_al_abrir_puerta": True, # al abrir una puerta de llave, el jugador entra en el mismo paso
    "roca_sobre_puas": True,       # una roca se puede empujar sobre púas sin pisar (visto en el nivel 14)
    "roca_sobre_diamante": True,   # una roca puede pasar por encima de un diamante (visto en el nivel 4)
}


def cargar():
    cfg = dict(POR_DEFECTO)
    if os.path.exists(RUTA):
        with open(RUTA, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def guardar(cfg):
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

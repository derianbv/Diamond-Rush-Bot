"""
Pruebas del agente completo contra un JUEGO SIMULADO (sin navegador).

El simulador dibuja el tablero con sprites, el agente lo "ve" con su visión,
planifica y "presiona teclas" que el simulador aplica. Así se prueba el ciclo
percibir -> planificar -> actuar -> verificar -> re-planificar.

Escenarios:
  1. El juego se "come" el 10% de las teclas y usa una regla distinta a la que
     supone el agente (al abrir una puerta de llave el jugador NO entra).
  2. Niveles 14, 17 y 19 del juego: qué botón abre qué puerta está oculto; el
     agente debe descubrirlo mirando y, si se atasca, reiniciar recordando lo
     aprendido. En el 17 además hay que pasar una roca por una puerta abierta, y en
     el 19 entrar a la puerta de la salida directo desde su botón.

Ejecutar:  python pruebas_simulacion.py
"""
import os
import random
import shutil
import sys
import tempfile

import cv2
import numpy as np

CARPETA = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CARPETA)
import agente  # noqa: E402
import config  # noqa: E402
import solver  # noqa: E402
import vision  # noqa: E402
from juego import AGUJERO, BOTON, PARED, PUAS, PUERTA_METALICA, SALIDA, SUELO, desde_texto  # noqa: E402

NIVEL_1 = """
##########
#D..#...D#
#.R.^.R..#
#..##^##.#
#D.#P..#.#
#.^#.K.#D#
#..#...#.#
##L#^^^#.#
#D....R..#
#.####O###
#..B.#..D#
####M#.#.#
#D.....#.#
#.######E#
##########
"""

# Nivel 14 del juego (tablero efectivo 8x12)
NIVEL_14 = """
########
..D..#DD
#M#E##DD
...#.#M#
D..D#...
.#M#.#OB
#.RB#D..
...#D...
#L#.##R#
B..B.M..
#..R.##K
###P####
"""
# Niveles 17 y 19: hay que pasar una roca por una puerta abierta (17) y entrar
# a la puerta de la salida desde su botón (19).
NIVEL_17 = """
########
..D.^.#K
D####.#M
.MKBM.B.
P##D###D
.^.R....
.^.R.###
.##.###B
##..R...
D#^^##.D
DL..D#L#
######.E
"""
NIVEL_19 = """
########
E##K#.D.
D#..#.#^
MB..M...
.##P##..
.^.D##RD
.#.....#
.##R##..
D.D.#..B
.####^##
.L...D.#
########
"""

# Emparejamiento real visto en el video (analisis_video/puertas.py):
# puerta (fila, col) <- botón (fila, col). El agente NO lo conoce: lo descubre jugando.
PUERTAS_14 = {(2, 1): (5, 7), (3, 6): (6, 3), (5, 2): (9, 0), (9, 5): (9, 3)}
PUERTAS_17 = {(2, 7): (3, 6), (3, 1): (3, 3), (3, 4): (7, 7)}
PUERTAS_19 = {(3, 0): (3, 1), (3, 4): (8, 7)}


def preparar_sprites(destino):
    """Sprites para dibujar el tablero (de assets/ y algunos inventados)."""
    def A(n):
        return cv2.resize(cv2.imread(os.path.join(CARPETA, "assets", f"{n}.png")), (34, 34))

    def color(bgr, base="floor"):
        t = A(base).copy()
        cv2.rectangle(t, (8, 8), (26, 26), bgr, -1)
        return t

    sprites = {
        "casilla_ocupada": A("wall1"), "casilla_vacia": A("floor"), "personaje": A("Player"),
        "personaje_con_llave": cv2.rectangle(A("Player").copy(), (4, 20), (14, 30), (200, 200, 0), -1),
        "diamante": A("diamond"), "llave": A("key"), "puerta_llave": A("keyDoor"), "roca": A("Rock"),
        "agujero": A("Hole"), "puas_inactivas": A("UntriggeredSpikes"), "puas_activas": color((120, 120, 120)),
        "puerta_objetivo_cerrada": color((0, 0, 200), "wall2"),
        "puerta_objetivo_abierta": color((0, 200, 0), "wall2"),
        "boton": color((60, 30, 90)), "boton_con_roca": color((150, 200, 230)),
        "puerta_metalica": color((90, 90, 90), "wall2"), "puerta_metalica_abierta": color((20, 20, 20), "wall2"),
        "agujero_con_roca": A("Rock"),
    }
    for et, img in sprites.items():
        os.makedirs(os.path.join(destino, et))
        cv2.imwrite(os.path.join(destino, et, "0.png"), img)
    return sprites


class JuegoSimulado:
    TECLA_A_DIR = {"up": "arriba", "down": "abajo", "left": "izquierda", "right": "derecha"}

    def __init__(self, texto, sprites, prob_ignorar=0.0, **reglas):
        self.real, self.estado = desde_texto(texto, **reglas)
        self.inicial = self.estado
        self.sprites = sprites
        self.prob_ignorar = prob_ignorar
        self.gano = False
        self.ignoradas = 0

    def capturar(self):
        e, real = self.estado, self.real
        filas = []
        for f in range(real.filas):
            fila = []
            for c in range(real.columnas):
                i = f * real.columnas + c
                t = real.tipo[i]
                et = {PARED: "casilla_ocupada", SUELO: "casilla_vacia", AGUJERO: "agujero", BOTON: "boton",
                      PUAS: "puas_inactivas",
                      SALIDA: "puerta_objetivo_cerrada" if e.diamantes else "puerta_objetivo_abierta",
                      PUERTA_METALICA: "puerta_metalica_abierta" if real.puerta_abierta(i, e.rocas)
                      else "puerta_metalica"}[t]
                if t == AGUJERO and i in e.agujeros_llenos:
                    et = "agujero_con_roca"
                if t == PUAS and i in e.puas_pisadas:
                    et = "puas_activas"
                if i in e.puertas_llave:
                    et = "puerta_llave"
                if i in e.llaves:
                    et = "llave"
                if i in e.diamantes:
                    et = "diamante"
                if i in e.rocas:
                    et = "boton_con_roca" if t == BOTON else "roca"
                if i == e.jugador:
                    et = "personaje_con_llave" if e.tiene_llave else "personaje"
                fila.append(self.sprites[et])
            filas.append(np.hstack(fila))
        img = np.vstack(filas).astype(np.int16)
        ruido = np.random.randint(-5, 6, img.shape)  # como una captura real, nunca idéntica
        return np.clip(img + ruido, 0, 255).astype(np.uint8)

    def presionar(self, tecla, *_):
        if random.random() < self.prob_ignorar:
            self.ignoradas += 1
            return
        r = self.real.mover(self.estado, self.TECLA_A_DIR[tecla])
        if r:
            self.estado, g = r
            self.gano |= g

    def reiniciar(self):
        self.estado = self.inicial


def jugar(juego, filas, columnas, reiniciar_si_falla=True):
    agente.presionar = juego.presionar
    agente.click = lambda x, y: None
    cfg = config.cargar()
    cfg.update(roi=[0, 0, columnas * 34, filas * 34], timeout_movimiento=0.02, tiempo_planificacion=60,
               pausa_extra=0, metodo_teclas="vk_scan")
    clf = vision.Clasificador(filas, columnas, cfg["umbral_desconocido"])
    agente.MEMORIA_PUERTAS.clear()
    for intento in range(3):
        resultado = agente.jugar_nivel(cfg, juego, clf, hacer_click=False)
        if resultado is True or not reiniciar_si_falla:
            break
        print(">>> El agente se atascó: REINICIO del nivel (recuerda lo aprendido de las puertas)")
        juego.reiniciar()
    return juego.gano


def main():
    random.seed(1)
    np.random.seed(1)
    # En la simulación el tiempo no importa: sin esperas y planificando en un solo proceso.
    agente.time.sleep = lambda s: None
    original = solver.resolver
    agente.resolver = lambda *a, **k: original(*a, **{**k, "paralelo": False})

    temporal = tempfile.mkdtemp(prefix="diamond_rush_")
    carpeta_original = vision.CARPETA_PLANTILLAS
    vision.CARPETA_PLANTILLAS = temporal
    try:
        sprites = preparar_sprites(temporal)
        resultados = []

        print("=" * 60, "\nEscenario 1: teclas perdidas + regla distinta en las puertas de llave\n" + "=" * 60)
        j = JuegoSimulado(NIVEL_1, sprites, prob_ignorar=0.10, entra_al_abrir=False)
        gano = jugar(j, 15, 10)
        resultados.append(("teclas perdidas + regla distinta", gano))
        print(f"teclas que el juego ignoró: {j.ignoradas}")

        for numero, texto, puertas in ((14, NIVEL_14, PUERTAS_14), (17, NIVEL_17, PUERTAS_17),
                                       (19, NIVEL_19, PUERTAS_19)):
            print("=" * 60, f"\nNivel {numero} con el emparejamiento de puertas oculto\n" + "=" * 60)
            j = JuegoSimulado(texto, sprites)
            j.real.candidatos = {pf * 8 + pc: {bf * 8 + bc} for (pf, pc), (bf, bc) in puertas.items()}
            gano = jugar(j, 12, 8)
            resultados.append((f"puertas ocultas (nivel {numero})", gano))

        print("\n" + "=" * 60)
        for nombre, gano in resultados:
            print(f"[{'OK' if gano else 'FALLA'}] {nombre}")
        print(f"{sum(g for _, g in resultados)}/{len(resultados)} escenarios ganados")
    finally:
        vision.CARPETA_PLANTILLAS = carpeta_original
        shutil.rmtree(temporal, ignore_errors=True)


if __name__ == "__main__":
    main()

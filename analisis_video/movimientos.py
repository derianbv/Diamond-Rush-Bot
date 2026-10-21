"""
Extrae del walkthrough la secuencia de movimientos del jugador (siguiendo su
camisa blanca) y la reproduce en el modelo del juego: si el modelo la acepta
y gana, sus reglas coinciden con el juego real (comprobado en los niveles 1 y 4).

Uso:
    python analisis_video/movimientos.py 4
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
PROY = os.path.dirname(AQUI)
OUT = os.path.join(AQUI, "salida")
_ap = argparse.ArgumentParser()
_ap.add_argument("nivel", type=int)
_ap.add_argument("--video", default=os.path.join(PROY, "Diamond Rush.mp4"))
_ap.add_argument("--paso", type=int, default=3, help="analizar 1 de cada N cuadros")
_args = _ap.parse_args()
NIVEL, PASO, VIDEO = _args.nivel, _args.paso, _args.video
sys.path.insert(0, PROY)
from juego import construir_estado, construir_nivel, dibujar, JUGADOR  # noqa: E402

F0, C0, NF, NC = 2, 1, 12, 8
CH, CW = 552 / 15, 360 / 10
inicio = json.load(open(os.path.join(AQUI, "inicios.json")))
verdad = json.load(open(os.path.join(AQUI, "niveles_walkthrough.json")))


ULTIMO = [None]


def centro_jugador(frame):
    """Centro de la camisa blanca del jugador (píxeles claros y poco saturados).
    La camisa mide ~30 px; los destellos al recoger diamantes son más grandes.
    Se elige el componente más cercano a la última posición conocida."""
    zona = frame[int(F0 * CH):int((F0 + NF) * CH), int(C0 * CW):int((C0 + NC) * CW)]
    hsv = cv2.cvtColor(zona, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 1] < 45) & (hsv[:, :, 2] > 190)).astype(np.uint8)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(m)
    cand = [(cent[i][0] / CW, (cent[i][1] + CH * 0.15) / CH) for i in range(1, n)
            if 20 <= stats[i, cv2.CC_STAT_AREA] <= 45 and cent[i][1] / CH > 0.25]
    if not cand:
        return None
    if ULTIMO[0] is not None:
        ux, uy = ULTIMO[0]
        cand.sort(key=lambda p: (p[0] - ux) ** 2 + (p[1] - uy) ** 2)
        if (cand[0][0] - ux) ** 2 + (cand[0][1] - uy) ** 2 > 1.0:
            return None  # demasiado lejos: probablemente es otra cosa (un destello, un diamante)
    ULTIMO[0] = cand[0]
    return cand[0]


v = cv2.VideoCapture(VIDEO)
ini = inicio[str(NIVEL)]
fin = inicio.get(str(NIVEL + 1), int(v.get(cv2.CAP_PROP_FRAME_COUNT)) - 60)
v.set(cv2.CAP_PROP_POS_FRAMES, ini)
celdas = []  # (frame, fila, col): cada vez que el jugador entra a una casilla nueva
for k in range(ini, fin):
    ok, fr = v.read()
    if not ok:
        break
    p = centro_jugador(fr)
    if p is None:
        continue
    cx, cy = p
    c, f = int(cx), int(cy)
    adentro = 0.2 < cx - c < 0.8 and 0.2 < cy - f < 0.8   # histéresis: bien adentro de la casilla
    if adentro and (not celdas or (celdas[-1][1], celdas[-1][2]) != (f, c)):
        celdas.append((k, f, c))

DIRS = {(-1, 0): "arriba", (1, 0): "abajo", (0, -1): "izquierda", (0, 1): "derecha"}
pasos = []
for (k0, f0, c0), (k1, f1, c1) in zip(celdas, celdas[1:]):
    d = (f1 - f0, c1 - c0)
    if d in DIRS:
        pasos.append((k1, DIRS[d]))
    else:  # saltó más de una casilla entre lecturas: rellenar en L (horizontal, luego vertical)
        for _ in range(abs(c1 - c0)):
            pasos.append((k1, "derecha" if c1 > c0 else "izquierda"))
        for _ in range(abs(f1 - f0)):
            pasos.append((k1, "abajo" if f1 > f0 else "arriba"))
print(f"{len(pasos)} movimientos extraídos del video")

g = [fila[1:9] for fila in verdad[str(NIVEL)][2:14]]
jug = next(f * 8 + c for f in range(12) for c in range(8) if g[f][c] in JUGADOR)
nivel = construir_nivel(g, jug)
e = construir_estado(nivel, g, jug, False)
for n, (k, d) in enumerate(pasos):
    r = nivel.mover(e, d)
    if r is None:
        print(f"\nPaso {n} ({d}) en t={k / 25:.2f}s: el MODELO LO RECHAZA. Estado del modelo:")
        print(dibujar(nivel, e))
        print("Siguientes movimientos del video:", [p for _, p in pasos[n:n + 12]])
        break
    e, gano = r
    if gano:
        print(f"El modelo GANA en el paso {n + 1}.")
        break
else:
    print("Se reprodujeron todos los movimientos; estado final del modelo:")
    print(dibujar(nivel, e))
print("diamantes restantes en el modelo:", len(e.diamantes))

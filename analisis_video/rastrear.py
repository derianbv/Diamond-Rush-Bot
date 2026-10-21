"""
Rastrea un nivel del walkthrough: lee el tablero cada pocos cuadros y anota
qué cambia (jugador, rocas, puertas, púas...). Así se vio, por ejemplo, qué
botón abre cada puerta metálica en el nivel 14.

Uso (después de extraer_niveles.py y construir_niveles.py):
    python analisis_video/rastrear.py 14
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
from vision import cortar_celdas, huella  # noqa: E402
from juego import SIMBOLO  # noqa: E402

verdad = json.load(open(os.path.join(AQUI, "niveles_walkthrough.json")))
inicio = json.load(open(os.path.join(AQUI, "inicios.json")))
F0, C0, NF, NC = 2, 1, 12, 8

# Clasificador con todas las casillas etiquetadas de los 20 inicios
H, L = [], []
for n in range(1, 21):
    cs = cortar_celdas(cv2.imread(f"{OUT}/niveles/nivel_{n:02d}.png"), 15, 10)
    for f in range(F0, F0 + NF):
        for c in range(C0, C0 + NC):
            H.append(huella(cs[f * 10 + c]))
            L.append(verdad[str(n)][f][c])
H = np.stack(H)
H2 = (H ** 2).sum(1)
L = np.array(L)
ES_J = L == "personaje"


def leer(frame):
    cs = cortar_celdas(frame, 15, 10)
    F = np.stack([huella(cs[f * 10 + c]) for f in range(F0, F0 + NF) for c in range(C0, C0 + NC)])
    D = np.sqrt(np.maximum((F ** 2).sum(1)[:, None] + H2[None] - 2 * F @ H.T, 0) / F.shape[1])
    et = L[D.argmin(1)].copy()
    dmin = D.min(1)
    j = int(D[:, ES_J].min(1).argmin())
    et[et == "personaje"] = "casilla_vacia"
    et[j] = "personaje"
    return et, dmin, F


v = cv2.VideoCapture(VIDEO)
ini = inicio[str(NIVEL)]
fin = inicio.get(str(NIVEL + 1), int(v.get(cv2.CAP_PROP_FRAME_COUNT)) - 60)
v.set(cv2.CAP_PROP_POS_FRAMES, ini)
ok, f0 = v.read()
_, _, F_ini = leer(f0)
pos = lambda i: f"({i // NC},{i % NC})"
anterior = None
k = ini
while k < fin - 10:
    v.set(cv2.CAP_PROP_POS_FRAMES, k)
    ok, fr = v.read()
    if not ok:
        break
    et, dmin, F = leer(fr)
    # casillas que cambiaron mucho respecto del inicio (p.ej. una puerta que se abrió)
    cambio = np.sqrt(((F - F_ini) ** 2).mean(1))
    resumen = {
        "J": int(np.where(et == "personaje")[0][0]),
        "R": tuple(np.where(et == "roca")[0]),
        "D": int((et == "diamante").sum()),
        "K": tuple(np.where(et == "llave")[0]),
        "L": tuple(np.where(et == "puerta_llave")[0]),
        "M": tuple(np.where(et == "puerta_metalica")[0]),
        "O": tuple(np.where(et == "agujero")[0]),
        "^": tuple(np.where(et == "puas_inactivas")[0]),
    }
    if resumen != anterior:
        cambios = []
        if anterior is None:
            cambios = [f"{c}={[pos(i) for i in v]}" if isinstance(v, tuple) else f"{c}={v}" for c, v in resumen.items()]
            cambios[0] = f"J={pos(resumen['J'])}"
        else:
            for c in resumen:
                if resumen[c] != anterior[c]:
                    if isinstance(resumen[c], tuple):
                        a, b = set(anterior[c]), set(resumen[c])
                        cambios.append(f"{c}: -{[pos(i) for i in sorted(a - b)]} +{[pos(i) for i in sorted(b - a)]}")
                    elif c == "J":
                        cambios.append(f"J {pos(anterior[c])}->{pos(resumen[c])}")
                    else:
                        cambios.append(f"{c} {anterior[c]}->{resumen[c]}")
        print(f"{k / 25:7.2f}s  " + "  ".join(cambios), flush=True)
        anterior = resumen
    k += PASO

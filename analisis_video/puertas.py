"""
Descubre en el walkthrough qué botón abre cada puerta metálica de un nivel.

Para cada cuadro (cada 0,2 s) mira:
  * si cada puerta está ABIERTA: su casilla se ve distinta a como empezó;
  * si cada botón está PRESIONADO: tiene algo encima (una roca o el jugador).
Luego, para cada puerta, el botón cuyo estado "presionado" coincide más veces
con el estado "abierta" de la puerta es el que la abre.

Uso:  python analisis_video/puertas.py 17 19   (necesita el video y extraer_niveles.py)
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
PROY = os.path.dirname(AQUI)
sys.path.insert(0, PROY)
from vision import cortar_celdas, huella  # noqa: E402

F0, C0, NF, NC = 2, 1, 12, 8
UMBRAL_CAMBIO = 15.0


def hay_jugador(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ((hsv[:, :, 1] < 45) & (hsv[:, :, 2] > 190)).sum() > 8


def analizar(nivel, video, verdad, inicios):
    grilla = [fila[C0:C0 + NC] for fila in verdad[str(nivel)][F0:F0 + NF]]
    puertas = [(f, c) for f in range(NF) for c in range(NC) if grilla[f][c] == "puerta_metalica"]
    botones = [(f, c) for f in range(NF) for c in range(NC) if grilla[f][c] == "boton"]
    if not puertas or not botones:
        return {}
    v = cv2.VideoCapture(video)
    ini = inicios[str(nivel)]
    fin = inicios.get(str(nivel + 1), int(v.get(cv2.CAP_PROP_FRAME_COUNT)) - 60) - 25
    v.set(cv2.CAP_PROP_POS_FRAMES, ini)
    _, f0 = v.read()
    celdas0 = cortar_celdas(f0, 15, 10)
    h0 = {p: huella(celdas0[(p[0] + F0) * 10 + p[1] + C0]) for p in puertas + botones}

    abierta = {p: [] for p in puertas}      # por cuadro: True/False/None (tapada por el jugador)
    presionado = {b: [] for b in botones}
    for k in range(ini, fin, 5):
        v.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, fr = v.read()
        if not ok:
            break
        cs = cortar_celdas(fr, 15, 10)
        for p in puertas:
            img = cs[(p[0] + F0) * 10 + p[1] + C0]
            cambio = np.sqrt(((huella(img) - h0[p]) ** 2).mean())
            abierta[p].append(None if hay_jugador(img) else cambio > UMBRAL_CAMBIO)
        for b in botones:
            img = cs[(b[0] + F0) * 10 + b[1] + C0]
            cambio = np.sqrt(((huella(img) - h0[b]) ** 2).mean())
            presionado[b].append(cambio > UMBRAL_CAMBIO)

    resultado = {}
    for p in puertas:
        validos = [i for i, x in enumerate(abierta[p]) if x is not None]
        veces_abierta = sum(abierta[p][i] for i in validos)
        mejor = None
        for b in botones:
            acuerdo = sum(abierta[p][i] == presionado[b][i] for i in validos) / max(1, len(validos))
            if mejor is None or acuerdo > mejor[1]:
                mejor = (b, acuerdo)
        resultado[p] = {"boton": mejor[0], "acuerdo": round(mejor[1], 3), "cuadros_abierta": veces_abierta,
                        "cuadros": len(validos)}
    return resultado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("niveles", type=int, nargs="+")
    ap.add_argument("--video", default=os.path.join(PROY, "Diamond Rush.mp4"))
    args = ap.parse_args()
    verdad = json.load(open(os.path.join(AQUI, "niveles_walkthrough.json")))
    inicios = json.load(open(os.path.join(AQUI, "inicios.json")))
    for n in args.niveles:
        print(f"Nivel {n}:")
        for p, r in analizar(n, args.video, verdad, inicios).items():
            print(f"  puerta {p} <- botón {r['boton']}  (coinciden el {r['acuerdo']:.0%} de los cuadros; "
                  f"abierta en {r['cuadros_abierta']} de {r['cuadros']})")


if __name__ == "__main__":
    main()

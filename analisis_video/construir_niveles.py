"""
Paso 2 del análisis del walkthrough: con los grupos etiquetados a mano
(etiquetas_grupos.py), armar el tablero de cada nivel y sacar ejemplos para
entrenar la visión.

Uso (después de extraer_niveles.py):
    python analisis_video/construir_niveles.py --video "Diamond Rush.mp4"

Salida:
    analisis_video/niveles_walkthrough.json   tablero inicial de los 20 niveles (grilla 15x10)
    analisis_video/salida/plantillas_video/   ejemplos por objeto, listos para copiar a plantillas/
"""
import argparse
import json
import os
import pickle
import shutil
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
sys.path.insert(0, AQUI)
from etiquetas_grupos import ETIQUETA_GRUPO  # noqa: E402
from vision import cortar_celdas, huella  # noqa: E402

SALIDA = os.path.join(AQUI, "salida")
NIVELES_FILA_ARRIBA_ABIERTA = (8, 20)   # en el resto, la fila de abajo del título es pared

# Estado que aparece al final de un nivel en una casilla que empezó con...
CAMBIO_A = {"puas_inactivas": "puas_activas", "agujero": "agujero_con_roca",
            "puerta_objetivo_cerrada": "puerta_objetivo_abierta",
            "puerta_metalica": "puerta_metalica_abierta", "boton": "boton_con_roca"}


def oscuros(img):
    """Píxeles muy oscuros en el centro de la casilla."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    return int((g[h // 5:-h // 5, w // 5:-w // 5] < 35).sum())


def hay_jugador(img):
    """La camisa blanca del jugador: píxeles claros y poco saturados."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ((hsv[:, :, 1] < 45) & (hsv[:, :, 2] > 190)).sum() > 8


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    args = ap.parse_args()

    datos = pickle.load(open(os.path.join(SALIDA, "grupos.pkl"), "rb"))
    frames = {n: cortar_celdas(cv2.imread(os.path.join(SALIDA, "niveles", f"nivel_{n:02d}.png")), 15, 10)
              for n in range(1, 21)}
    verdad = {n: [["casilla_ocupada"] * 10 for _ in range(15)] for n in range(1, 21)}

    for gi, grupo in enumerate(datos["grupos"]):
        for i in grupo:
            n, f, c = datos["celdas"][i]
            img = frames[n][f * 10 + c]
            if gi == 0:
                # El grupo más grande ("suelo") en realidad mezcla suelo, púas y agujeros:
                # se separan contando píxeles oscuros (suelo 0-19, púas 45-70, agujero >190).
                o = oscuros(img)
                et = "agujero" if o > 150 else "puas_inactivas" if 30 <= o <= 80 else "casilla_vacia"
                # El cursor de la grabación (círculo negro) no son púas
                if et == "puas_inactivas" and (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) < 12).sum() > 25:
                    et = "casilla_vacia"
            else:
                et = ETIQUETA_GRUPO[gi]
            verdad[n][f][c] = et

    for n in verdad:
        if n not in NIVELES_FILA_ARRIBA_ABIERTA:
            verdad[n][2][1:9] = ["casilla_ocupada"] * 8  # bajo el título: pared (el sombrero confunde)

    json.dump(verdad, open(os.path.join(AQUI, "niveles_walkthrough.json"), "w"))
    print("Tableros guardados en niveles_walkthrough.json")

    # Ejemplos para la visión: las casillas iniciales + estados del final de cada nivel
    inicios = {int(k): fr for k, fr in json.load(open(os.path.join(AQUI, "inicios.json"))).items()}
    v = cv2.VideoCapture(args.video)
    fin_video = int(v.get(cv2.CAP_PROP_FRAME_COUNT)) - 60
    muestras = []
    for n in range(1, 21):
        cs0 = frames[n]
        v.set(cv2.CAP_PROP_POS_FRAMES, (inicios[n + 1] if n < 20 else fin_video) - 15)
        _, fr = v.read()
        cs1 = cortar_celdas(fr, 15, 10)
        for f in range(2, 14):
            for c in range(1, 9):
                et0 = verdad[n][f][c]
                muestras.append((et0, cs0[f * 10 + c]))
                if et0 in CAMBIO_A and not hay_jugador(cs1[f * 10 + c]):
                    if np.sqrt(((huella(cs0[f * 10 + c]) - huella(cs1[f * 10 + c])) ** 2).mean()) > 15:
                        muestras.append((CAMBIO_A[et0], cs1[f * 10 + c]))

    # Quitar casi-duplicados por objeto
    carpeta = os.path.join(SALIDA, "plantillas_video")
    shutil.rmtree(carpeta, ignore_errors=True)
    por_objeto = {}
    for et, img in muestras:
        h = huella(img)
        lista = por_objeto.setdefault(et, [])
        if all(np.sqrt(((h - h2) ** 2).mean()) > 7 for h2, _ in lista):
            lista.append((h, img))
    for et, lista in por_objeto.items():
        os.makedirs(os.path.join(carpeta, et))
        for k, (_, img) in enumerate(lista):
            cv2.imwrite(os.path.join(carpeta, et, f"video_{k:03d}.png"), img)
    print({et: len(l) for et, l in por_objeto.items()})
    print("Ejemplos en", carpeta, "(revisarlos con la galería antes de copiarlos a plantillas/)")


if __name__ == "__main__":
    main()

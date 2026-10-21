"""
Paso 1 del análisis del walkthrough: extraer el primer cuadro de cada nivel y
agrupar sus casillas por parecido (para etiquetarlas por grupos, no una a una).

Uso (desde la carpeta del proyecto):
    python analisis_video/extraer_niveles.py --video "Diamond Rush.mp4"
    python analisis_video/extraer_niveles.py --video "Diamond Rush.mp4" --detectar   # mostrar cambios de tablero

Salida en analisis_video/salida/:
    niveles/nivel_XX.png   primer cuadro quieto de cada nivel
    grupos.pkl             grupos de casillas parecidas
    grupos_N.png           hojas con un ejemplo de cada grupo (para etiquetarlos a ojo
                           en etiquetas_grupos.py)
"""
import argparse
import json
import os
import pickle
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from vision import cortar_celdas, huella  # noqa: E402

SALIDA = os.path.join(AQUI, "salida")
FILAS, COLUMNAS = 15, 10          # grilla completa del juego
F0, F1 = 2, 15                    # filas con tablero (debajo del título)
UMBRAL_GRUPO = 20.0               # distancia de huella para considerar dos casillas "iguales"


def detectar_cambios(video):
    """Momentos en que el tablero cambia casi entero (= cambio de nivel).
    Se compara cada 5 cuadros una versión reducida del tablero."""
    v = cv2.VideoCapture(video)
    fps = v.get(cv2.CAP_PROP_FPS)
    i, previo, eventos = 0, None, []
    while True:
        ok, f = v.read()
        if not ok:
            break
        if i % 5 == 0:
            g = cv2.resize(cv2.cvtColor(f[110:540], cv2.COLOR_BGR2GRAY), (90, 108)).astype(np.float32)
            if previo is not None and np.abs(g - previo).mean() > 15:
                if not eventos or i - eventos[-1] > 50:
                    eventos.append(i)
            previo = g
        i += 1
    return [round(e / fps, 1) for e in eventos]


def primer_cuadro_quieto(v, desde):
    """Desde el cuadro `desde`, el primero tras 4 cuadros seguidos sin cambios."""
    v.set(cv2.CAP_PROP_POS_FRAMES, desde)
    previo, quietos = None, 0
    for k in range(150):
        ok, f = v.read()
        g = cv2.cvtColor(f[110:540], cv2.COLOR_BGR2GRAY).astype(np.float32)
        if previo is not None:
            quietos = quietos + 1 if np.abs(g - previo).mean() < 0.8 else 0
            if quietos >= 4:
                return desde + k - 4, f
        previo = g
    return desde, f


def agrupar(celdas):
    """Agrupamiento "líder": cada casilla entra al primer grupo cuyo
    representante está a menos de UMBRAL_GRUPO; si no, crea uno nuevo."""
    H = np.stack([huella(img) for _, _, _, img in celdas])
    dim = H.shape[1]
    centros, grupos = [], []
    for i, h in enumerate(H):
        if centros:
            d = np.sqrt(((np.stack(centros) - h) ** 2).sum(1) / dim)
            j = int(d.argmin())
            if d[j] < UMBRAL_GRUPO:
                grupos[j].append(i)
                continue
        centros.append(h)
        grupos.append([i])
    return sorted(grupos, key=len, reverse=True)


def hojas_de_grupos(celdas, grupos):
    T = 54
    tiles = []
    for k, miembros in enumerate(grupos):
        sel = [miembros[0]] + miembros[1:][::max(1, len(miembros) // 3)][:3]
        t = np.full((T + 14, T * 4, 3), 30, np.uint8)
        for m, i in enumerate(sel):
            t[:T, m * T:(m + 1) * T] = cv2.resize(celdas[i][3], (T, T))
        cv2.putText(t, f"#{k} n={len(miembros)}", (2, T + 11), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1)
        tiles.append(t)
    while len(tiles) % 6:
        tiles.append(np.zeros_like(tiles[0]))
    filas = [np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]
    for p in range(0, len(filas), 12):
        cv2.imwrite(os.path.join(SALIDA, f"grupos_{p // 12}.png"), np.vstack(filas[p:p + 12]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--detectar", action="store_true", help="solo mostrar los cambios de tablero detectados")
    args = ap.parse_args()

    if args.detectar:
        print("Cambios grandes de tablero (s):", detectar_cambios(args.video))
        print("Cada uno es un paso de nivel; revisarlos a ojo y guardar los inicios en inicios.json")
        return

    # Cuadro (aproximado) donde empieza cada nivel, revisado a ojo a partir de --detectar
    inicios = {int(n): fr for n, fr in json.load(open(os.path.join(AQUI, "inicios.json"))).items()}
    os.makedirs(os.path.join(SALIDA, "niveles"), exist_ok=True)
    v = cv2.VideoCapture(args.video)
    celdas = []  # (nivel, fila, col, imagen)
    for n, fr in sorted(inicios.items()):
        _, f = primer_cuadro_quieto(v, fr)
        cv2.imwrite(os.path.join(SALIDA, "niveles", f"nivel_{n:02d}.png"), f)
        cs = cortar_celdas(f, FILAS, COLUMNAS)
        celdas += [(n, fi, c, cs[fi * COLUMNAS + c]) for fi in range(F0, F1) for c in range(COLUMNAS)]

    grupos = agrupar(celdas)
    print(f"{len(celdas)} casillas -> {len(grupos)} grupos")
    pickle.dump({"celdas": [(n, f, c) for n, f, c, _ in celdas], "grupos": grupos},
                open(os.path.join(SALIDA, "grupos.pkl"), "wb"))
    hojas_de_grupos(celdas, grupos)
    print("Hojas guardadas en", SALIDA, "-> etiquetar los grupos en etiquetas_grupos.py")


if __name__ == "__main__":
    main()

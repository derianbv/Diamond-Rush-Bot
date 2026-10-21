"""
Visión: capturar el tablero y decir qué hay en cada casilla.

Método (sin entrenamiento): "vecino más cercano" contra plantillas.
  1. Se corta cada casilla de la captura.
  2. Se le quita un margen (por si la grilla está corrida 1-2 píxeles) y se
     reduce a 16x16 píxeles. Ese vector de 16*16*3 números es su "huella".
  3. Se compara con la huella de cada plantilla guardada en plantillas/<etiqueta>/.
     La etiqueta de la plantilla más parecida gana.

Las plantillas se sacan en el MISMO computador donde se juega (herramienta
`etiquetar`), así no importa que los colores cambien entre pantallas.
"""
import glob
import os
import shutil
import time
from dataclasses import dataclass

import cv2
import mss
import numpy as np

import objetos
from config import CARPETA
from juego import JUGADOR

CARPETA_PLANTILLAS = os.path.join(CARPETA, "plantillas")
CARPETA_ASSETS = os.path.join(CARPETA, "assets")

ETIQUETAS = [
    "personaje", "personaje_con_llave", "casilla_vacia", "casilla_ocupada",
    "diamante", "llave", "puerta_objetivo_cerrada", "puerta_objetivo_abierta",
    "puerta_llave", "puas_inactivas", "puas_activas", "roca", "agujero",
    "agujero_con_roca", "boton", "boton_con_roca", "puerta_metalica",
    "puerta_metalica_abierta", "objetivo_ultimo_nivel",
]

# Sprites que ya estaban en assets/ -> etiqueta a la que corresponden
ASSETS_A_ETIQUETA = {
    "Player": "personaje", "floor": "casilla_vacia", "diamond": "diamante",
    "key": "llave", "keyDoor": "puerta_llave", "Rock": "roca", "Hole": "agujero",
    "UntriggeredSpikes": "puas_inactivas", "Lava": "casilla_ocupada",
    "wall1": "casilla_ocupada", "wall2": "casilla_ocupada", "wall3": "casilla_ocupada",
    "wall4": "casilla_ocupada", "wall5": "casilla_ocupada",
}

TAM = 16       # lado de la huella
MARGEN = 0.12  # fracción de la casilla que se recorta en cada borde


def huella(celda):
    h, w = celda.shape[:2]
    my, mx = int(h * MARGEN), int(w * MARGEN)
    interior = celda[my:h - my, mx:w - mx]
    peq = cv2.resize(interior, (TAM, TAM), interpolation=cv2.INTER_AREA)
    return peq.astype(np.float32).ravel()


def cortar_celdas(img, filas, columnas):
    """Devuelve la lista de casillas (fila por fila). Usa bordes con decimales
    para que el error de redondeo no se acumule hacia la derecha/abajo."""
    alto, ancho = img.shape[:2]
    celdas = []
    for f in range(filas):
        y1, y2 = round(f * alto / filas), round((f + 1) * alto / filas)
        for c in range(columnas):
            x1, x2 = round(c * ancho / columnas), round((c + 1) * ancho / columnas)
            celdas.append(img[y1:y2, x1:x2])
    return celdas


class Capturador:
    def __init__(self, roi):
        self.sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
        x, y, w, h = roi
        self.region = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}

    def capturar(self):
        img = np.asarray(self.sct.grab(self.region))
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def capturar_monitor(indice=1):
    sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
    mon = sct.monitors[indice]
    img = cv2.cvtColor(np.asarray(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
    return img, (mon["left"], mon["top"])


@dataclass
class Lectura:
    etiquetas: list          # filas x columnas de strings
    distancias: np.ndarray   # (filas, columnas): qué tan parecida a su plantilla
    jugador: int             # índice de la casilla del jugador (-1 si no se ve)
    dist_jugador: float
    con_llave: bool

    def texto(self):
        from juego import SIMBOLO
        return "\n".join("".join(SIMBOLO.get(e, "?") for e in fila) for fila in self.etiquetas)


def sembrar_plantillas():
    """Si plantillas/ está vacía, copia los sprites de assets/ como punto de partida."""
    if glob.glob(os.path.join(CARPETA_PLANTILLAS, "*", "*.png")):
        return
    if os.path.exists(os.path.join(CARPETA_PLANTILLAS, ".sin_semilla")):
        return  # el usuario decidió empezar de cero
    for ruta in glob.glob(os.path.join(CARPETA_ASSETS, "*.png")):
        nombre = os.path.splitext(os.path.basename(ruta))[0]
        etiqueta = ASSETS_A_ETIQUETA.get(nombre)
        if etiqueta:
            destino = os.path.join(CARPETA_PLANTILLAS, etiqueta)
            os.makedirs(destino, exist_ok=True)
            shutil.copy(ruta, os.path.join(destino, f"asset_{nombre}.png"))
    print("[i] Plantillas iniciales copiadas desde assets/")


def guardar_plantilla(etiqueta, celda):
    destino = os.path.join(CARPETA_PLANTILLAS, etiqueta)
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, f"{time.time_ns()}.png")
    cv2.imwrite(ruta, celda)
    return ruta


class Clasificador:
    """La grilla en pantalla es de `filas` x `columnas` (con bordes y HUD).
    Solo se analiza el `area` efectiva del tablero: [fila0, col0, n_filas, n_cols].
    Todo lo de afuera es borde/HUD y se considera pared."""

    def __init__(self, filas, columnas, umbral, area=None):
        self.filas, self.columnas, self.umbral = filas, columnas, umbral
        self.area = list(area) if area else [0, 0, filas, columnas]
        f0, c0, nf, nc = self.area
        self.filas_area, self.cols_area = nf, nc
        # índice en la grilla completa de cada casilla del área (fila por fila)
        self.indices_area = [(f0 + f) * columnas + (c0 + c) for f in range(nf) for c in range(nc)]
        sembrar_plantillas()
        self.cargar()

    def en_area(self, fila, col):
        """(fila, col) de la grilla completa -> (fila, col) del área, o None si es borde."""
        f0, c0, nf, nc = self.area
        f, c = fila - f0, col - c0
        return (f, c) if 0 <= f < nf and 0 <= c < nc else None

    def celdas_area(self, img):
        todas = cortar_celdas(img, self.filas, self.columnas)
        return [todas[i] for i in self.indices_area]

    def cargar(self):
        extra = objetos.cargar()
        huellas, etiquetas, nombres = [], [], []
        for nombre in ETIQUETAS + list(extra):
            base = objetos.base_de(nombre, extra)  # el comportamiento (para el juego)
            for ruta in glob.glob(os.path.join(CARPETA_PLANTILLAS, nombre, "*.png")):
                img = cv2.imread(ruta, cv2.IMREAD_COLOR)
                if img is not None:
                    huellas.append(huella(img))
                    etiquetas.append(base)
                    nombres.append(nombre)
        if not huellas:
            raise RuntimeError("No hay plantillas en plantillas/. Usa `python agente.py etiquetar`.")
        self.T = np.stack(huellas)
        self.T2 = (self.T ** 2).sum(1)
        self.etiquetas_t = np.array(etiquetas)
        self.es_jugador = np.isin(self.etiquetas_t, JUGADOR)
        self.hay_con_llave = "personaje_con_llave" in etiquetas
        self.conteo = {n: nombres.count(n) for n in ETIQUETAS + list(extra)}

    def distancias(self, img):
        """Matriz (casillas del área x plantillas) con la distancia RMS entre huellas.
        Se calcula con álgebra: |a-b|² = |a|² + |b|² - 2·a·b (muy rápido)."""
        F = np.stack([huella(c) for c in self.celdas_area(img)])
        d2 = (F ** 2).sum(1)[:, None] + self.T2[None, :] - 2.0 * F @ self.T.T
        return np.sqrt(np.maximum(d2, 0) / F.shape[1])

    def clasificar(self, img):
        """Devuelve la Lectura del área efectiva (n_filas x n_cols)."""
        D = self.distancias(img)
        mejor = D.argmin(1)
        dist = D[np.arange(len(D)), mejor]
        etiquetas = self.etiquetas_t[mejor].tolist()

        # El jugador es la casilla que más se parece a alguna plantilla de jugador.
        jugador, dist_j, con_llave = -1, float("inf"), False
        if self.es_jugador.any():
            Dj = D[:, self.es_jugador]
            por_celda = Dj.min(1)
            jugador = int(por_celda.argmin())
            dist_j = float(por_celda[jugador])
            et_j = self.etiquetas_t[self.es_jugador][Dj[jugador].argmin()]
            con_llave = et_j == "personaje_con_llave"
            if dist_j > 2 * self.umbral:
                jugador = -1  # no hay nada parecido al jugador en pantalla
            else:
                etiquetas[jugador] = et_j

        for i in range(len(etiquetas)):
            if dist[i] > self.umbral and i != jugador:
                etiquetas[i] = "desconocido"
            elif etiquetas[i] in JUGADOR and i != jugador:
                etiquetas[i] = "desconocido"

        nf, nc = self.filas_area, self.cols_area
        grid = [etiquetas[f * nc:(f + 1) * nc] for f in range(nf)]
        return Lectura(grid, dist.reshape(nf, nc), jugador, dist_j, con_llave)

    def puntaje_alineacion(self, img):
        """Promedio de la distancia a la plantilla más cercana: entre más bajo,
        mejor está alineada la grilla. Lo usa el auto-ajuste de `calibrar`."""
        return float(self.distancias(img).min(1).mean())


def crear_clasificador(cfg):
    return Clasificador(cfg["filas"], cfg["columnas"], cfg["umbral_desconocido"], cfg.get("area"))

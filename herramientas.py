"""
Herramientas interactivas (ventanas de OpenCV):

  calibrar  -> marcar dónde está el tablero en la pantalla y ajustar la grilla.
  etiquetar -> enseñarle al agente cómo se ve cada objeto en ESTE computador.
"""
import os
import time

import cv2
import numpy as np

import config
import objetos
from controles import minimizar, restaurar
from juego import SIMBOLO
from vision import Capturador, capturar_monitor, cortar_celdas, crear_clasificador, guardar_plantilla


def _etiquetable(clf, f, c):
    """Se puede etiquetar el tablero efectivo y el anillo de borde que lo rodea
    (sirve como ejemplo de pared o de puertas). El título de arriba no."""
    f0, c0, nf, nc = clf.area
    return f0 - 1 <= f <= f0 + nf and c0 - 1 <= c <= c0 + nc and 0 <= f < clf.filas and 0 <= c < clf.columnas


def dibujar_overlay(img, lectura, clf, escala, seleccion=()):
    """Dibuja la grilla completa. Los bordes/HUD se oscurecen; el tablero
    efectivo (área) lleva un marco celeste y la etiqueta de cada casilla.
    `seleccion` son casillas (fila, col) de la grilla completa."""
    filas, columnas = clf.filas, clf.columnas
    f0, c0, nf, nc = clf.area
    vis = cv2.resize(img, None, fx=escala, fy=escala, interpolation=cv2.INTER_NEAREST)
    H, W = vis.shape[:2]

    def X(c):
        return round(c * W / columnas)

    def Y(f):
        return round(f * H / filas)

    for f in range(filas):
        for c in range(columnas):
            if clf.en_area(f, c) is None:
                # borde: se ignora al jugar (más oscuro lo que ni siquiera se puede etiquetar)
                vis[Y(f):Y(f + 1), X(c):X(c + 1)] //= 2 if _etiquetable(clf, f, c) else 4
    for f in range(filas + 1):
        cv2.line(vis, (0, Y(f)), (W, Y(f)), (255, 255, 255), 1)
    for c in range(columnas + 1):
        cv2.line(vis, (X(c), 0), (X(c), H), (255, 255, 255), 1)
    cv2.rectangle(vis, (X(c0), Y(f0)), (X(c0 + nc), Y(f0 + nf)), (255, 255, 0), 2)
    if lectura is not None:
        for f in range(nf):
            for c in range(nc):
                et = lectura.etiquetas[f][c]
                color = (0, 0, 255) if et == "desconocido" else (0, 255, 0)
                if f * nc + c == lectura.jugador:
                    color = (255, 200, 0)
                x, y = X(c0 + c), Y(f0 + f)
                texto = SIMBOLO.get(et, "?")
                cv2.putText(vis, texto, (x + 3, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3)
                cv2.putText(vis, texto, (x + 3, y + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1)
    for (f, c) in seleccion:
        cv2.rectangle(vis, (X(c) + 1, Y(f) + 1), (X(c + 1) - 2, Y(f + 1) - 2), (0, 255, 255), 3)
    return vis


def pitido():
    try:
        import winsound
        winsound.Beep(880, 250)
    except Exception:
        print("\a", end="")


def al_frente(ventana, img, dejar_encima=True):
    """Muestra la ventana y la pone delante de todas (si no, puede quedar
    escondida detrás del navegador)."""
    cv2.imshow(ventana, img)
    cv2.waitKey(1)
    try:
        cv2.setWindowProperty(ventana, cv2.WND_PROP_TOPMOST, 1)
        if not dejar_encima:
            cv2.waitKey(1)
            cv2.setWindowProperty(ventana, cv2.WND_PROP_TOPMOST, 0)
    except Exception:
        pass


def con_letrero(img, lineas, alto, tam=0.6):
    """Agrega una franja negra arriba de la imagen con instrucciones en amarillo."""
    franja = np.zeros((alto, img.shape[1], 3), dtype=img.dtype)
    paso = alto // max(1, len(lineas))
    for k, texto in enumerate(lineas):
        cv2.putText(franja, texto, (8, paso * k + paso - 10), cv2.FONT_HERSHEY_SIMPLEX, tam, (0, 255, 255), 1,
                    cv2.LINE_AA)
    return np.vstack([franja, img])


def _recortar(pantalla, roi):
    x, y, w, h = roi
    return pantalla[round(y):round(y + h), round(x):round(x + w)]


def _roi_valida(pantalla, roi):
    x, y, w, h = roi
    return x >= 0 and y >= 0 and w > 20 and h > 20 and x + w <= pantalla.shape[1] and y + h <= pantalla.shape[0]


def auto_ajustar(pantalla, roi, clf):
    """Busca el corrimiento/tamaño de la grilla que hace que las casillas se
    parezcan más a las plantillas (búsqueda local por coordenadas)."""
    def puntaje(r):
        return clf.puntaje_alineacion(_recortar(pantalla, r)) if _roi_valida(pantalla, r) else float("inf")

    mejor, mejor_p = list(roi), puntaje(roi)
    for _ in range(3):
        x, y, w, h = mejor
        candidatos = [[x + dx, y + dy, w, h] for dx in range(-4, 5) for dy in range(-4, 5)]
        candidatos += [[x, y, w + dw, h + dh] for dw in range(-6, 7) for dh in range(-6, 7)]
        anterior = mejor_p
        for r in candidatos:
            p = puntaje(r)
            if p < mejor_p:
                mejor, mejor_p = r, p
        if mejor_p >= anterior:
            break
    return mejor, mejor_p


def calibrar(cfg):
    filas, columnas = cfg["filas"], cfg["columnas"]
    print("En 3 segundos tomo una captura de la pantalla. Ve al juego y déjalo visible (sin tapar).")
    print("Vas a escuchar un pitido cuando la captura esté tomada.")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)
    pantalla, (ox, oy) = capturar_monitor(cfg["monitor"])
    pitido()
    print("¡Captura tomada! Se abrió una ventana con la captura (tiene un letrero amarillo arriba).")

    esc = min(1.0, 1500 / pantalla.shape[1], 800 / pantalla.shape[0])
    vista = cv2.resize(pantalla, None, fx=esc, fy=esc) if esc < 1 else pantalla.copy()
    alto_letrero = 70
    vista = con_letrero(vista, [
        "ESTA ES UNA FOTO DE TU PANTALLA.",
        f"Arrastra un rectangulo sobre TODO el juego ({columnas}x{filas} casillas), INCLUYENDO el titulo y botones de arriba. ENTER = listo, C = cancelar",
    ], alto_letrero)
    print(f"Selecciona TODO el juego ({columnas} columnas x {filas} filas), incluyendo el título y los botones de arriba.")
    ventana_sel = "Selecciona el tablero"
    cv2.namedWindow(ventana_sel, cv2.WINDOW_AUTOSIZE)
    al_frente(ventana_sel, vista)
    x, y, w, h = cv2.selectROI(ventana_sel, vista, showCrosshair=False)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        print("Cancelado.")
        return
    y -= alto_letrero  # el letrero agregó una franja arriba de la imagen
    if y < 0:
        h += y
        y = 0
    roi = [x / esc, y / esc, w / esc, h / esc]

    clf = crear_clasificador(cfg)
    print("""
Ajuste fino de la grilla (las líneas blancas deben caer justo en los bordes de las casillas):
  w a s d : mover 1 px       W A S D : mover 5 px
  j / l   : más angosto / más ancho      i / k : más bajo / más alto
  f       : auto-ajuste con las plantillas
  ENTER   : guardar          ESC : cancelar""")
    ventana = "Ajuste de grilla"
    primera = True
    while True:
        recorte = _recortar(pantalla, roi)
        lectura = clf.clasificar(recorte)
        escala = min(2.0, 700 / recorte.shape[0])
        vis = dibujar_overlay(recorte, lectura, clf, escala)
        vis = con_letrero(vis, ["Lineas blancas = bordes de casillas",
                                f"Marco celeste = tablero efectivo {clf.cols_area}x{clf.filas_area}",
                                "f auto | wasd mover | j/l ancho | i/k alto",
                                "ENTER guardar | ESC cancelar"], 80, tam=0.45)
        if primera:
            cv2.namedWindow(ventana, cv2.WINDOW_AUTOSIZE)
            al_frente(ventana, vis)
            primera = False
        cv2.imshow(ventana, vis)
        k = cv2.waitKey(0) & 0xFF
        paso = 5 if chr(k).isupper() else 1
        nuevo = list(roi)
        if k == 27:
            print("Cancelado.")
            break
        if k in (13, 10):
            cfg["roi"] = [round(roi[0] + ox), round(roi[1] + oy), round(roi[2]), round(roi[3])]
            config.guardar(cfg)
            print(f"Guardado en config.json: roi = {cfg['roi']} "
                  f"(casilla ≈ {roi[2] / columnas:.1f} x {roi[3] / filas:.1f} px)")
            break
        c = chr(k).lower()
        if c == "a": nuevo[0] -= paso
        elif c == "d": nuevo[0] += paso
        elif c == "w": nuevo[1] -= paso
        elif c == "s": nuevo[1] += paso
        elif c == "j": nuevo[2] -= paso
        elif c == "l": nuevo[2] += paso
        elif c == "i": nuevo[3] -= paso
        elif c == "k": nuevo[3] += paso
        elif c == "f":
            nuevo, p = auto_ajustar(pantalla, roi, clf)
            print(f"  auto-ajuste: {[round(v) for v in nuevo]}  (puntaje {p:.1f}, menor es mejor)")
        if _roi_valida(pantalla, nuevo):
            roi = nuevo
    cv2.destroyAllWindows()


IMPORTANTES = ("personaje", "casilla_vacia", "casilla_ocupada", "diamante", "puerta_objetivo_cerrada")
ANCHO_PANEL = 270


def dibujar_panel(alto, clf, teclas, n_sel, mensaje, alerta):
    """Panel lateral con las teclas y cuántos ejemplos hay de cada objeto."""
    panel = np.full((alto, ANCHO_PANEL, 3), 30, dtype=np.uint8)
    y = 18
    extra = objetos.cargar()

    def linea(texto, color=(220, 220, 220), tam=0.42):
        nonlocal y
        cv2.putText(panel, texto, (6, y), cv2.FONT_HERSHEY_SIMPLEX, tam, color, 1, cv2.LINE_AA)
        y += 17

    linea("1) CLIC en casillas  2) TECLA", (0, 255, 255), 0.45)
    linea(f"   seleccionadas: {n_sel}", (0, 255, 255) if n_sel else (150, 150, 150))
    for tecla, nombre in teclas.items():
        if tecla in objetos.ALIAS:
            continue
        n = clf.conteo.get(nombre, 0)
        color = (90, 90, 255) if n == 0 and nombre in IMPORTANTES else (120, 220, 120) if n else (160, 160, 160)
        linea(f"{tecla}  {objetos.nombre_corto(nombre, extra)[:28]} [{n}]", color)
    linea("#  pared      .  suelo", (200, 200, 120))
    linea("ENTER: elegir de la LISTA COMPLETA", (0, 255, 255))
    linea("n: crear objeto nuevo", (0, 255, 255))
    linea("r: REVISAR / borrar ejemplos malos", (0, 255, 255))
    y += 3
    for texto in ("clic der: limpiar seleccion", "ESPACIO: nueva captura", "v: en vivo on/off   u: deshacer",
                  "p: guardar captura   ESC: salir"):
        linea(texto)
    y += 3
    for parte in alerta:
        linea(parte, (60, 60, 255), 0.45)
    for parte in mensaje:
        linea(parte, (0, 255, 255), 0.45)
    return panel


def _texto_alerta(lectura):
    """Si la mayoría de casillas no se parecen a nada conocido, seguramente
    otra ventana está tapando el juego (con el juego visible la mediana ≈ 8)."""
    if float(np.median(lectura.distancias)) > 25:
        return ["NO RECONOZCO EL JUEGO.", "Esta tapado por otra", "ventana? Despejalo y", "presiona ESPACIO."]
    return []


def etiquetar(cfg, consola=None):
    if not cfg.get("roi"):
        print("Primero ejecuta: python agente.py calibrar")
        return
    cap = Capturador(cfg["roi"])
    clf = crear_clasificador(cfg)
    teclas = objetos.todas_las_teclas()
    print("Herramienta de etiquetado abierta (las instrucciones están en la ventana).")

    # Tamaño y posición de la ventana: al lado del juego, sin taparlo.
    x, y, w, h = cfg["roi"]
    try:
        import ctypes
        ancho_pantalla = ctypes.windll.user32.GetSystemMetrics(0)
    except Exception:
        ancho_pantalla = 1920
    espacio_der = ancho_pantalla - (x + w) - 20
    espacio_izq = x - 20
    espacio = max(espacio_der, espacio_izq)
    escala = max(0.6, min(2.0, 700 / h, (espacio - ANCHO_PANEL) / w))
    ancho_ventana = int(w * escala) + ANCHO_PANEL
    pos_x = x + w + 20 if espacio_der >= espacio_izq else max(0, x - 20 - ancho_ventana)

    ventana = "Etiquetar"
    cv2.namedWindow(ventana, cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow(ventana, int(pos_x), int(max(0, y - 30)))

    estado = {"img": cap.capturar(), "sel": set(), "en_vivo": False, "ultimo": [],
              "mensaje": ["Listo. Haz clic en casillas."]}
    estado["lectura"] = clf.clasificar(estado["img"])

    def mouse(evento, mx, my, flags, _):
        H, W = estado["img"].shape[0] * escala, estado["img"].shape[1] * escala
        if evento == cv2.EVENT_LBUTTONDOWN and mx < W:
            celda = (int(my / (H / clf.filas)), int(mx / (W / clf.columnas)))
            if not _etiquetable(clf, *celda):
                estado["mensaje"] = ["Eso es el titulo/botones:", "no se etiqueta."]
                return
            estado["sel"].symmetric_difference_update({celda})
        elif evento == cv2.EVENT_RBUTTONDOWN:
            estado["sel"].clear()

    def capturar():
        estado["img"] = cap.capturar()
        estado["lectura"] = clf.clasificar(estado["img"])

    def componer():
        tablero = dibujar_overlay(estado["img"], estado["lectura"], clf, escala, estado["sel"])
        panel = dibujar_panel(tablero.shape[0], clf, teclas, len(estado["sel"]), estado["mensaje"],
                              _texto_alerta(estado["lectura"]))
        return np.hstack([tablero, panel])

    def guardar(nombre):
        celdas = cortar_celdas(estado["img"], clf.filas, clf.columnas)
        estado["ultimo"] = [guardar_plantilla(nombre, celdas[f * clf.columnas + c]) for f, c in estado["sel"]]
        n = len(estado["ultimo"])
        estado["mensaje"] = [f"GUARDADO: {n} ejemplo(s) de", objetos.nombre_corto(nombre)[:30], "(u = deshacer)"]
        print(f"Guardados {n} ejemplos de '{nombre}'")
        estado["sel"].clear()
        clf.cargar()
        estado["lectura"] = clf.clasificar(estado["img"])

    def en_consola(funcion):
        """Muestra la consola para que el usuario escriba, y luego vuelve."""
        estado["mensaje"] = ["RESPONDE EN LA CONSOLA", "(la ventana negra)"]
        cv2.imshow(ventana, componer())
        cv2.waitKey(1)
        restaurar(consola)
        print("\n(La ventana 'Etiquetar' sigue abierta: responde aquí y luego vuelve a ella.)")
        resultado = funcion()
        minimizar(consola)
        al_frente(ventana, componer(), dejar_encima=False)
        return resultado

    cv2.setMouseCallback(ventana, mouse)
    al_frente(ventana, componer(), dejar_encima=False)
    pitido()
    while True:
        if estado["en_vivo"]:
            capturar()
        cv2.imshow(ventana, componer())
        k = cv2.waitKey(60) & 0xFF
        if k == 255:
            continue
        if k == 27:
            break
        ch = chr(k)
        if k == 32:
            capturar()
            estado["mensaje"] = ["Nueva captura tomada."]
        elif k in (13, 10):
            if not estado["sel"]:
                estado["mensaje"] = ["Primero haz clic en", "una o varias casillas."]
                continue
            nombre = en_consola(objetos.elegir_de_lista)
            teclas = objetos.todas_las_teclas()
            clf.cargar()
            if nombre:
                guardar(nombre)
            else:
                estado["mensaje"] = ["Cancelado."]
        elif ch == "n":
            nombre = en_consola(objetos.crear_interactivo)
            teclas = objetos.todas_las_teclas()
            clf.cargar()
            if nombre:
                tecla = next(t for t, n in teclas.items() if n == nombre)
                if estado["sel"]:
                    guardar(nombre)
                else:
                    estado["mensaje"] = [f"Creado '{nombre[:20]}'", f"Tecla: {tecla}"]
            else:
                estado["mensaje"] = ["Cancelado."]
        elif ch == "r":
            revisar_ejemplos()
            clf.cargar()
            estado["lectura"] = clf.clasificar(estado["img"])
            estado["mensaje"] = ["Ejemplos revisados."]
            al_frente(ventana, componer(), dejar_encima=False)
        elif ch == "v":
            estado["en_vivo"] = not estado["en_vivo"]
            estado["mensaje"] = ["Modo en vivo: " + ("ON" if estado["en_vivo"] else "OFF")]
        elif ch == "p":
            os.makedirs(os.path.join(config.CARPETA, "capturas"), exist_ok=True)
            ruta = os.path.join(config.CARPETA, "capturas", f"tablero_{time.strftime('%H%M%S')}.png")
            cv2.imwrite(ruta, estado["img"])
            estado["mensaje"] = ["Captura guardada en", "capturas/"]
        elif ch == "u":
            for ruta in estado["ultimo"]:
                if os.path.exists(ruta):
                    os.remove(ruta)
            estado["mensaje"] = [f"Borrados {len(estado['ultimo'])} ejemplos."]
            estado["ultimo"] = []
            clf.cargar()
            estado["lectura"] = clf.clasificar(estado["img"])
        elif ch in teclas:
            if estado["sel"]:
                guardar(teclas[ch])
            else:
                estado["mensaje"] = ["Primero haz clic en", "una o varias casillas."]
        else:
            estado["mensaje"] = [f"La tecla '{ch}' no hace nada.", "ENTER = lista completa"]
    cv2.destroyAllWindows()


def revisar_ejemplos():
    """Galería de todos los ejemplos guardados, para encontrar y borrar los
    mal etiquetados. Los borrados se mueven a plantillas_descartadas/."""
    import glob
    import shutil
    from vision import CARPETA_PLANTILLAS
    TAM, COLS, FILAS_PAG, ALTO_TXT, ALTO_CAB = 72, 12, 7, 16, 48
    por_pagina = COLS * FILAS_PAG

    def cargar_items():
        extra = objetos.cargar()
        return [(n, r) for n in list(objetos.BASE) + list(extra)
                for r in sorted(glob.glob(os.path.join(CARPETA_PLANTILLAS, n, "*.png")))]

    estado = {"items": cargar_items(), "marcados": set(), "pagina": 0, "mensaje": ""}
    ventana = "Revisar ejemplos"

    def componer():
        items, pag = estado["items"], estado["pagina"]
        paginas = max(1, (len(items) + por_pagina - 1) // por_pagina)
        lienzo = np.full((ALTO_CAB + FILAS_PAG * (TAM + ALTO_TXT), COLS * TAM, 3), 25, np.uint8)
        cab = ["Clic = marcar/desmarcar  |  b = BORRAR marcados  |  a/d = pagina  |  ESC = volver",
               f"Pagina {pag + 1}/{paginas}   marcados: {len(estado['marcados'])}   {estado['mensaje']}"]
        for k, t in enumerate(cab):
            cv2.putText(lienzo, t, (6, 18 + 20 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
        for j, (nombre, ruta) in enumerate(items[pag * por_pagina:(pag + 1) * por_pagina]):
            f, c = divmod(j, COLS)
            x, y = c * TAM, ALTO_CAB + f * (TAM + ALTO_TXT)
            img = cv2.imread(ruta)
            if img is not None:
                lienzo[y:y + TAM, x:x + TAM] = cv2.resize(img, (TAM, TAM), interpolation=cv2.INTER_AREA)
            cv2.putText(lienzo, objetos.nombre_corto(nombre).lstrip("*")[:11], (x + 2, y + TAM + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.36, (120, 220, 120), 1, cv2.LINE_AA)
            if ruta in estado["marcados"]:
                cv2.line(lienzo, (x + 4, y + 4), (x + TAM - 4, y + TAM - 4), (0, 0, 255), 3)
                cv2.line(lienzo, (x + TAM - 4, y + 4), (x + 4, y + TAM - 4), (0, 0, 255), 3)
        return lienzo

    def mouse(evento, mx, my, flags, _):
        if evento != cv2.EVENT_LBUTTONDOWN or my < ALTO_CAB:
            return
        f, c = (my - ALTO_CAB) // (TAM + ALTO_TXT), mx // TAM
        j = estado["pagina"] * por_pagina + f * COLS + c
        if c < COLS and f < FILAS_PAG and j < len(estado["items"]):
            estado["marcados"].symmetric_difference_update({estado["items"][j][1]})

    cv2.namedWindow(ventana, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(ventana, mouse)
    al_frente(ventana, componer(), dejar_encima=False)
    while True:
        cv2.imshow(ventana, componer())
        k = cv2.waitKey(60) & 0xFF
        if k == 27:
            break
        paginas = max(1, (len(estado["items"]) + por_pagina - 1) // por_pagina)
        if k == ord("a"):
            estado["pagina"] = max(0, estado["pagina"] - 1)
        elif k == ord("d"):
            estado["pagina"] = min(paginas - 1, estado["pagina"] + 1)
        elif k == ord("b") and estado["marcados"]:
            for ruta in estado["marcados"]:
                destino = os.path.join(config.CARPETA, "plantillas_descartadas",
                                       os.path.basename(os.path.dirname(ruta)))
                os.makedirs(destino, exist_ok=True)
                shutil.move(ruta, os.path.join(destino, os.path.basename(ruta)))
            estado["mensaje"] = f"Borrados {len(estado['marcados'])} (copia en plantillas_descartadas/)"
            print(estado["mensaje"])
            estado["marcados"].clear()
            estado["items"] = cargar_items()
            estado["pagina"] = min(estado["pagina"], max(0, (len(estado["items"]) - 1) // por_pagina))
    cv2.destroyWindow(ventana)

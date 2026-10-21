"""
Asistente para preparar y lanzar el agente.
Ejecutar con doble clic en INICIAR.bat (o: .venv\\Scripts\\python asistente.py)

Al abrir muestra un menú. Lo normal es JUGAR con los datos ya guardados
(calibración en config.json y ejemplos en plantillas/). Re-entrenar o
re-calibrar son opciones aparte, solo cuando hace falta.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser

CARPETA = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
URL_JUEGO = "https://www.minijuegos.com/juego/diamond-rush"

os.system("")  # activa los colores ANSI en la consola de Windows
AZUL, VERDE, AMARILLO, ROJO, NEGRITA, FIN = "\033[96m", "\033[92m", "\033[93m", "\033[91m", "\033[1m", "\033[0m"

IMPORTANTES = ["personaje", "casilla_vacia", "casilla_ocupada", "diamante", "puerta_objetivo_cerrada"]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def titulo(n, total, texto):
    print(f"\n{AZUL}{'=' * 64}\n {NEGRITA}PASO {n}/{total}: {texto}{FIN}\n{AZUL}{'=' * 64}{FIN}")


def info(texto):
    print(texto.strip("\n"))


def preguntar(texto, opciones="sn", defecto="s"):
    """Pregunta hasta recibir una de las opciones. ENTER = opción por defecto."""
    etiquetas = "/".join(o.upper() if o == defecto else o for o in opciones)
    while True:
        r = input(f"{AMARILLO}{texto} [{etiquetas}]: {FIN}").strip().lower() or defecto
        if r in opciones:
            return r
        print(f"  Responde una de: {', '.join(opciones)}")


def ejecutar(*args):
    print(f"{AZUL}> python {' '.join(args)}{FIN}\n")
    r = subprocess.run([PY, *args], cwd=CARPETA)
    print()
    return r.returncode == 0


def cargar_config():
    ruta = os.path.join(CARPETA, "config.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return {}


def objetos_creados():
    ruta = os.path.join(CARPETA, "objetos.json")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return {}


def contar_plantillas():
    """nombre del objeto -> cantidad de ejemplos guardados."""
    conteo = {}
    for carpeta in glob.glob(os.path.join(CARPETA, "plantillas", "*")):
        if os.path.isdir(carpeta):
            conteo[os.path.basename(carpeta)] = len(glob.glob(os.path.join(carpeta, "*.png")))
    return conteo


def faltantes():
    """Objetos obligatorios sin ningún ejemplo (los objetos creados por el
    usuario cuentan para el objeto base al que se parecen)."""
    conteo = contar_plantillas()
    cubiertos = {n for n, k in conteo.items() if k}
    cubiertos |= {d["como"] for n, d in objetos_creados().items() if conteo.get(n)}
    return [et for et in IMPORTANTES if et not in cubiertos]


def mostrar_plantillas():
    conteo = contar_plantillas()
    extra = objetos_creados()
    falta = faltantes()
    print("\nEjemplos guardados por objeto:")
    for nombre in sorted(conteo, key=lambda n: (n in extra, n)):
        n = conteo[nombre]
        color = VERDE if n else (ROJO if nombre in falta else "")
        nota = f"  (objeto tuyo, se comporta como {extra[nombre]['como']})" if nombre in extra else ""
        print(f"  {color}{nombre:26s} {n}{FIN}{nota}")
    for nombre in falta:
        if nombre not in conteo:
            print(f"  {ROJO}{nombre:26s} 0{FIN}")
    if falta:
        print(f"{ROJO}Faltan objetos obligatorios: {', '.join(falta)}{FIN}")


# ---------------------------------------------------------------------------
# Pasos. Cada uno devuelve "siguiente", "repetir", "menu" o
# otro paso (función) al que ir.
# ---------------------------------------------------------------------------
def paso_entorno():
    info("Reviso que estén instaladas las librerías (OpenCV, NumPy, mss)\n"
         "y corro las pruebas de las reglas del juego y del A*.")
    if preguntar("¿Empezamos?") == "n":
        return "siguiente"
    faltan = subprocess.run([PY, "-c", "import cv2, numpy, mss"], cwd=CARPETA).returncode != 0
    if faltan:
        print(f"{ROJO}Faltan librerías.{FIN}")
        if preguntar("¿Las instalo ahora? (necesita internet)") == "s":
            ejecutar("-m", "pip", "install", "-r", "requirements.txt")
        return "repetir"
    print(f"{VERDE}Librerías OK.{FIN}")
    if not ejecutar("pruebas.py"):
        print(f"{ROJO}Las pruebas fallaron. Copia lo de arriba y pídeme ayuda.{FIN}")
        return "repetir" if preguntar("¿Reintentar?") == "s" else "siguiente"
    return "siguiente"


def paso_juego():
    info(f"""
1. Abre el juego en el navegador: {URL_JUEGO}
2. Pon el zoom del navegador en 100% (Ctrl + 0).
3. Entra a un nivel y deja el juego COMPLETO visible (también el título de arriba).
4. A partir de aquí NO muevas ni cambies el tamaño de la ventana del navegador
   ni hagas scroll en la página.
   No te preocupes por esta consola: se minimiza sola cuando el agente mira la pantalla.""")
    if preguntar("¿Abro el juego en el navegador por ti?", defecto="n") == "s":
        webbrowser.open(URL_JUEGO)
    preguntar("¿Ya está el juego visible y la ventana en su lugar?", "s", "s")
    return "siguiente"


def paso_listo_para_jugar():
    cfg = cargar_config()
    info("""
Uso los datos guardados (calibración + ejemplos). Antes de jugar:
  * El juego debe estar en el MISMO lugar de la pantalla que cuando calibraste
    (misma ventana, mismo zoom, sin scroll). Si lo moviste, usa 'Re-calibrar'.
  * El nivel debe estar listo en pantalla.""")
    print(f"  Tablero guardado en pantalla: x={cfg['roi'][0]}, y={cfg['roi'][1]}, "
          f"ancho={cfg['roi'][2]}, alto={cfg['roi'][3]}")
    if preguntar("¿Revisar primero qué lee el agente (sin mover nada)?", defecto="n") == "s":
        return paso_ver
    return "siguiente"


def paso_calibrar():
    cfg = cargar_config()
    if cfg.get("roi"):
        print(f"Ya hay una calibración guardada: roi = {cfg['roi']}")
        if preguntar("¿Volver a calibrar? (solo si moviste la ventana o es otro computador)", defecto="n") == "n":
            return "siguiente"
    info("""
Qué va a pasar:
  1. Esta consola se MINIMIZA sola y en 3 segundos se toma una foto de la
     pantalla. Vas a escuchar un pitido.
  2. Se abre una ventana con esa foto (letrero amarillo arriba): arrastra un
     rectángulo sobre TODO el juego, INCLUYENDO el título y los botones de
     arriba (ajustes / reiniciar) y los bordes, de lado a lado. ENTER.
  3. Aparece la grilla blanca (10 x 15). Las líneas deben caer en los bordes
     de las casillas. El MARCO CELESTE es el tablero efectivo (8 x 11);
     lo de afuera (bordes y título) se oscurece y se ignora.
     Teclas (con la ventana activa):
        f        -> auto-ajuste (pruébalo primero)
        w a s d  -> mover 1 px   (en MAYÚSCULA, 5 px)
        j / l    -> más angosta / más ancha
        i / k    -> más baja / más alta
        ENTER    -> guardar      ESC -> cancelar""")
    if preguntar("¿Listo para calibrar?") == "n":
        return "siguiente"
    ejecutar("agente.py", "calibrar")
    if not cargar_config().get("roi"):
        print(f"{ROJO}No se guardó ninguna calibración.{FIN}")
        return "repetir"
    r = preguntar("¿El marco celeste quedó justo sobre las 8 x 11 casillas del tablero? (s = sí, r = repetir)", "sr")
    return "siguiente" if r == "s" else "repetir"


INSTRUCCIONES_ETIQUETAR = """
Cómo etiquetar:
  * Esta consola se minimiza. La ventana 'Etiquetar' aparece AL LADO del
    juego, con las teclas escritas a la derecha.
  * Solo se etiqueta DENTRO del marco celeste (bordes y título no cuentan).
  * Clic en una o varias casillas (quedan en amarillo) y presiona la tecla
    del objeto. Para paredes puedes usar '#' y para suelo '.'.
    TIP: selecciona VARIOS ejemplos de cada cosa (todas las paredes
    distintas, varios diamantes...): entre más ejemplos, menos errores.
  * Si algo no corresponde a ningún objeto de la lista, presiona 'n' para
    CREAR UN OBJETO NUEVO (eliges cómo se comporta: pared, suelo, etc.).
  * Juega a mano en el navegador para que aparezcan cosas nuevas (recoger
    una llave, pisar púas, mover al personaje a cada lado) y vuelve a la
    ventana 'Etiquetar' con ESPACIO para tomar una captura nueva.
  * Etiqueta al personaje mirando ARRIBA, ABAJO, IZQUIERDA y DERECHA.
  * ENTER con casillas seleccionadas = elegir el objeto de la LISTA COMPLETA.
  * 'r' = revisar y borrar ejemplos mal etiquetados (un clic equivocado
    puede hacer que el agente lea mal, p.ej. suelo como agujero).
  * Si dice "NO RECONOZCO EL JUEGO", algo lo está tapando.
  * ESC para terminar. La consola vuelve sola."""


def abrir_etiquetador():
    info(INSTRUCCIONES_ETIQUETAR)
    if preguntar("¿Abrir la herramienta de etiquetado?") == "s":
        ejecutar("agente.py", "etiquetar")


def paso_etiquetar():
    """Etiquetado dentro de la configuración completa (primera vez)."""
    info("""
Este es el "entrenamiento" del agente: le enseñas cómo se ve cada objeto.
SE HACE UNA SOLA VEZ: cada ejemplo queda guardado en la carpeta plantillas/
y se usa siempre. Para otro computador, copia la carpeta completa del proyecto.""")
    mostrar_plantillas()
    if not faltantes() and preguntar("\nYa tienes lo obligatorio. ¿Etiquetar más de todas formas?", defecto="n") == "n":
        return "siguiente"
    abrir_etiquetador()
    r = preguntar("¿Terminaste de etiquetar? (s = sí, r = seguir etiquetando)", "sr")
    return "siguiente" if r == "s" else "repetir"


def paso_reentrenar():
    """Menú de re-entrenamiento: agregar ejemplos, crear objetos o empezar de cero."""
    mostrar_plantillas()
    r = preguntar("\n¿Qué quieres hacer?\n"
                  "  e = etiquetar (agregar o corregir ejemplos)\n"
                  "  n = crear un objeto nuevo (algo que no está en la lista)\n"
                  "  r = revisar y borrar ejemplos mal etiquetados\n"
                  "  b = BORRAR todos los ejemplos y empezar de cero (se guarda una copia)\n"
                  "  v = volver al menú\n", "enrbv", "e")
    if r == "v":
        return "menu"
    if r == "n":
        ejecutar("-c", "import objetos; objetos.crear_interactivo()")
        return "repetir"
    if r == "r":
        info("Se abre una galería con todos los ejemplos. Haz clic en los que estén MAL\n"
             "(quedan con una X roja) y presiona 'b' para borrarlos. ESC para volver.")
        ejecutar("agente.py", "revisar")
        return "repetir"
    if r == "b":
        if preguntar(f"{ROJO}¿Seguro? Se moverán todos los ejemplos a una copia de respaldo{FIN}", defecto="n") == "s":
            origen = os.path.join(CARPETA, "plantillas")
            if os.path.isdir(origen):
                destino = os.path.join(CARPETA, f"plantillas_respaldo_{time.strftime('%Y%m%d_%H%M%S')}")
                shutil.move(origen, destino)
                print(f"{VERDE}Copia guardada en {destino}{FIN}")
            os.makedirs(origen, exist_ok=True)
            open(os.path.join(origen, ".sin_semilla"), "w").close()  # no volver a copiar assets/
        return "repetir"
    abrir_etiquetador()
    r = preguntar("¿Seguir re-entrenando? (s = volver a estas opciones, n = revisar la lectura)", "sn", "n")
    return "repetir" if r == "s" else "siguiente"


def paso_ver():
    info("""
El agente va a leer la pantalla e imprimir el tablero (8 x 11) tal como lo
entiende, y después calcula el plan. NO presiona ninguna tecla.
Compara el dibujo con lo que ves en el juego:
  P jugador  # pared  . suelo  D diamante  K llave  L puerta de llave
  ^ púas  X púas activas  R roca  O agujero  B botón  M puerta metálica
  E salida  ? desconocido""")
    preguntar("¿Está el nivel en pantalla y sin tapar?", "s")
    ejecutar("agente.py", "ver")
    r = preguntar("¿El tablero impreso coincide con el juego y encontró un plan?\n"
                  "  s = sí, seguir   e = no, re-entrenar (etiquetar)   r = leer de nuevo", "ser")
    return {"s": "siguiente", "e": paso_reentrenar, "r": "repetir"}[r]


def paso_probar():
    info("""
Prueba del teclado: el agente hace clic en el tablero para darle foco,
mueve al personaje una casilla y lo regresa a su lugar.
Debe decir 'llegó en 0.xxx s' en ambos movimientos.
OJO: tu personaje se va a mover (y volver). No toques el mouse ni el teclado.""")
    if preguntar("¿Hacer la prueba?") == "n":
        return "siguiente"
    ejecutar("agente.py", "probar")
    r = preguntar("¿Dijo 'llegó' en ambos movimientos? (s = sí, r = repetir, n = no funcionó)", "srn")
    if r == "n":
        info(f"""
{ROJO}El juego no está recibiendo las teclas o no ve al personaje.{FIN} Revisa:
  * que nada tape el juego
  * que el personaje esté etiquetado mirando en cada dirección
  * que la calibración siga bien (si moviste la ventana, recalibra)""")
        r2 = preguntar("¿Re-entrenar (e), recalibrar (c) o seguir igual (s)?", "ecs", "e")
        return {"e": paso_reentrenar, "c": paso_calibrar, "s": "siguiente"}[r2]
    return "siguiente" if r == "s" else "repetir"


def paso_jugar():
    info("""
¡A jugar! Cuando confirmes, el agente:
  1. minimiza esta consola y hace clic en el juego para darle foco
  2. lee el nivel y planifica (puede tardar unos segundos)
  3. juega solo; si algo sale distinto a lo esperado, re-planifica
No toques el mouse ni el teclado mientras juega.
Para detenerlo: abre esta consola y presiona Ctrl + C.""")
    continuo = preguntar("¿Seguir jugando automáticamente los niveles siguientes?", defecto="n") == "s"
    preguntar("¿El nivel está listo en pantalla? Al confirmar empieza a jugar", "s")
    try:
        ejecutar("agente.py", "jugar", *(["--continuo"] if continuo else []))
    except KeyboardInterrupt:
        print(f"\n{AMARILLO}Detenido.{FIN}")
    r = preguntar("¿Qué sigue?  j = jugar otro nivel   v = revisar lectura   m = volver al menú", "jvm", "j")
    return {"j": "repetir", "v": paso_ver, "m": "menu"}[r]


NOMBRE = {
    paso_entorno: "Revisar instalación", paso_juego: "Abrir el juego",
    paso_listo_para_jugar: "Preparar la partida", paso_calibrar: "Calibrar el tablero",
    paso_etiquetar: "Etiquetar objetos", paso_reentrenar: "Re-entrenar",
    paso_ver: "Revisar la lectura (sin jugar)", paso_probar: "Probar el teclado", paso_jugar: "Jugar",
}


def correr(secuencia):
    """Ejecuta los pasos en orden. Si un paso pide ir a otro: si ese otro
    está en la secuencia salta ahí; si no, lo ejecuta a continuación."""
    secuencia = list(secuencia)
    i = 0
    while i < len(secuencia):
        paso = secuencia[i]
        titulo(i + 1, len(secuencia), NOMBRE[paso])
        r = paso()
        if r == "menu":
            return
        if r == "siguiente":
            i += 1
        elif callable(r):
            if r in secuencia:
                i = secuencia.index(r)
            else:
                secuencia.insert(i + 1, r)
                i += 1
        # "repetir": se queda en el mismo paso


# ---------------------------------------------------------------------------
# Menú principal (una tecla por opción: pensado para el torneo, donde el
# tiempo importa). Las opciones de preparación usan los pasos guiados de arriba.
# ---------------------------------------------------------------------------
def leer_tecla(validas):
    """Lee UNA tecla sin necesidad de ENTER (en Windows)."""
    try:
        import msvcrt
        while True:
            ch = msvcrt.getwch().lower()
            if ch in validas:
                print(ch)
                return ch
    except ImportError:
        while True:
            ch = input().strip().lower()[:1]
            if ch in validas:
                return ch


def ejecutar_rapido(*args):
    try:
        ejecutar("agente.py", *args)
    except KeyboardInterrupt:
        print(f"\n{AMARILLO}Detenido.{FIN}")


OPCIONES = [
    ("1", "Jugar", "ve al juego y presiona F8 para empezar (F9 cancela)"),
    ("2", "Ver lectura", "qué ve el agente y su plan, sin mover nada"),
    ("3", "Probar teclado", "mueve al personaje 1 casilla y vuelve"),
    ("4", "Re-calibrar", "si moviste la ventana del navegador"),
    ("5", "Re-entrenar", "etiquetar o revisar ejemplos"),
    ("6", "Configuración completa", "primera vez u otro computador"),
    ("0", "Salir", ""),
]


def menu():
    cfg = cargar_config()
    calibrado = bool(cfg.get("roi"))
    falta = faltantes()
    estado = (f"{VERDE}listo{FIN}" if calibrado and not falta
              else f"{ROJO}falta {'calibrar' if not calibrado else 'entrenar'} -> [6]{FIN}")
    print(f"\n{AZUL}{'-' * 60}{FIN}")
    print(f"{NEGRITA} DIAMOND RUSH · agente{FIN}   ({estado})")
    print(f"{AZUL}{'-' * 60}{FIN}")
    for k, nombre, ayuda in OPCIONES:
        print(f"  {NEGRITA}{k}{FIN}  {nombre:<23} {ayuda}")
    print(f"{AMARILLO}> {FIN}", end="", flush=True)
    r = leer_tecla("0123456")
    if r == "0":
        return False
    if r in "123" and not calibrado:
        print(f"{ROJO}Primero calibra el tablero: [4] o [6].{FIN}")
        return True
    if r == "1":
        print("Ve al navegador y presiona F8 cuando el nivel esté listo (F9 cancela).")
        ejecutar_rapido("f8")
    elif r == "2":
        ejecutar_rapido("ver")
    elif r == "3":
        ejecutar_rapido("probar")
    elif r == "4":
        correr([paso_calibrar, paso_ver])
    elif r == "5":
        correr([paso_reentrenar, paso_ver])
    elif r == "6":
        correr([paso_entorno, paso_juego, paso_calibrar, paso_etiquetar, paso_ver, paso_probar])
    return True


def main():
    while menu():
        pass
    print(f"\n{VERDE}¡Listo! Mucha suerte en el torneo.{FIN}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSaliendo del asistente.")

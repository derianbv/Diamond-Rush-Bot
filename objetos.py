"""
Objetos personalizados del entrenador.

Si en pantalla aparece algo que no corresponde a ninguno de los objetos base,
se puede crear un objeto nuevo (p.ej. "pared_con_hojas" o "salida_dorada").
Cada objeto nuevo dice a qué objeto base SE PARECE EN COMPORTAMIENTO, así el
planificador sabe cómo tratarlo (pared, suelo, diamante, salida...).

Se guardan en objetos.json:  {"nombre": {"como": "<objeto base>", "tecla": "z"}}
y sus ejemplos en plantillas/<nombre>/.
"""
import json
import os
import re

from config import CARPETA

RUTA = os.path.join(CARPETA, "objetos.json")

# Objetos base: etiqueta -> descripción para el usuario
BASE = {
    "personaje": "el jugador",
    "personaje_con_llave": "el jugador llevando una llave",
    "casilla_vacia": "suelo (se puede caminar)",
    "casilla_ocupada": "pared (no se puede pasar)",
    "diamante": "diamante (hay que recogerlo)",
    "llave": "llave (se recoge)",
    "puerta_objetivo_cerrada": "salida cerrada",
    "puerta_objetivo_abierta": "salida abierta",
    "puerta_llave": "puerta que se abre con llave",
    "puas_inactivas": "púas sin pisar (se pisan una sola vez)",
    "puas_activas": "púas activas (bloquean)",
    "roca": "roca (se empuja)",
    "agujero": "agujero (se tapa con una roca)",
    "agujero_con_roca": "agujero tapado (se camina)",
    "boton": "botón",
    "boton_con_roca": "botón con roca encima",
    "puerta_metalica": "puerta metálica cerrada (la abre un botón)",
    "puerta_metalica_abierta": "puerta metálica abierta",
    "objetivo_ultimo_nivel": "meta del último nivel (estatua)",
}

# Nombre corto (sin tildes, para dibujarlo con OpenCV) y símbolo de cada objeto base
CORTO = {
    "personaje": "jugador (P)",
    "personaje_con_llave": "jugador con llave (p)",
    "casilla_vacia": "suelo (.)",
    "casilla_ocupada": "pared (#)",
    "diamante": "diamante (D)",
    "llave": "llave (K)",
    "puerta_objetivo_cerrada": "salida cerrada (E)",
    "puerta_objetivo_abierta": "salida abierta (e)",
    "puerta_llave": "puerta de llave (L)",
    "puas_inactivas": "puas sin pisar (^)",
    "puas_activas": "puas activas (X)",
    "roca": "roca (R)",
    "agujero": "agujero (O)",
    "agujero_con_roca": "agujero tapado (o)",
    "boton": "boton (B)",
    "boton_con_roca": "boton con roca (b)",
    "puerta_metalica": "puerta metalica cerr. (M)",
    "puerta_metalica_abierta": "puerta metalica abie. (m)",
    "objetivo_ultimo_nivel": "estatua final ($)",
}


def nombre_corto(nombre, objetos=None):
    if nombre in CORTO:
        return CORTO[nombre]
    objetos = cargar() if objetos is None else objetos
    return f"*{nombre} = {CORTO[objetos[nombre]['como']].split(' (')[0]}"


def elegir_de_lista():
    """Muestra en la consola TODOS los objetos (base y creados) y devuelve el
    elegido. 0 = crear uno nuevo. ENTER = cancelar."""
    extra = cargar()
    nombres = list(BASE) + list(extra)
    print("\n=== ¿Qué objeto hay en las casillas seleccionadas? ===")
    for i, n in enumerate(nombres, 1):
        desc = BASE[n] if n in BASE else f"(tuyo) se comporta como: {BASE[extra[n]['como']]}"
        print(f"  {i:2d}. {n:26s} {desc}")
    print("   0. NINGUNO de estos: crear un objeto nuevo")
    while True:
        r = input("Número (ENTER = cancelar): ").strip()
        if not r:
            return None
        if r == "0":
            return crear_interactivo()
        if r.isdigit() and 1 <= int(r) <= len(nombres):
            return nombres[int(r) - 1]
        print("  Escribe un número de la lista.")


# Teclas fijas de la herramienta (no se pueden usar para objetos nuevos)
TECLAS_BASE = dict(zip("1234567890asdfghjkl", BASE))
ALIAS = {"#": "casilla_ocupada", ".": "casilla_vacia"}
TECLAS_RESERVADAS = set("vupnr")  # en vivo, deshacer, captura, nuevo objeto, revisar
TECLAS_LIBRES = "bceimoqtwxyzBCEFGIJMNOQRTUVWXYZ"


def cargar():
    if os.path.exists(RUTA):
        with open(RUTA, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar(objetos):
    with open(RUTA, "w", encoding="utf-8") as f:
        json.dump(objetos, f, indent=2, ensure_ascii=False)


def base_de(nombre, objetos=None):
    """Objeto base que define el comportamiento de `nombre`."""
    if nombre in BASE:
        return nombre
    objetos = cargar() if objetos is None else objetos
    return objetos[nombre]["como"]


def todas_las_teclas():
    """tecla -> nombre del objeto (base, alias y personalizados)."""
    teclas = dict(TECLAS_BASE)
    teclas.update(ALIAS)
    for nombre, datos in cargar().items():
        teclas[datos["tecla"]] = nombre
    return teclas


def crear_interactivo():
    """Pregunta en la consola los datos de un objeto nuevo y lo guarda."""
    objetos = cargar()
    print("\n=== Nuevo objeto ===")
    while True:
        nombre = input("Nombre del objeto (ej: pared_con_hojas; ENTER = cancelar): ").strip().lower()
        if not nombre:
            print("Cancelado.")
            return None
        nombre = re.sub(r"[^a-z0-9_]+", "_", nombre.replace(" ", "_")).strip("_")
        if nombre in BASE or nombre in objetos:
            print(f"  Ya existe un objeto llamado '{nombre}'. Usa otro nombre.")
            continue
        break

    lista = list(BASE)
    print(f"\n¿Cómo se comporta '{nombre}' en el juego? (a qué objeto se parece)")
    for i, et in enumerate(lista, 1):
        print(f"  {i:2d}. {BASE[et]}")
    while True:
        r = input("Número: ").strip()
        if r.isdigit() and 1 <= int(r) <= len(lista):
            como = lista[int(r) - 1]
            break
        print("  Escribe un número de la lista.")

    usadas = set(todas_las_teclas()) | TECLAS_RESERVADAS
    libres = [t for t in TECLAS_LIBRES if t not in usadas]
    if not libres:
        print("No quedan teclas libres.")
        return None
    while True:
        t = input(f"Tecla para etiquetarlo (libres: {' '.join(libres)}) [ENTER = {libres[0]}]: ").strip() or libres[0]
        if t in libres:
            break
        print("  Esa tecla no está libre.")

    objetos[nombre] = {"como": como, "tecla": t}
    guardar(objetos)
    os.makedirs(os.path.join(CARPETA, "plantillas", nombre), exist_ok=True)
    print(f"Creado '{nombre}' (se comporta como {BASE[como]}), tecla '{t}'.")
    return nombre

"""
Pruebas del modelo del juego y del A* con niveles dibujados en texto.
Ejecutar:  python pruebas.py

Símbolos: P jugador, p jugador con llave, . suelo, # pared, D diamante,
K llave, L puerta de llave, ^ púas, X púas activas, R roca, O agujero,
B botón, M puerta metálica, E salida.
"""
import time

from juego import desde_texto, dibujar
from solver import resolver

CASOS = {
    "camino simple": """
        #####
        #P.D#
        #...#
        #..E#
        #####
    """,
    "llave y puerta": """
        #######
        #P..#E#
        #.K.L.#
        #######
    """,
    "roca al agujero": """
        #######
        #PR.O.E
        #######
    """,
    "boton y puerta metalica": """
        ########
        #..R.B.#
        #P######
        #.....ME
        ########
    """,
    # Las púas: solo se pueden pisar una vez. Hay que elegir bien el orden.
    "puas una sola vez": """
        #######
        #D.^.P#
        #.###.#
        #E....#
        #######
    """,
    # La roca puede pasar por encima de la llave.
    "roca sobre llave": """
        #########
        #PRK...##
        #####.L.E
        #########
    """,
}

# Casos que deben resultar IMPOSIBLES con estas reglas
IMPOSIBLES = {
    "sin llave": """
        ######
        #P.LE#
        ######
    """,
    "puas bloquean regreso": """
        ########
        #D.^.PE#
        ########
    """,
}


def main():
    total, fallos = 0, 0
    for nombre, texto in CASOS.items():
        total += 1
        filas = [l.strip() for l in texto.strip().splitlines()]
        ancho = max(len(f) for f in filas)
        texto = "\n".join(f.ljust(ancho, "#") for f in filas)
        nivel, estado = desde_texto(texto)
        t = time.perf_counter()
        plan = resolver(nivel, estado, limite_segundos=10, verbose=False)
        dt = time.perf_counter() - t
        if plan is None:
            fallos += 1
            print(f"[FALLA] {nombre}: no encontró solución\n{dibujar(nivel, estado)}\n")
            continue
        # verificar que el plan realmente gana según el modelo
        e = estado
        gano = False
        for paso in plan:
            e, gano = nivel.mover(e, paso)
        ok = gano and not e.diamantes
        fallos += not ok
        print(f"[{'OK' if ok else 'FALLA'}] {nombre}: {len(plan)} pasos en {dt * 1000:.1f} ms -> {' '.join(plan)}")

    for nombre, texto in IMPOSIBLES.items():
        total += 1
        nivel, estado = desde_texto(texto)
        plan = resolver(nivel, estado, limite_segundos=5, verbose=False)
        ok = plan is None
        fallos += not ok
        print(f"[{'OK' if ok else 'FALLA'}] imposible '{nombre}' -> {'sin solución' if ok else plan}")

    print(f"\n{total - fallos}/{total} pruebas correctas")


if __name__ == "__main__":
    main()

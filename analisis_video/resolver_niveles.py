"""
Prueba del planificador con los 20 niveles reales del juego (extraídos del
walkthrough). No necesita el video: usa niveles_walkthrough.json.

Estos tableros son SOLO datos de prueba; el agente no los usa al jugar
(siempre calcula el plan a partir de lo que ve en pantalla).

Uso (desde la carpeta del proyecto):
    python analisis_video/resolver_niveles.py                 # todos, con todos los núcleos
    python analisis_video/resolver_niveles.py --procesos 3    # simular un PC de 4 núcleos
    python analisis_video/resolver_niveles.py --niveles 6,10,11 --limite 60
"""
import argparse
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
from juego import JUGADOR, PUAS, construir_estado, construir_nivel  # noqa: E402
from solver import resolver  # noqa: E402

F0, C0, NF, NC = 2, 1, 12, 8   # tablero efectivo 8x12 dentro de la grilla 15x10


def cargar(n, verdad):
    g = [fila[C0:C0 + NC] for fila in verdad[str(n)][F0:F0 + NF]]
    jug = next(f * NC + c for f in range(NF) for c in range(NC) if g[f][c] in JUGADOR)
    nivel = construir_nivel(g, jug)
    return nivel, construir_estado(nivel, g, jug, False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--niveles", default=",".join(map(str, range(1, 21))))
    ap.add_argument("--limite", type=float, default=100.0, help="segundos por nivel")
    ap.add_argument("--procesos", type=int, default=None, help="estrategias en paralelo (por defecto: núcleos-1)")
    args = ap.parse_args()
    verdad = json.load(open(os.path.join(AQUI, "niveles_walkthrough.json")))

    resueltos = 0
    niveles = [int(x) for x in args.niveles.split(",")]
    for n in niveles:
        nivel, e = cargar(n, verdad)
        t = time.perf_counter()
        plan = resolver(nivel, e, args.limite, verbose=False, espera_mejor=10, procesos=args.procesos)
        dt = time.perf_counter() - t
        if plan:  # comprobar que el plan gana en el modelo
            x, gano = e, False
            for p in plan:
                x, gano = nivel.mover(x, p)
            resueltos += gano
        print(f"Nivel {n:2d}: diamantes={len(e.diamantes):2d} rocas={len(e.rocas):2d} llaves={len(e.llaves)} "
              f"púas={sum(t == PUAS for t in nivel.tipo)} -> "
              + (f"{len(plan)} pasos en {dt:.1f}s" if plan else f"SIN SOLUCIÓN ({dt:.0f}s)"), flush=True)
    print(f"\n{resueltos}/{len(niveles)} niveles resueltos")


if __name__ == "__main__":
    main()

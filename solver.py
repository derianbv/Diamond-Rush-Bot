"""
Búsqueda A* sobre el espacio de estados del juego.

Cada nodo es un Estado completo (jugador + rocas + diamantes + ...), no solo
una posición. Cada movimiento cuesta 1, así que g(n) = pasos dados y
f(n) = g(n) + w * h(n).

Dos heurísticas:
  * "admisible": nunca sobreestima (ver Nivel.heuristica). Con w=1 da el
    camino MÁS CORTO, pero en niveles grandes puede tardar demasiado.
  * "recorrido": largo del tour 'diamante más cercano primero' (más
    informada, no admisible). Encuentra soluciones mucho más rápido.

  * "agujeros": como "recorrido", pero sabe que cada agujero sin tapar en el
    camino a la salida cuesta rellenarlo con una roca. Es la que resuelve
    niveles tipo "puzle de rocas" (nivel 20: la estatua está detrás de 4
    agujeros y no hay diamantes, así que las otras dos heurísticas se reducen a
    "distancia a la salida" y A* se pierde entre millones de combinaciones de rocas).

Ninguna combinación (heurística, peso) gana en todos los niveles (lo medimos
con los 20 niveles del walkthrough), así que se corren VARIAS EN PARALELO,
una por núcleo del procesador, y nos quedamos con el plan más corto.
El tiempo de planificar no cuenta en el torneo (solo desde la primera tecla).

Poda: si el jugador acaba de pisar una púa y por eso ya no puede llegar a
algún diamante o a la salida, ese estado se descarta.
"""
import heapq
import itertools
import multiprocessing
import os
import time

from juego import AGUJERO, DIRECCIONES, INF

ORDEN = tuple(DIRECCIONES)

OK, SIN_SOLUCION, SIN_TIEMPO = "ok", "sin_solucion", "sin_tiempo"

# Estrategias en orden de prioridad (heurística, peso). Con pocos núcleos solo
# corren las primeras, así que van primero las que mejor resultaron en los 20
# niveles del walkthrough (más rápidas en los niveles difíciles), y la óptima
# (admisible, w=1) que da el plan más corto en los niveles chicos.
ESTRATEGIAS = [
    ("recorrido", 1.5),
    ("admisible", 1.0),   # la óptima
    ("recorrido", 5.0),
    ("recorrido", 1.0),
    ("recorrido", 3.0),
    ("admisible", 5.0),
]


def _hay_agujeros_por_tapar(nivel, inicio):
    return any(t == AGUJERO and i not in inicio.agujeros_llenos for i, t in enumerate(nivel.tipo))


def estrategias_para(nivel, inicio):
    """Las estrategias a probar, en orden de prioridad, según cómo es el nivel.
    (Con pocos núcleos solo corren las primeras, por eso el orden importa.)"""
    lista = list(ESTRATEGIAS)
    if inicio.rocas and _hay_agujeros_por_tapar(nivel, inicio):
        if nivel.agujeros_obligatorios(inicio) > 0:
            # La meta (o algún diamante) está SELLADA detrás de agujeros: hay que
            # rellenarlos con rocas sí o sí. Las heurísticas que lo saben van primero
            # (la de peso 2 después de la óptima, para no quitarle su lugar a las que
            # ya funcionaban en los niveles con diamantes).
            lista.insert(0, ("agujeros", 1.0))
            lista.insert(3, ("agujeros_medio", 2.0))
            lista.append(("agujeros", 3.0))
        else:
            # Los agujeros se pueden esquivar: el orden de siempre, y las nuevas al
            # final por si el camino fácil resulta no servir (y hay núcleos de sobra).
            lista += [("agujeros", 1.0), ("agujeros_medio", 2.0)]
    if not inicio.diamantes:
        # Sin diamantes "admisible" y "recorrido" son la MISMA heurística: no
        # tiene sentido gastar un núcleo en repetir una estrategia.
        vistas, unicas = set(), []
        for nombre, peso in lista:
            clave = ("recorrido" if nombre == "admisible" else nombre, peso)
            if clave not in vistas:
                vistas.add(clave)
                unicas.append((nombre, peso))
        lista = unicas
    return lista


def _heuristica(nivel, nombre):
    if nombre == "admisible":
        return nivel.heuristica
    if nombre == "recorrido":
        return nivel.heuristica_tour
    # "agujeros": peaje = lo que cuesta traer una roca a un agujero, del orden del
    # "medio perímetro" del tablero. "agujeros_medio": la mitad (más optimista).
    peaje = nivel.filas + nivel.columnas
    if nombre == "agujeros_medio":
        peaje //= 2
    return lambda e: nivel.heuristica_agujeros(e, peaje)


def _a_estrella(nivel, inicio, peso, heuristica, hora_limite):
    h0 = heuristica(inicio)
    if h0 >= INF or not nivel.todo_alcanzable(inicio):
        return SIN_SOLUCION, None, 0

    contador = itertools.count()          # desempate para que heapq no compare estados
    abiertos = [(peso * h0, 0, next(contador), inicio)]
    mejor_g = {inicio: 0}
    padre = {inicio: None}                # estado -> (estado_anterior, direccion)
    metas = set()
    expandidos = 0

    while abiertos:
        _, menos_g, _, e = heapq.heappop(abiertos)
        g = -menos_g
        if g > mejor_g[e]:
            continue                      # entrada vieja, ya encontramos algo mejor
        if e in metas:
            return OK, _reconstruir(padre, e), expandidos

        expandidos += 1
        if expandidos % 4096 == 0 and time.perf_counter() > hora_limite:
            return SIN_TIEMPO, None, expandidos

        for d in ORDEN:
            r = nivel.mover(e, d)
            if r is None:
                continue
            n, gano = r
            ng = g + 1
            if ng >= mejor_g.get(n, INF):
                continue
            if not gano and n.puas_pisadas is not e.puas_pisadas and not nivel.todo_alcanzable(n):
                continue                  # la púa recién pisada encerró algo que falta
            h = 0 if gano else heuristica(n)
            if h >= INF:
                continue                  # desde aquí es imposible llegar
            mejor_g[n] = ng
            padre[n] = (e, d)
            if gano:
                metas.add(n)
            # -ng: a igual f preferimos el nodo más profundo (llega antes a la meta)
            heapq.heappush(abiertos, (ng + peso * h, -ng, next(contador), n))

    return SIN_SOLUCION, None, expandidos


def _reconstruir(padre, e):
    plan = []
    while padre[e] is not None:
        e, d = padre[e]
        plan.append(d)
    plan.reverse()
    return plan


def _correr(nivel, inicio, nombre, peso, segundos):
    """Una estrategia. Se ejecuta en un proceso aparte."""
    h = _heuristica(nivel, nombre)
    t = time.perf_counter()
    estado, plan, expandidos = _a_estrella(nivel, inicio, peso, h, t + segundos)
    return nombre, peso, estado, plan, expandidos, time.perf_counter() - t


def resolver(nivel, inicio, limite_segundos=100.0, verbose=True, paralelo=True, espera_mejor=15.0, procesos=None):
    """Devuelve la lista de movimientos (p.ej. ["arriba", "derecha", ...]) o None.
    paralelo=True: varias estrategias a la vez (para el plan inicial).
    paralelo=False: una tras otra (para re-planificar rápido a mitad del nivel)."""
    nucleos = procesos or max(1, (os.cpu_count() or 2) - 1)
    if paralelo and nucleos > 1:
        return _resolver_paralelo(nivel, inicio, limite_segundos, verbose, espera_mejor, nucleos)
    return _resolver_secuencial(nivel, inicio, limite_segundos, verbose)


def _resolver_secuencial(nivel, inicio, limite_segundos, verbose):
    t0 = time.perf_counter()
    fin = t0 + limite_segundos
    estrategias = estrategias_para(nivel, inicio)
    for k, (nombre, peso) in enumerate(estrategias):
        restante = fin - time.perf_counter()
        if restante <= 0:
            break
        parte = restante if k == len(estrategias) - 1 else restante * 0.35
        _, _, estado, plan, expandidos, dt = _correr(nivel, inicio, nombre, peso, parte)
        if verbose:
            print(f"  A* ({nombre}, peso={peso}): {estado}, {expandidos} nodos, {dt:.2f}s"
                  + (f", {len(plan)} pasos" if plan else ""))
        if estado == OK:
            return plan
        if estado == SIN_SOLUCION:
            return None  # se exploró todo: con estas reglas no hay solución
    return None


def _resolver_paralelo(nivel, inicio, limite_segundos, verbose, espera_mejor, nucleos):
    estrategias = estrategias_para(nivel, inicio)[:nucleos]
    t0 = time.perf_counter()
    resultados = []
    pool = multiprocessing.get_context("spawn").Pool(len(estrategias))
    try:
        tareas = [pool.apply_async(_correr, (nivel, inicio, n, p, limite_segundos)) for n, p in estrategias]
        pendientes = set(range(len(tareas)))
        primero = None
        if verbose:
            print(f"  Probando {len(tareas)} estrategias en paralelo...")
        while pendientes and time.perf_counter() - t0 < limite_segundos + 2:
            for i in list(pendientes):
                if tareas[i].ready():
                    pendientes.discard(i)
                    nombre, peso, estado, plan, expandidos, dt = tareas[i].get()
                    if verbose:
                        print(f"  A* ({nombre}, peso={peso}): {estado}, {expandidos} nodos, {dt:.2f}s"
                              + (f", {len(plan)} pasos" if plan else ""))
                    if estado == SIN_SOLUCION:
                        return None  # se exploró todo: no hay solución con estas reglas
                    if estado == OK:
                        resultados.append(plan)
                        primero = primero or time.perf_counter()
                        if nombre == "admisible" and peso == 1.0:
                            pendientes.clear()  # es la óptima: no hay nada mejor
            if primero and time.perf_counter() - primero > espera_mejor:
                break  # ya esperamos bastante por un plan más corto
            time.sleep(0.05)
    finally:
        pool.terminate()
    if not resultados:
        return None
    mejor = min(resultados, key=len)
    if verbose:
        print(f"  Mejor plan: {len(mejor)} pasos ({time.perf_counter() - t0:.1f}s)")
    return mejor

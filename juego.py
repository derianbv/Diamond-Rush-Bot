"""
Modelo del juego Diamond Rush: qué hay en el tablero y qué pasa al moverse.

Separamos el nivel en dos partes:

  * Lo FIJO (clase Nivel): paredes, agujeros, botones, puertas metálicas, salida
    y púas. Esto no se mueve durante el nivel.
  * Lo que CAMBIA (Estado): dónde está el jugador, las rocas, los diamantes
    que faltan, las llaves en el piso, las puertas de llave cerradas, si llevo
    llave, qué púas ya pisé y qué agujeros ya tapé.

Las casillas se numeran con un solo entero: indice = fila * columnas + columna.
Así un Estado es una tupla de enteros y frozensets, que se puede guardar en
un diccionario (lo necesita el A* para no repetir estados).
"""
import heapq
from collections import deque, namedtuple

# ---------------------------------------------------------------------------
# Tipos de casilla fija
# ---------------------------------------------------------------------------
PARED, SUELO, AGUJERO, BOTON, PUERTA_METALICA, SALIDA, PUAS = range(7)

DIRECCIONES = {
    "arriba": (-1, 0),
    "abajo": (1, 0),
    "izquierda": (0, -1),
    "derecha": (0, 1),
}

INF = 10 ** 6

Estado = namedtuple("Estado", [
    "jugador",          # casilla del jugador
    "rocas",            # frozenset: casillas con roca
    "diamantes",        # frozenset: diamantes que faltan por recoger
    "llaves",           # frozenset: llaves que siguen en el piso
    "puertas_llave",    # frozenset: puertas de llave todavía cerradas
    "tiene_llave",      # bool: el jugador lleva una llave
    "puas_pisadas",     # frozenset: púas ya pisadas (ahora bloquean)
    "agujeros_llenos",  # frozenset: agujeros tapados con una roca (caminables)
])


class Nivel:
    """Parte fija del nivel + las reglas de movimiento."""

    def __init__(self, filas, columnas, tipo, puertas=(),
                 entra_al_abrir=True, roca_sobre_puas=True, roca_sobre_diamante=True,
                 requiere_diamantes=True):
        self.filas = filas
        self.columnas = columnas
        self.tipo = tipo                      # lista: tipo de cada casilla
        self.salidas = {i for i, t in enumerate(tipo) if t == SALIDA}
        # En el último nivel la meta es la estatua y NO hace falta juntar diamantes
        # (en el walkthrough se gana con 0/14).
        self.requiere_diamantes = requiere_diamantes

        # Reglas que no están 100% confirmadas (se pueden cambiar en config.json)
        self.entra_al_abrir = entra_al_abrir      # al abrir una puerta de llave, ¿el jugador entra en el mismo paso?
        self.roca_sobre_puas = roca_sobre_puas    # ¿una roca puede empujarse sobre púas sin pisar?
        self.roca_sobre_diamante = roca_sobre_diamante  # ¿una roca puede pasar sobre un diamante? (nivel 4: sí)

        # Movimientos que el modelo creía posibles pero el juego real no dejó
        # hacer: (casilla_jugador, direccion, rocas). Lo llena el agente.
        self.bloqueados = set()

        # Qué botón abre cada puerta metálica NO se ve en pantalla (en el nivel 14
        # el botón no abre la puerta más cercana). Por eso el modelo es optimista:
        # una puerta se abre si CUALQUIERA de sus botones candidatos tiene roca.
        # Al jugar, el agente mira qué puertas se abren y descarta candidatos.
        self.botones = [i for i, t in enumerate(tipo) if t == BOTON]
        self.candidatos = {p: set(self.botones) for p in puertas}

        # vecino[i][direccion] = casilla de al lado, o -1 si es fuera del tablero
        self.vecino = []
        for i in range(filas * columnas):
            f, c = divmod(i, columnas)
            v = {}
            for nombre, (df, dc) in DIRECCIONES.items():
                nf, nc = f + df, c + dc
                v[nombre] = nf * columnas + nc if 0 <= nf < filas and 0 <= nc < columnas else -1
            self.vecino.append(v)

        # Máscaras de bits para todo_alcanzable (bit i = casilla i)
        n = filas * columnas
        self.mascara_libre = sum(1 << i for i in range(n) if tipo[i] != PARED)
        self.mascara_salidas = sum(1 << s for s in self.salidas)
        self.sin_col0 = sum(1 << i for i in range(n) if i % columnas != 0)                  # tras correr a la derecha
        self.sin_col_ultima = sum(1 << i for i in range(n) if i % columnas != columnas - 1)  # tras correr a la izquierda

        self.dist = self._distancias_estaticas()
        self.dist_salida = [min((self.dist[i][s] for s in self.salidas), default=INF)
                            for i in range(filas * columnas)]

        # Memoria de heuristica_agujeros: (peaje, agujeros tapados) -> distancia a la salida de cada casilla
        self._tablas_peaje = {}

    # -----------------------------------------------------------------------
    # Distancias para la heurística
    # -----------------------------------------------------------------------
    def _distancias_estaticas(self):
        """BFS desde cada casilla en un mapa "optimista": todo lo que no es
        pared se considera transitable (rocas, puertas, agujeros...). Como el
        mapa real nunca es más fácil que este, la distancia nunca sobreestima:
        eso hace que la heurística sea admisible."""
        n = self.filas * self.columnas
        dist = []
        for origen in range(n):
            d = [INF] * n
            if self.tipo[origen] != PARED:
                d[origen] = 0
                cola = deque([origen])
                while cola:
                    a = cola.popleft()
                    for b in self.vecino[a].values():
                        if b >= 0 and d[b] == INF and self.tipo[b] != PARED:
                            d[b] = d[a] + 1
                            cola.append(b)
            dist.append(d)
        return dist

    def heuristica(self, e):
        """h(n): para cada diamante que falta, tengo que ir hasta él y después
        a la salida. Tomamos el peor de esos caminos (el máximo), y también la
        distancia directa a la salida. Nunca sobreestima el costo real."""
        fila_dist = self.dist[e.jugador]
        h = self.dist_salida[e.jugador]
        for d in e.diamantes:
            v = fila_dist[d] + self.dist_salida[d]
            if v > h:
                h = v
        return h

    def heuristica_tour(self, e):
        """Estimación más fuerte (no admisible): largo del recorrido
        'ir siempre al diamante más cercano' y después a la salida. Sirve para
        encontrar soluciones rápido en niveles grandes."""
        pos, total = e.jugador, 0
        faltan = set(e.diamantes)
        while faltan:
            fila = self.dist[pos]
            d = min(faltan, key=fila.__getitem__)
            total += fila[d]
            pos = d
            faltan.discard(d)
        return total + self.dist_salida[pos]

    def _tabla_peaje(self, tapados, peaje):
        """Distancia de cada casilla a la salida, pero cruzar un agujero SIN tapar
        cuesta `peaje` pasos extra (es lo que cuesta, más o menos, traer una roca
        y empujarla hasta ahí). Solo depende de QUÉ agujeros ya están tapados, así
        que se calcula una vez por combinación y se guarda."""
        clave = (peaje, tapados)
        d = self._tablas_peaje.get(clave)
        if d is None:
            d = [INF] * (self.filas * self.columnas)
            cola = []
            for s in self.salidas:
                d[s] = 0
                cola.append((0, s))
            while cola:                       # Dijkstra desde la(s) salida(s), hacia atrás
                dd, a = heapq.heappop(cola)
                if dd > d[a]:
                    continue
                costo = 1 + (peaje if self.tipo[a] == AGUJERO and a not in tapados else 0)
                for b in self.vecino[a].values():
                    if b >= 0 and self.tipo[b] != PARED and dd + costo < d[b]:
                        d[b] = dd + costo
                        heapq.heappush(cola, (dd + costo, b))
            self._tablas_peaje[clave] = d
        return d

    def heuristica_agujeros(self, e, peaje):
        """Como heuristica_tour, pero sabe que los agujeros sin tapar en el camino
        a la salida hay que rellenarlos con rocas. Sin esto, en un nivel donde la
        salida está detrás de varios agujeros (nivel 20) la heurística dice "faltan
        11 pasos" cuando en realidad faltan ~75, y A* se pierde probando
        combinaciones de rocas sin ninguna guía (no es admisible, como el tour)."""
        con_peaje = self._tabla_peaje(e.agujeros_llenos, peaje)[e.jugador]
        if con_peaje >= INF:
            return INF
        return self.heuristica_tour(e) + con_peaje - self.dist_salida[e.jugador]

    def agujeros_obligatorios(self, e):
        """Cuántos agujeros sin tapar hay que rellenar, como mínimo, para llegar a la
        salida y a todos los diamantes (0 = se puede llegar a todo sin rellenar nada).
        Mide si el objetivo está "sellado" detrás de agujeros, como en el nivel 20.
        Es un recorrido 0-1: entrar a un agujero sin tapar cuenta 1, lo demás 0
        (rocas, puertas y púas se ignoran: es optimista)."""
        n = self.filas * self.columnas
        cuenta = [INF] * n
        cuenta[e.jugador] = 0
        cola = deque([e.jugador])
        while cola:
            a = cola.popleft()
            for b in self.vecino[a].values():
                if b < 0 or self.tipo[b] == PARED:
                    continue
                c = cuenta[a] + (1 if self.tipo[b] == AGUJERO and b not in e.agujeros_llenos else 0)
                if c < cuenta[b]:
                    cuenta[b] = c
                    # 0-1 BFS: el costo 0 va al frente de la cola, el 1 al final
                    cola.appendleft(b) if c == cuenta[a] else cola.append(b)
        a_la_salida = min((cuenta[s] for s in self.salidas), default=INF)
        if a_la_salida >= INF:
            return 0  # la salida no se alcanza ni rellenando: eso lo detecta el A*
        return max([a_la_salida] + [cuenta[d] for d in e.diamantes if cuenta[d] < INF])

    def todo_alcanzable(self, e):
        """¿Todavía se puede llegar a todos los diamantes y a la salida, contando
        las púas ya pisadas como paredes? (Lo demás se toma con optimismo.)
        Si no, ese estado es un callejón sin salida.

        Se calcula con máscaras de bits (cada casilla es un bit de un entero):
        la zona alcanzable crece "inundando" a las 4 vecinas en cada vuelta,
        con unas pocas operaciones por vuelta en vez de recorrer casilla por casilla."""
        libre = self.mascara_libre
        for p in e.puas_pisadas:
            libre &= ~(1 << p)
        c = self.columnas
        zona = 1 << e.jugador
        while True:
            nueva = (zona | ((zona << 1) & self.sin_col0) | ((zona >> 1) & self.sin_col_ultima)
                     | (zona << c) | (zona >> c)) & libre
            if nueva == zona:
                break
            zona = nueva
        zona |= 1 << e.jugador  # el jugador puede estar parado sobre una púa ya pisada
        for d in e.diamantes:
            if not zona >> d & 1:
                return False
        return bool(zona & self.mascara_salidas)

    # -----------------------------------------------------------------------
    # Reglas
    # -----------------------------------------------------------------------
    def puerta_abierta(self, puerta, rocas):
        """Una puerta metálica está abierta si su botón tiene una roca encima.
        (Si el jugador pisa el botón también se abre y se cierra apenas se baja:
        solo le sirve si entra a la puerta directo desde el botón; eso lo
        revisa `mover`.)"""
        return any(b in rocas for b in self.candidatos.get(puerta, ()))

    def observar_puertas(self, rocas, abiertas, jugador):
        """Aprende qué botón abre cada puerta a partir de lo que se ve:
        si una puerta está abierta, su botón es uno de los que tienen roca;
        si está cerrada, no es ninguno de ellos. Devuelve True si cambió algo."""
        if jugador in self.botones:
            return False  # el jugador pisando un botón también abre puertas: no sirve para deducir
        pulsados = {b for b in self.botones if b in rocas}
        cambio = False
        for p, cand in self.candidatos.items():
            if p == jugador:
                continue
            nuevo = cand & pulsados if p in abiertas else cand - pulsados
            if nuevo and nuevo != cand:
                self.candidatos[p] = nuevo
                cambio = True
        return cambio

    def _roca_puede_ir(self, r, e, rocas, desde):
        """¿Se puede empujar la roca que está en `desde` hacia la casilla r?"""
        if r < 0:
            return False
        t = self.tipo[r]
        if t == PARED or t == SALIDA:
            return False
        if t == PUERTA_METALICA and not self.puerta_abierta(r, rocas - {desde}):
            # Una roca puede pasar por una puerta metálica ABIERTA (nivel 17 del
            # walkthrough, 658,9 s). Si la roca que se empuja es la que la mantenía
            # abierta (estaba en su botón), al moverla la puerta se cierra.
            return False
        if t == PUAS and (not self.roca_sobre_puas or r in e.puas_pisadas):
            return False
        if r in rocas or r in e.puertas_llave:
            return False
        if r in e.diamantes and not self.roca_sobre_diamante:
            return False
        # SUELO, BOTON, AGUJERO (lleno o vacío), y casillas con llave o diamante:
        # la roca queda encima y el objeto aparece de nuevo al quitarla.
        return True

    def mover(self, e, direccion):
        """Aplica un movimiento. Devuelve (nuevo_estado, gano) o None si el
        movimiento no es posible (el jugador no se movería)."""
        q = self.vecino[e.jugador][direccion]
        if q < 0:
            return None
        if self.bloqueados and (e.jugador, direccion, e.rocas) in self.bloqueados:
            return None
        t = self.tipo[q]

        if t == PARED:
            return None
        if t == AGUJERO and q not in e.agujeros_llenos:
            return None
        if t == PUAS and q in e.puas_pisadas:
            return None
        if t == PUERTA_METALICA and not (self.puerta_abierta(q, e.rocas)
                                         or e.jugador in self.candidatos.get(q, ())):
            # Abierta por una roca en su botón, o porque el jugador está PARADO en
            # su botón y entra a la puerta en ese mismo paso (nivel 19 del
            # walkthrough: el botón está al lado de la puerta). Al salir del
            # botón la puerta se cierra, pero el jugador ya está adentro.
            return None
        if t == SALIDA:
            if e.diamantes and self.requiere_diamantes:
                return None  # la salida está cerrada mientras falten diamantes
            return e._replace(jugador=q), True

        rocas = e.rocas
        agujeros = e.agujeros_llenos
        puertas = e.puertas_llave
        tiene_llave = e.tiene_llave

        # Puerta de llave
        if q in puertas:
            if not tiene_llave:
                return None
            puertas = puertas - {q}
            tiene_llave = False
            if not self.entra_al_abrir:
                return e._replace(puertas_llave=puertas, tiene_llave=False), False

        # Empujar roca
        if q in rocas:
            r = self.vecino[q][direccion]
            if not self._roca_puede_ir(r, e, rocas, q):
                return None
            rocas = rocas - {q}
            if self.tipo[r] == AGUJERO and r not in agujeros:
                agujeros = agujeros | {r}  # la roca tapa el agujero y desaparece
            else:
                rocas = rocas | {r}

        diamantes = e.diamantes
        if q in diamantes:
            diamantes = diamantes - {q}

        llaves = e.llaves
        if q in llaves and not tiene_llave:
            llaves = llaves - {q}
            tiene_llave = True

        puas = e.puas_pisadas
        if t == PUAS:
            puas = puas | {q}  # al salir de aquí quedará bloqueada

        nuevo = Estado(q, rocas, diamantes, llaves, puertas, tiene_llave, puas, agujeros)
        return nuevo, False

    def simular(self, estado, plan):
        """Ejecuta un plan sobre el modelo. Devuelve la lista de estados."""
        estados = [estado]
        for paso in plan:
            r = self.mover(estados[-1], paso)
            if r is None:
                raise ValueError(f"Movimiento inválido en el plan: {paso}")
            estados.append(r[0])
        return estados


# ---------------------------------------------------------------------------
# De etiquetas (lo que ve la cámara) a Nivel + Estado
# ---------------------------------------------------------------------------
# Símbolos de un carácter para imprimir el tablero y escribir niveles de prueba
SIMBOLO = {
    "personaje": "P",
    "personaje_con_llave": "p",
    "casilla_vacia": ".",
    "casilla_ocupada": "#",
    "diamante": "D",
    "llave": "K",
    "puerta_objetivo_cerrada": "E",
    "puerta_objetivo_abierta": "e",
    "puerta_llave": "L",
    "puas_inactivas": "^",
    "puas_activas": "X",
    "roca": "R",
    "agujero": "O",
    "agujero_con_roca": "o",
    "boton": "B",
    "boton_con_roca": "b",
    "puerta_metalica": "M",
    "puerta_metalica_abierta": "m",
    "objetivo_ultimo_nivel": "$",
    "desconocido": "?",
    "hud": "H",
}
ETIQUETA_DE_SIMBOLO = {v: k for k, v in SIMBOLO.items()}

JUGADOR = ("personaje", "personaje_con_llave")


def construir_nivel(etiquetas, jugador, entra_al_abrir=True, roca_sobre_puas=True, roca_sobre_diamante=True):
    """Crea la parte fija del nivel a partir de la grilla de etiquetas.
    `etiquetas` es una lista de filas; `jugador` es el índice de su casilla."""
    filas, columnas = len(etiquetas), len(etiquetas[0])
    # Último nivel: si se ve la estatua dorada, ESA es la meta (no hay puerta de
    # salida) y no hace falta juntar diamantes.
    estatua = any(et == "objetivo_ultimo_nivel" for fila in etiquetas for et in fila)
    tipo = []
    for f in range(filas):
        for c in range(columnas):
            et = etiquetas[f][c]
            if f * columnas + c == jugador or et in JUGADOR:
                tipo.append(SUELO)
            elif et in ("casilla_ocupada", "puas_activas", "desconocido", "hud"):
                tipo.append(PARED)  # lo desconocido se trata como pared, por seguridad
            elif et in ("agujero", "agujero_con_roca"):
                tipo.append(AGUJERO)
            elif et in ("boton", "boton_con_roca"):
                tipo.append(BOTON)
            elif et in ("puerta_metalica", "puerta_metalica_abierta"):
                tipo.append(PUERTA_METALICA)
            elif et == "objetivo_ultimo_nivel":
                tipo.append(SALIDA)
            elif et in ("puerta_objetivo_cerrada", "puerta_objetivo_abierta"):
                # Con la estatua en el tablero, una "puerta de salida" es un error de
                # lectura: no cuenta como meta (se trata como pared, por seguridad).
                tipo.append(PARED if estatua else SALIDA)
            elif et == "puas_inactivas":
                tipo.append(PUAS)
            else:  # casilla_vacia, diamante, llave, puerta_llave, roca
                tipo.append(SUELO)

    botones = [i for i, t in enumerate(tipo) if t == BOTON]
    puertas = [i for i, t in enumerate(tipo) if t == PUERTA_METALICA]
    if not botones:
        for p in puertas:
            tipo[p] = PARED  # puerta sin botón: nunca abre
        puertas = []

    return Nivel(filas, columnas, tipo, puertas, entra_al_abrir, roca_sobre_puas, roca_sobre_diamante,
                 requiere_diamantes=not estatua)


def construir_estado(nivel, etiquetas, jugador, tiene_llave, previo=None):
    """Arma el Estado (lo que cambia) a partir de lo que se ve en pantalla.
    Si hay un estado `previo` (cuando re-planificamos a mitad del nivel), lo
    usamos para lo que la cámara no puede ver: una llave tapada por una roca,
    o la púa que está debajo del jugador.

    Una roca puede quedar encima de unas púas: eso NO las activa. Las púas se
    activan DESPUÉS de que el jugador pasa por encima, apenas se mueve a otra
    casilla (en el modelo se marcan al entrar, que es equivalente: mientras está
    encima todavía puede ir hacia cualquier lado).

    Una roca que cae en un agujero lo tapa y desaparece ("agujero_con_roca"). Pero
    otra roca SÍ puede pasar por encima de un agujero ya tapado, y esa se sigue
    contando como roca."""
    columnas = nivel.columnas
    rocas, diamantes, llaves, puertas, puas, agujeros = set(), set(), set(), set(), set(), set()
    for f, fila in enumerate(etiquetas):
        for c, et in enumerate(fila):
            i = f * columnas + c
            t = nivel.tipo[i]
            if i == jugador:
                continue
            if t == AGUJERO:
                if et != "agujero":
                    agujeros.add(i)  # se ve algo encima del agujero: está tapado
                if et == "roca" and previo is not None and i in previo.rocas:
                    # Agujero ya tapado con OTRA roca encima. La primera roca quedó
                    # atrapada en el hueco ("agujero_con_roca", no cuenta como roca),
                    # pero esta segunda sí se puede seguir empujando.
                    # Solo se cuenta si el modelo sabe que se empujó una roca ahí:
                    # un agujero tapado se ve casi igual que una roca, y contar una
                    # roca de más puede dejar el nivel "sin solución".
                    rocas.add(i)
                continue
            if t == PUAS:
                # Las púas se activan cuando el jugador pasa por encima y se mueve
                # a otra casilla. Una roca encima no las activa: la roca se sigue
                # contando como roca y las púas quedan sin pisar.
                if et == "puas_activas":
                    puas.add(i)
                elif et in ("roca", "boton_con_roca"):
                    rocas.add(i)
                elif et != "puas_inactivas" and previo is not None:
                    # La visión no reconoce lo que hay encima (p.ej. aún no hay
                    # ejemplos de "roca sobre púas"): nos quedamos con lo que ya
                    # sabíamos de esa casilla.
                    if i in previo.rocas:
                        rocas.add(i)
                    if i in previo.puas_pisadas:
                        puas.add(i)
                continue
            if et in ("roca", "boton_con_roca"):
                rocas.add(i)
            elif et == "diamante":
                diamantes.add(i)
            elif et == "llave":
                llaves.add(i)
            elif et == "puerta_llave":
                puertas.add(i)

    if previo is not None:
        llaves |= previo.llaves & rocas          # llaves escondidas bajo una roca
        diamantes |= previo.diamantes & rocas    # diamantes escondidos bajo una roca
        if nivel.tipo[jugador] == PUAS:
            puas.add(jugador)                    # la púa que estoy pisando
        if nivel.tipo[jugador] == AGUJERO:
            agujeros.add(jugador)
    elif nivel.tipo[jugador] == PUAS:
        puas.add(jugador)

    if not nivel.requiere_diamantes:
        diamantes = set()  # no hacen falta: no los seguimos (el espacio de búsqueda es mucho menor)
    return Estado(jugador, frozenset(rocas), frozenset(diamantes), frozenset(llaves),
                  frozenset(puertas), bool(tiene_llave), frozenset(puas), frozenset(agujeros))


def desde_texto(texto, **reglas):
    """Construye (nivel, estado) desde un dibujo en texto. Útil para pruebas."""
    filas = [linea.strip() for linea in texto.strip().splitlines()]
    etiquetas = [[ETIQUETA_DE_SIMBOLO[ch] for ch in fila] for fila in filas]
    columnas = len(filas[0])
    jugador = next(f * columnas + c for f, fila in enumerate(filas)
                   for c, ch in enumerate(fila) if ch in "Pp")
    con_llave = any("p" in fila for fila in filas)
    nivel = construir_nivel(etiquetas, jugador, **reglas)
    return nivel, construir_estado(nivel, etiquetas, jugador, con_llave)


def dibujar(nivel, e):
    """Devuelve el estado como texto (para imprimir en consola)."""
    base = {PARED: "#", SUELO: ".", AGUJERO: "O", BOTON: "B",
            PUERTA_METALICA: "M", SALIDA: "E", PUAS: "^"}
    lineas = []
    for f in range(nivel.filas):
        fila = []
        for c in range(nivel.columnas):
            i = f * nivel.columnas + c
            t = nivel.tipo[i]
            ch = base[t]
            if t == AGUJERO and i in e.agujeros_llenos:
                ch = "o"
            if t == PUAS and i in e.puas_pisadas:
                ch = "X"
            if t == PUERTA_METALICA and nivel.puerta_abierta(i, e.rocas):
                ch = "m"
            if i in e.puertas_llave:
                ch = "L"
            if i in e.llaves:
                ch = "K"
            if i in e.diamantes:
                ch = "D"
            if i in e.rocas:
                ch = "b" if t == BOTON else "R"
            if i == e.jugador:
                ch = "p" if e.tiene_llave else "P"
            fila.append(ch)
        lineas.append("".join(fila))
    return "\n".join(lineas)

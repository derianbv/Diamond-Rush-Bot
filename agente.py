"""
Agente inteligente para Diamond Rush.

Ciclo del agente (percibir -> planificar -> actuar -> verificar):
  1. SENSOR: captura el tablero y clasifica cada casilla (vision.py).
  2. MODELO: convierte la grilla en un Nivel + Estado (juego.py).
  3. PLAN:   A* sobre el espacio de estados (solver.py).
  4. ACTUADOR: presiona las teclas (controles.py). Después de cada tecla
     espera a VER al jugador en la casilla esperada antes de seguir. Si algo
     no coincide con lo que predijo el modelo, vuelve a leer la pantalla y
     re-planifica desde la situación real.

Uso:
  python agente.py calibrar      # marcar el tablero en pantalla (una vez por computador)
  python agente.py etiquetar     # enseñar cómo se ve cada objeto
  python agente.py ver           # leer el tablero y mostrar el plan, SIN mover nada
  python agente.py probar        # medir cuánto tarda un movimiento
  python agente.py jugar         # jugar el nivel que está en pantalla
  python agente.py jugar --continuo   # seguir con los niveles siguientes
  python agente.py f8            # espera a que presiones F8 en el juego y lo juega (F9 = cancelar)
"""
import argparse
import sys
import time

import config
from controles import (METODOS, VK_F8, VK_F9, activar_dpi, click, minimizar, presionar,
                       restaurar, tecla_global, ventana_consola)
from juego import construir_estado, construir_nivel, dibujar, SALIDA
from solver import resolver


# jugar_nivel devuelve True (ganó), False (no pudo empezar: no ve el juego, no hay
# plan o las teclas no llegan) o ATASCADO (empezó a jugar y quedó sin salida:
# solo en ese caso sirve reiniciar el nivel).
ATASCADO = "atascado"
SIN_PLAN = "sin_plan"   # desde lo que se ve no hay solución (¿el nivel ya estaba trabado?)

# Lo aprendido sobre botones/puertas mientras se juega un nivel. Solo sirve si
# hay que reiniciar ESE intento; al empezar un nivel nuevo se borra.
MEMORIA_PUERTAS = {}


def tecla(cfg, paso, duracion=None, metodo=None):
    presionar(cfg["teclas"][paso], duracion or cfg["tiempo_tecla"], metodo or cfg["metodo_teclas"])


def preparar(cfg):
    from vision import Capturador, crear_clasificador
    if not cfg.get("roi"):
        sys.exit("No hay tablero calibrado. Ejecuta primero: python agente.py calibrar")
    return Capturador(cfg["roi"]), crear_clasificador(cfg)


def leer_estable(cap, clf, intentos=20, pausa=0.03):
    """Lee el tablero hasta que dos capturas seguidas den lo mismo
    (así no leemos a mitad de una animación)."""
    anterior = None
    for _ in range(intentos):
        lectura = clf.clasificar(cap.capturar())
        if anterior is not None and lectura.etiquetas == anterior.etiquetas and lectura.jugador == anterior.jugador:
            return lectura
        anterior = lectura
        time.sleep(pausa)
    return anterior


def armar(cfg, clf, lectura, nivel=None, previo=None):
    """Lectura de pantalla -> (nivel, estado)."""
    if lectura.jugador < 0:
        raise RuntimeError("No encuentro al jugador en pantalla.")
    if nivel is None:
        nivel = construir_nivel(lectura.etiquetas, lectura.jugador, cfg["entra_al_abrir_puerta"],
                                cfg["roca_sobre_puas"], cfg["roca_sobre_diamante"])
        # Si ya jugamos este mismo nivel (p.ej. antes de reiniciarlo), recordamos
        # qué botones abren qué puertas.
        nivel.candidatos = MEMORIA_PUERTAS.setdefault(tuple(nivel.tipo), nivel.candidatos)
    # Si no tenemos plantilla de "personaje_con_llave", confiamos en el modelo.
    if previo is not None and not clf.hay_con_llave:
        tiene_llave = previo.tiene_llave
    else:
        tiene_llave = lectura.con_llave
    estado = construir_estado(nivel, lectura.etiquetas, lectura.jugador, tiene_llave, previo)
    return nivel, estado


def diagnostico(lectura, nivel, estado):
    print("Lo que veo (P jugador, # pared, . suelo, D diamante, K llave, L puerta llave,")
    print("            ^ púas, X púas activas, R roca, O agujero, B botón, M puerta metálica, E salida, ? desconocido):")
    print(lectura.texto())
    desconocidas = sum(fila.count("desconocido") for fila in lectura.etiquetas)
    print(f"\nJugador en fila {estado.jugador // nivel.columnas}, columna {estado.jugador % nivel.columnas} "
          f"(parecido {lectura.dist_jugador:.1f}) | diamantes: {len(estado.diamantes)} (compáralo con el contador del juego) | rocas: {len(estado.rocas)} "
          f"| llaves: {len(estado.llaves)} | lleva llave: {estado.tiene_llave}")
    if desconocidas:
        print(f"[!] {desconocidas} casillas desconocidas (se tratan como pared). Usa `etiquetar` para corregirlas.")
    if SALIDA not in nivel.tipo:
        print("[!] No veo la salida. Etiqueta la puerta objetivo con `etiquetar`.")


def planificar(cfg, nivel, estado):
    t = time.perf_counter()
    plan = resolver(nivel, estado, cfg["tiempo_planificacion"], espera_mejor=cfg["esperar_mejor_plan"])
    print(f"Planificación: {time.perf_counter() - t:.2f}s -> "
          + (f"{len(plan)} movimientos" if plan else "SIN SOLUCIÓN"))
    return plan


def esperar_jugador(cap, clf, destino, timeout):
    """Espera hasta ver al jugador en `destino`. Devuelve True si llegó."""
    fin = time.perf_counter() + timeout
    while True:
        if clf.clasificar(cap.capturar()).jugador == destino:
            return True
        if time.perf_counter() > fin:
            return False


def puertas_abiertas(nivel, lectura):
    """Puertas metálicas que en pantalla NO se ven cerradas."""
    return {p for p in nivel.candidatos
            if lectura.etiquetas[p // nivel.columnas][p % nivel.columnas] != "puerta_metalica"}


def _coincide(visto, esperado):
    return (visto.rocas == esperado.rocas and visto.diamantes == esperado.diamantes
            and visto.puertas_llave == esperado.puertas_llave)


def probar_metodos(cfg, cap, clf, paso, destino):
    """La primera tecla no movió al personaje: probar otras formas de enviar
    teclas (y como último recurso un clic en el juego para darle foco).
    Si alguna funciona, se guarda en config.json para la próxima vez."""
    actual = (cfg["metodo_teclas"], cfg["tiempo_tecla"])
    opciones = [(m, d, False) for d in (cfg["tiempo_tecla"], 0.08, 0.15) for m in METODOS]
    opciones += [(m, 0.08, True) for m in METODOS]
    for metodo, duracion, con_click in opciones:
        if (metodo, duracion) == actual and not con_click:
            continue
        if con_click:
            x, y, w, h = cfg["roi"]
            click(x + w / 2, y + h / 2)
            time.sleep(0.3)
        tecla(cfg, paso, duracion, metodo)
        if esperar_jugador(cap, clf, destino, 0.8):
            print(f"[i] Las teclas funcionan con el método '{metodo}' ({duracion * 1000:.0f} ms)"
                  + (" después de un clic" if con_click else "") + ". Guardado en config.json.")
            cfg["metodo_teclas"], cfg["tiempo_tecla"] = metodo, duracion
            if con_click:
                cfg["click_para_foco"] = True
            config.guardar(cfg)
            return True
    print("[!] Ninguna forma de enviar teclas movió al personaje. Revisa que el juego tenga el foco "
          "(haz clic dentro del juego) y que nada lo tape.")
    return False


def jugar_nivel(cfg, cap, clf, hacer_click=True):
    if hacer_click and cfg["click_para_foco"]:
        x, y, w, h = cfg["roi"]
        click(x + w / 2, y + h / 2)  # dar foco al juego (antes de leer, por si el clic cambia algo)
        time.sleep(0.3)

    lectura = leer_estable(cap, clf)
    nivel, estado = armar(cfg, clf, lectura)
    nivel.observar_puertas(estado.rocas, puertas_abiertas(nivel, lectura), estado.jugador)
    diagnostico(lectura, nivel, estado)
    plan = planificar(cfg, nivel, estado)
    if not plan:
        return SIN_PLAN

    replanificaciones = 0
    reintentos = 0
    movimientos = 0
    i = 0
    t_inicio = time.perf_counter()  # el tiempo cuenta desde la primera tecla
    while True:
        paso = plan[i]
        siguiente, gano = nivel.mover(estado, paso)
        tecla(cfg, paso)
        movimientos += 1
        if gano:
            print(f"\n*** Nivel terminado: {movimientos} movimientos en {time.perf_counter() - t_inicio:.2f}s ***")
            return True

        ok = llego = esperar_jugador(cap, clf, siguiente.jugador, cfg["timeout_movimiento"])
        if not llego and movimientos == 1 and siguiente.jugador != estado.jugador:
            # Primera tecla sin efecto: ¿el juego no recibe las teclas así?
            ok = llego = probar_metodos(cfg, cap, clf, paso, siguiente.jugador)
            if not llego:
                return False
        motivo = "el jugador no llegó a la casilla esperada"
        hubo_evento = siguiente._replace(jugador=estado.jugador, puas_pisadas=estado.puas_pisadas) != estado
        if ok and hubo_evento:
            # Se movió una roca, se recogió algo o se abrió una puerta: comprobar con la vista.
            for _ in range(2):
                lectura = leer_estable(cap, clf)
                _, visto = armar(cfg, clf, lectura, nivel, siguiente)
                if _coincide(visto, siguiente):
                    break
                time.sleep(0.12)
            else:
                ok, motivo = False, "el tablero no quedó como predijo el modelo"
            if ok and nivel.candidatos and nivel.observar_puertas(
                    visto.rocas, puertas_abiertas(nivel, lectura), visto.jugador):
                ok, motivo = False, "aprendí qué botón abre cada puerta metálica"

        if ok:
            estado = siguiente
            i += 1
            reintentos = 0
            if cfg["pausa_extra"] > 0:
                time.sleep(cfg["pausa_extra"])
            continue

        if not llego:
            # ¿La tecla simplemente no entró? (en pantalla no cambió nada)
            lectura = leer_estable(cap, clf)
            try:
                _, visto = armar(cfg, clf, lectura, nivel, estado)
            except RuntimeError:
                visto = None
            if visto is not None and visto.jugador == estado.jugador and _coincide(visto, estado):
                reintentos += 1
                if reintentos <= 2:
                    print(f"[.] Paso {movimientos} ({paso}): la tecla no tuvo efecto, la repito")
                    continue
                # El modelo cree que se puede, pero el juego no lo deja: lo aprendemos.
                nivel.bloqueados.add((estado.jugador, paso, estado.rocas))
                motivo = "el juego no permite este movimiento (queda marcado como bloqueado)"
        reintentos = 0

        # Algo salió distinto: re-leer la pantalla y re-planificar
        replanificaciones += 1
        print(f"[!] Paso {movimientos} ({paso}): {motivo}. Re-planificando ({replanificaciones})...")
        if replanificaciones > cfg["max_replanificaciones"]:
            print("Demasiadas re-planificaciones, me detengo.")
            return ATASCADO
        time.sleep(0.15)
        lectura = leer_estable(cap, clf)
        try:
            _, estado = armar(cfg, clf, lectura, nivel, siguiente if llego else estado)
        except RuntimeError as e:
            print("   ", e)
            return False
        print(dibujar(nivel, estado))
        # Aquí el reloj ya corre: re-planificación rápida, sin lanzar procesos.
        plan = resolver(nivel, estado, min(30.0, cfg["tiempo_planificacion"]), verbose=False, paralelo=False)
        if not plan:
            print("No encontré solución desde aquí.")
            return ATASCADO
        i = 0


def esperar_nuevo_nivel(cap, clf, texto_anterior, timeout=180):
    print("Esperando el siguiente nivel...")
    time.sleep(1.5)
    fin = time.perf_counter() + timeout
    while time.perf_counter() < fin:
        lectura = leer_estable(cap, clf)
        hay_salida = any(et.startswith("puerta_objetivo") or et == "objetivo_ultimo_nivel"
                         for fila in lectura.etiquetas for et in fila)
        if lectura.jugador >= 0 and hay_salida and lectura.texto() != texto_anterior:
            time.sleep(0.3)
            return True
        time.sleep(0.3)
    return False


def comando_ver(cfg, imagen=None):
    from vision import crear_clasificador
    import cv2
    if imagen:
        clf = crear_clasificador(cfg)
        lectura = clf.clasificar(cv2.imread(imagen))
    else:
        cap, clf = preparar(cfg)
        lectura = leer_estable(cap, clf)
    nivel, estado = armar(cfg, clf, lectura)
    diagnostico(lectura, nivel, estado)
    plan = planificar(cfg, nivel, estado)
    if plan:
        print("Plan:", " ".join(plan))


def comando_probar(cfg):
    """Hace un movimiento válido y lo deshace, midiendo cuánto tarda en verse."""
    cap, clf = preparar(cfg)
    if cfg["click_para_foco"]:
        x, y, w, h = cfg["roi"]
        click(x + w / 2, y + h / 2)
        time.sleep(0.3)
    nivel, estado = armar(cfg, clf, leer_estable(cap, clf))
    opuesto = {"arriba": "abajo", "abajo": "arriba", "izquierda": "derecha", "derecha": "izquierda"}
    for paso in opuesto:
        r = nivel.mover(estado, paso)
        if r is None or r[1] or r[0]._replace(jugador=estado.jugador) != estado:
            continue  # solo movimientos "limpios" (sin recoger ni empujar nada)
        for p, destino in ((paso, r[0].jugador), (opuesto[paso], estado.jugador)):
            t = time.perf_counter()
            tecla(cfg, p)
            ok = esperar_jugador(cap, clf, destino, 1.0)
            if not ok and p == paso:
                ok = probar_metodos(cfg, cap, clf, p, destino)
            print(f"{p}: {'llegó' if ok else 'NO llegó'} en {time.perf_counter() - t:.3f}s")
            if not ok:
                return
            time.sleep(0.3)
        return
    print("No hay un movimiento limpio disponible para probar.")


def main():
    activar_dpi()
    parser = argparse.ArgumentParser(description="Agente Diamond Rush")
    parser.add_argument("comando", choices=["calibrar", "etiquetar", "revisar", "ver", "probar", "jugar", "f8"])
    parser.add_argument("--continuo", action="store_true", help="seguir jugando los niveles siguientes")
    parser.add_argument("--imagen", help="(ver) usar una captura guardada en vez de la pantalla")
    parser.add_argument("--espera", type=float, default=0, help="segundos de espera antes de empezar")
    args = parser.parse_args()
    cfg = config.cargar()

    # La consola no debe tapar el juego: se minimiza mientras el agente mira la pantalla.
    consola = None
    if not args.imagen:
        consola = ventana_consola()
        if consola:
            print("Minimizo esta consola para que no tape el juego (vuelve al terminar)...")
            minimizar(consola)
    args.consola = consola
    try:
        if args.espera:
            print(f"Empiezo en {args.espera:.0f} s...")
            time.sleep(args.espera)
        ejecutar_comando(cfg, args)
    except RuntimeError as e:
        print(f"[!] {e}")
    finally:
        restaurar(consola)


def reiniciar_nivel(cfg):
    """Clic en el botón de reiniciar del juego (esquina superior derecha)."""
    x, y, w, h = cfg["roi"]
    rx, ry = cfg["boton_reiniciar"]
    print("Reiniciando el nivel con el botón del juego...")
    click(x + rx * w, y + ry * h)
    time.sleep(2.0)


def ejecutar_comando(cfg, args):
    if args.comando == "calibrar":
        from herramientas import calibrar
        calibrar(cfg)
    elif args.comando == "etiquetar":
        from herramientas import etiquetar
        etiquetar(cfg, args.consola)
    elif args.comando == "revisar":
        from herramientas import revisar_ejemplos
        revisar_ejemplos()
    elif args.comando == "ver":
        comando_ver(cfg, args.imagen)
    elif args.comando == "probar":
        comando_probar(cfg)
    elif args.comando == "jugar":
        cap, clf = preparar(cfg)
        primero = True
        while True:
            texto = clf.clasificar(cap.capturar()).texto()
            gano = jugar_con_reintentos(cfg, cap, clf, hacer_click=primero)
            primero = False
            if not (args.continuo and gano):
                break
            if not esperar_nuevo_nivel(cap, clf, texto):
                break
    elif args.comando == "f8":
        comando_f8(cfg)


def jugar_con_reintentos(cfg, cap, clf, hacer_click):
    """Juega el nivel; si se atasca, lo reinicia (hasta 2 veces) recordando
    lo aprendido sobre las puertas EN ESTE intento."""
    MEMORIA_PUERTAS.clear()  # nivel nuevo: no se usa nada de partidas anteriores
    for intento in range(3):
        try:
            resultado = jugar_nivel(cfg, cap, clf, hacer_click=hacer_click and intento == 0)
        except RuntimeError as e:
            print(f"[!] {e}")
            return False
        if resultado is True:
            return True
        # Reiniciar sirve si se atascó jugando, o si al empezar ya no había
        # solución (el nivel venía trabado): en ese caso, una sola vez.
        reiniciable = resultado == ATASCADO or (resultado == SIN_PLAN and intento == 0)
        if not reiniciable or not cfg["reiniciar_si_falla"] or intento == 2:
            return False
        reiniciar_nivel(cfg)
    return False


def comando_f8(cfg):
    """Espera a que el usuario presione F8 (estando en el navegador, así el
    juego ya tiene el foco) y juega el nivel que está en pantalla."""
    cap, clf = preparar(cfg)
    tecla_global(VK_F8)
    tecla_global(VK_F9)  # descartar pulsaciones viejas
    while True:
        if tecla_global(VK_F9):
            print("Cancelado.")
            return
        if tecla_global(VK_F8):
            break
        time.sleep(0.03)
    jugar_con_reintentos(cfg, cap, clf, hacer_click=False)


if __name__ == "__main__":
    main()

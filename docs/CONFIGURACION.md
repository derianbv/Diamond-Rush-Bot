# Configurar el agente en cualquier computador

Guía paso a paso para dejar el agente funcionando en un computador nuevo, por ejemplo
el del torneo o el de la universidad. Toma unos 10 minutos la primera vez.

---

## 0. Qué se necesita

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10 u 11 de 64 bits |
| Python | 3.10, 3.11, 3.12 o 3.13 |
| Navegador | Chrome, Edge o Firefox, con el juego abierto: <https://www.minijuegos.com/juego/diamond-rush> |
| Internet | No hace falta: las librerías vienen incluidas en `paquetes/` (ver el paso 1.3) |

El agente funciona en computadores lentos. Calcula más despacio, pero en un PC de 4 núcleos
el nivel más difícil se resuelve en menos de 1 minuto (el límite del torneo es 2 minutos).

---

## 1. Preparar el computador

### 1.1 Instalar Python (si no está)

1. Entrar a <https://www.python.org/downloads/> y descargar la última versión.
2. Al instalar, **marcar la casilla "Add Python to PATH"**.
3. Elegir la instalación normal. No necesita permisos de administrador: se instala para tu usuario.

Para comprobarlo, abre una terminal (tecla Windows → `cmd`) y escribe `python --version` o `py --version`.
Debe responder algo como `Python 3.12.x`.

### 1.2 Descargar el agente

- **Con Git**: `git clone <url-del-repositorio>`
- **Sin Git**: en la página del repositorio, botón **Code → Download ZIP**, y descomprimirlo.

Conviene una carpeta de **ruta corta**, por ejemplo `C:\DiamondRush`: en rutas muy largas
Windows no deja instalar algunas librerías (límite de 260 caracteres por ruta).

### 1.3 Librerías incluidas (sin internet)

El agente viene **listo para usar**:

- `paquetes/` trae las librerías (OpenCV, NumPy, mss) para Python 3.10 a 3.13, así que se
  instala **sin internet**.
- `plantillas/` trae el entrenamiento de la visión (unos 700 ejemplos), así que **no hay que
  entrenar nada**.

`INICIAR.bat` instala desde `paquetes/` y, solo si no puede (por ejemplo, con una versión de
Python que no está incluida), descarga de internet. Si alguna vez falta `paquetes/`,
`descargar_paquetes.bat` la vuelve a crear en un computador con internet.

---

## 2. Primera ejecución

Hacer doble clic en **`INICIAR.bat`**. La primera vez muestra:

```
Primera vez en este computador: creando el entorno de Python...
Instalando librerias...
Listo.
```

Tarda 1 a 3 minutos. Se crea una carpeta `.venv` que es propia de ese computador.
Si copias la carpeta de un PC a otro, `INICIAR.bat` detecta que esa `.venv` no sirve y la vuelve a crear.

Después se abre el menú:

```
------------------------------------------------------------
 DIAMOND RUSH · agente   (falta calibrar -> [6])
------------------------------------------------------------
  1  Jugar                   ve al juego y presiona F8 para empezar (F9 cancela)
  2  Ver lectura             qué ve el agente y su plan, sin mover nada
  3  Probar teclado          mueve al personaje 1 casilla y vuelve
  4  Re-calibrar             si moviste la ventana del navegador
  5  Re-entrenar             etiquetar o revisar ejemplos
  6  Configuración completa  primera vez u otro computador
  0  Salir
```

Cada opción se elige con **una sola tecla**, sin ENTER.

---

## 3. Preparar el navegador

Antes de calibrar, y también antes de jugar:

1. Abrir <https://www.minijuegos.com/juego/diamond-rush> y entrar a un nivel.
2. Poner el **zoom del navegador en 100 %** (`Ctrl + 0`).
3. Dejar visible el juego completo, incluido el título "Level N" y los botones de arriba.
4. **No mover ni cambiar el tamaño de la ventana** después de calibrar, y no hacer scroll en la página.
   Si se mueve, hay que volver a calibrar (opción 4).

La consola del agente puede estar encima del juego: se minimiza sola cuando el agente mira la pantalla.

---

## 4. Configuración completa (opción 6)

La opción **6** recorre todos los pasos en orden. En cada paso explica qué hacer y pregunta
si salió bien: `S` sigue, `r` repite. Con ENTER se elige la opción que aparece en mayúscula.

### 4.1 Revisar instalación

Comprueba las librerías y ejecuta las pruebas internas. Debe terminar en `8/8 pruebas correctas`.

### 4.2 Abrir el juego

Recuerda lo del paso 3; si quieres, abre el juego en el navegador.

### 4.3 Calibrar el tablero

Le dice al agente **en qué parte de la pantalla está el juego**.

1. La consola se minimiza; a los 3 segundos se toma una foto de la pantalla y suena un pitido.
2. Se abre una ventana con esa foto y un **letrero amarillo**. Con el mouse, arrastra un rectángulo
   sobre **todo el juego**, de borde a borde, **incluyendo el título y los botones de arriba**.
   Presiona **ENTER**.
3. Aparece la grilla (10 columnas × 15 filas). Las líneas blancas deben caer sobre los bordes
   de las casillas, y el **marco celeste** debe encerrar el tablero jugable (8 × 12). Lo de afuera
   se oscurece porque es borde o título.

   | Tecla | Acción |
   |---|---|
   | `f` | **auto-ajuste** (conviene probarlo primero) |
   | `w` `a` `s` `d` | mover la grilla 1 píxel (en mayúscula, 5 píxeles) |
   | `j` / `l` | grilla más angosta / más ancha |
   | `i` / `k` | grilla más baja / más alta |
   | `ENTER` | guardar |
   | `ESC` | cancelar |

La calibración se guarda en `config.json`, que es propio de cada computador.

### 4.4 Etiquetar objetos (entrenamiento)

El agente **ya viene entrenado**: `plantillas/` trae unos 700 ejemplos sacados del walkthrough, que
reconocen bien el juego en distintas pantallas. Este paso muestra cuántos ejemplos hay y, si no
falta nada obligatorio, se puede saltar.

Solo hace falta etiquetar si en el paso siguiente aparece algo mal leído (ver sección 6).

### 4.5 Revisar la lectura

El agente lee la pantalla e imprime el tablero como lo entiende, **sin mover nada**:

```
Lo que veo (P jugador, # pared, . suelo, D diamante, ...):
########
.P......
#####R##
..DD.O..
...
Jugador en fila 1, columna 1 | diamantes: 6 (compáralo con el contador del juego) | rocas: 5 ...
Planificación: 0.24s -> 47 movimientos
```

Hay que revisar dos cosas:

- Que el dibujo coincida con el juego.
- Que el **número de diamantes** sea igual al del contador del juego (por ejemplo "0/6").

| Símbolo | Objeto | Símbolo | Objeto |
|---|---|---|---|
| `P` / `p` | jugador / jugador con llave | `R` | roca |
| `#` | pared | `O` / `o` | agujero / agujero tapado |
| `.` | suelo | `B` / `b` | botón / botón con roca |
| `D` | diamante | `M` / `m` | puerta metálica cerrada / abierta |
| `K` | llave | `E` / `e` | salida cerrada / abierta |
| `L` | puerta de llave | `$` | estatua (último nivel) |
| `^` / `X` | púas / púas ya pisadas | `?` | no reconocido (se toma como pared) |

### 4.6 Probar el teclado

El agente mueve al personaje una casilla y lo regresa. Debe decir `llegó en 0.xxx s` las dos veces.

Si la tecla no mueve al personaje, el agente **prueba solo otras formas de enviar teclas**
(otro código de tecla, mantenerla más tiempo y, al final, un clic en el juego) y guarda en
`config.json` la que funcione. Si ninguna funciona, ver la sección 7.

---

## 5. Jugar (opción 1)

1. En el menú, presiona **1**. La consola se minimiza.
2. Ve al navegador y deja el nivel listo.
3. Presiona **F8**. El agente lee el tablero, **calcula el plan** (de menos de 1 s a ~1 minuto,
   según el nivel) y juega. **No toques el mouse ni el teclado** mientras juega.
   Para cancelar antes de empezar, presiona **F9**.
4. Al terminar vuelve la consola con el resultado (`*** Nivel terminado: 47 movimientos en 12.3s ***`)
   y el menú, listo para el siguiente nivel.

Por qué F8: al presionarlo, el navegador ya es la ventana activa, así que las teclas del agente
le llegan directo al juego.

Si el agente se atasca (por ejemplo, porque descubre que un botón no abre la puerta que esperaba),
reinicia el nivel con el botón del juego, como máximo 2 veces, y vuelve a calcular.

---

## 6. Re-entrenar (opción 5)

Sirve cuando la lectura tiene errores (`?` o un objeto confundido). Opciones:

| Tecla | Acción |
|---|---|
| `e` | abrir el **etiquetador** |
| `n` | crear un **objeto nuevo** (algo que no está en la lista) |
| `r` | **revisar** ejemplos guardados y borrar los mal etiquetados |
| `b` | borrar todos los ejemplos y empezar de cero (se guarda una copia) |
| `v` | volver |

### El etiquetador

Se abre una ventana al lado del juego, con las teclas escritas a la derecha.

1. **Clic** en una o varias casillas, que quedan marcadas en amarillo.
2. Presiona la **tecla del objeto**: `1` jugador, `4` o `#` pared, `3` o `.` suelo, `5` diamante,
   `7` salida cerrada… La lista completa está en la ventana.
3. Si no recuerdas la tecla, presiona **ENTER**: en la consola aparece la **lista completa**
   numerada; escribe el número del objeto.
4. Si el objeto no existe en la lista, presiona `n` y créalo. Te pide un nombre, **cómo se comporta**
   (pared, suelo, diamante, salida…) y una tecla.

Otros controles: `ESPACIO` toma otra captura, `u` deshace lo último, `r` abre la galería de
ejemplos, clic derecho limpia la selección y `ESC` sale.

Consejos:

- Selecciona **varios ejemplos** de cada cosa: con más ejemplos hay menos errores.
- Juega a mano para que aparezcan estados nuevos (personaje con llave, púas pisadas, puerta abierta)
  y captúralos con `ESPACIO`.
- Si la ventana dice **"NO RECONOZCO EL JUEGO"**, algo está tapando el juego.
- Un clic en la casilla equivocada puede hacer que el agente lea mal (por ejemplo, suelo como
  agujero). La galería (`r`) sirve para encontrar y borrar esos ejemplos.

---

## 7. Problemas frecuentes

| Problema | Solución |
|---|---|
| `No encontre Python` al abrir `INICIAR.bat` | Instalar Python marcando "Add Python to PATH" (paso 1.1) y volver a abrir el `.bat` |
| Falla la instalación de librerías | Usar Python 3.10 a 3.13 (las versiones incluidas en `paquetes/`), o revisar internet |
| Error `El nombre del archivo o la extensión es demasiado largo` | La carpeta está en una ruta muy larga: moverla a `C:\DiamondRush`, borrar `.venv` y volver a abrir `INICIAR.bat` |
| `No encuentro al jugador en pantalla` | El juego está tapado, se movió la ventana (opción 4) o el zoom no está en 100 % |
| Muchas casillas `?` o diamantes de menos | Recalibrar (4); si sigue, re-entrenar (5) con esas casillas |
| El personaje no se mueve | Opción 3: el agente prueba otras formas de enviar teclas. Hacer clic una vez dentro del juego y usar F8 desde el navegador |
| La grilla queda corrida | En la calibración, `f` (auto-ajuste) y luego `w a s d` / `j l i k` |
| La escala de Windows es 125 % o 150 % | Funciona igual, pero calibra **después** de elegir la escala y no la cambies |
| Hay dos monitores | El juego debe estar en el monitor principal (o cambiar `"monitor"` en `config.json`) |
| `SIN SOLUCIÓN` en un nivel empezado | El nivel quedó trabado (por ejemplo, una roca mal empujada): el agente reinicia el nivel una vez |

---

## 8. Ajustes (`config.json`)

`config.json` se crea al calibrar. Los valores que no aparecen ahí se toman de `config.py`.

| Ajuste | Por defecto | Para qué |
|---|---|---|
| `roi` | (calibración) | posición del juego en la pantalla `[x, y, ancho, alto]` |
| `monitor` | `1` | monitor donde está el juego |
| `tiempo_planificacion` | `100` | segundos máximos para calcular el plan |
| `esperar_mejor_plan` | `15` | tras el primer plan, segundos extra buscando uno más corto (antes de la primera tecla, no cuentan en el torneo) |
| `timeout_movimiento` | `0.6` | si el personaje no llega en ese tiempo, el agente revisa qué pasó |
| `tiempo_tecla`, `metodo_teclas` | `0.03`, `vk_scan` | cómo se envían las teclas (la opción 3 los ajusta sola) |
| `reiniciar_si_falla` | `true` | reiniciar el nivel si el agente se atasca |
| `boton_reiniciar` | `[0.85, 0.10]` | dónde está el botón de reiniciar, relativo al juego |
| `entra_al_abrir_puerta` | `true` | regla: al abrir una puerta de llave el personaje entra en el mismo paso |
| `roca_sobre_puas`, `roca_sobre_diamante` | `true`, `true` | reglas confirmadas en el walkthrough |

---

## 9. Uso sin menú (línea de comandos)

Desde la carpeta del agente:

```powershell
.venv\Scripts\python agente.py calibrar     # marcar el juego en pantalla
.venv\Scripts\python agente.py etiquetar    # etiquetador
.venv\Scripts\python agente.py revisar      # galería de ejemplos
.venv\Scripts\python agente.py ver          # leer y planificar sin mover nada
.venv\Scripts\python agente.py probar       # probar el teclado
.venv\Scripts\python agente.py f8           # esperar F8 y jugar el nivel
.venv\Scripts\python agente.py jugar        # jugar ya (hace clic en el juego para darle foco)
.venv\Scripts\python agente.py ver --imagen captura.png   # leer una captura guardada
```

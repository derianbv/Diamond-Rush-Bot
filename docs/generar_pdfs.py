"""
Genera los PDF de la documentación a partir de los .md de esta carpeta.

    docs/CONFIGURACION.md  ->  docs/Guia_de_configuracion.pdf
    docs/FUNCIONAMIENTO.md ->  docs/Documentacion_tecnica.pdf

Requisitos (solo para regenerar los PDF, el agente no los necesita):
    pip install markdown pypdf reportlab
    y Microsoft Edge instalado (se usa para imprimir el HTML a PDF).

Uso:  python docs/generar_pdfs.py
"""
import html
import io
import os
import re
import shutil
import subprocess
import tempfile
import time

import markdown
from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

AQUI = os.path.dirname(os.path.abspath(__file__))
EDGE = next((r for r in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                         r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") if os.path.exists(r)), None)

DOCUMENTOS = [
    {
        "md": "CONFIGURACION.md",
        "pdf": "Guia_de_configuracion.pdf",
        "titulo": "Guía de configuración",
        "subtitulo": "Cómo instalar y poner a punto el agente en cualquier computador, paso a paso",
    },
    {
        "md": "FUNCIONAMIENTO.md",
        "pdf": "Documentacion_tecnica.pdf",
        "titulo": "Documentación técnica",
        "subtitulo": "Cómo funciona el agente por dentro: visión, modelo del juego, búsqueda A* y ejecución",
    },
]

PROYECTO = "Agente inteligente para Diamond Rush"
CURSO = "Proyecto de Sistemas Inteligentes"
FECHA = "Octubre de 2026"

CSS = """
@page { size: A4; margin: 18mm 17mm 20mm 17mm; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }
body { font-family: "Segoe UI", Calibri, Arial, sans-serif; font-size: 10.3pt; line-height: 1.5;
       color: #1d2b36; margin: 0; }
a { color: #0b5d80; text-decoration: none; }
h1 { display: none; }
h2 { font-size: 15.5pt; color: #0b4f6c; border-bottom: 2px solid #0b4f6c; padding-bottom: 3px;
     margin: 20pt 0 8pt; break-after: avoid; }
h3 { font-size: 12pt; color: #146186; margin: 13pt 0 5pt; break-after: avoid; }
p { margin: 5pt 0; }
ul, ol { margin: 4pt 0 6pt; padding-left: 18pt; }
li { margin: 2pt 0; }
hr { display: none; }
table { border-collapse: collapse; width: 100%; margin: 7pt 0 9pt; font-size: 9.3pt; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
th { background: #0b4f6c; color: #fff; text-align: left; padding: 5px 7px; font-weight: 600; }
td { border-bottom: 1px solid #d6e0e8; padding: 4px 7px; vertical-align: top; }
tr:nth-child(even) td { background: #f3f7fa; }
code { font-family: Consolas, "Cascadia Mono", monospace; font-size: 8.9pt; background: #edf2f6;
       padding: 0 3px; border-radius: 3px; }
pre { background: #f4f7f9; border: 1px solid #d6e0e8; border-left: 4px solid #0b4f6c; border-radius: 4px;
      padding: 7px 10px; font-size: 8.7pt; line-height: 1.35; white-space: pre-wrap; break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 8.7pt; }
.formula { text-align: center; font-family: "Cambria Math", Cambria, serif; font-size: 12.5pt;
           margin: 9pt 0; padding: 8pt; background: #f2f7fb; border-radius: 6px; break-inside: avoid; }
strong { color: #0f2f40; }

/* Portada */
.portada { height: 255mm; display: flex; flex-direction: column; justify-content: center; break-after: page; }
.portada .banda { width: 70mm; height: 6px; background: #0b4f6c; margin-bottom: 14mm; }
.portada .proyecto { font-size: 13pt; color: #146186; letter-spacing: .5px; text-transform: uppercase; }
.portada .titulo { font-size: 34pt; font-weight: 700; color: #0b2f40; margin: 4mm 0 5mm; line-height: 1.1; }
.portada .subtitulo { font-size: 14pt; color: #34495e; max-width: 150mm; }
.portada .pie { margin-top: 40mm; font-size: 11pt; color: #52606d; border-top: 1px solid #cbd5df; padding-top: 4mm; }

/* Índice */
.indice { break-after: page; }
.indice h2 { margin-top: 0; }
.indice ol { list-style: none; padding: 0; margin-top: 8pt; }
.indice li { display: flex; align-items: baseline; font-size: 11.5pt; margin: 5pt 0; }
.indice li .t { white-space: nowrap; }
.indice li .p { flex: 1; border-bottom: 1px dotted #9aa5b1; margin: 0 6px; transform: translateY(-3px); }
.indice li .n { color: #0b4f6c; font-weight: 600; }

/* Diagrama del ciclo del agente */
.flujo { display: flex; align-items: stretch; justify-content: space-between; margin: 10pt 0 4pt; break-inside: avoid; }
.caja { flex: 1; border: 1.5px solid #0b4f6c; border-radius: 7px; padding: 6px 4px; text-align: center;
        background: #f2f7fb; font-size: 9pt; }
.caja b { display: block; color: #0b4f6c; font-size: 10pt; }
.caja span { color: #52606d; }
.flecha { align-self: center; color: #0b4f6c; font-size: 16pt; padding: 0 4px; }
.retorno { text-align: center; font-size: 9.3pt; color: #0b4f6c; border: 1.5px dashed #0b4f6c; border-radius: 7px;
           padding: 5px; margin: 4pt 0 10pt; break-inside: avoid; }
"""

DIAGRAMA = """
<div class="flujo">
  <div class="caja"><b>Pantalla</b><span>captura de la zona<br>del juego (mss)</span></div>
  <div class="flecha">&#10140;</div>
  <div class="caja"><b>Visión</b><span>vision.py<br>qué hay en cada casilla</span></div>
  <div class="flecha">&#10140;</div>
  <div class="caja"><b>Modelo</b><span>juego.py<br>Nivel + Estado + reglas</span></div>
  <div class="flecha">&#10140;</div>
  <div class="caja"><b>Planificación</b><span>solver.py<br>A* en paralelo</span></div>
  <div class="flecha">&#10140;</div>
  <div class="caja"><b>Teclado</b><span>controles.py<br>SendInput</span></div>
</div>
<div class="retorno">&#8634; agente.py: después de cada tecla mira la pantalla; si algo no coincide con lo
predicho, vuelve a leer el tablero y re-planifica</div>
"""


def a_html(texto_md):
    """Markdown -> HTML, con los arreglos propios de estos documentos."""
    # El diagrama de texto del documento técnico se reemplaza por uno dibujado
    texto_md = re.sub(r"```\n[^`]*agente\.py: verificar cada paso[^`]*```", "MARCADORDIAGRAMA", texto_md)
    cuerpo = markdown.markdown(texto_md, extensions=["tables", "fenced_code", "toc", "sane_lists"])
    cuerpo = cuerpo.replace("<p>MARCADORDIAGRAMA</p>", DIAGRAMA)
    # Bloques ```formula -> fórmula centrada
    cuerpo = re.sub(r'<pre><code class="language-formula">(.*?)</code></pre>',
                    lambda m: f'<div class="formula">{m.group(1).strip()}</div>', cuerpo, flags=re.S)
    return cuerpo


def secciones(cuerpo):
    """(id, título) de cada sección principal (h2)."""
    return [(m.group(1), html.unescape(re.sub("<[^>]+>", "", m.group(2))))
            for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>', cuerpo)]


def pagina_html(doc, cuerpo, paginas=None):
    items = []
    for k, (ident, titulo) in enumerate(secciones(cuerpo)):
        n = paginas[k] if paginas else "&nbsp;"
        items.append(f'<li><a class="t" href="#{ident}">{html.escape(titulo)}</a><span class="p"></span>'
                     f'<span class="n">{n}</span></li>')
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>{doc['titulo']} - {PROYECTO}</title><style>{CSS}</style></head><body>
<section class="portada">
  <div class="banda"></div>
  <div class="proyecto">{PROYECTO}</div>
  <div class="titulo">{doc['titulo']}</div>
  <div class="subtitulo">{doc['subtitulo']}</div>
  <div class="pie">{CURSO}<br>{FECHA}</div>
</section>
<section class="indice"><h2>Contenido</h2><ol>{''.join(items)}</ol></section>
{cuerpo}
</body></html>"""


def imprimir(html_texto, destino):
    """HTML -> PDF con Edge en modo sin ventana."""
    tmp = tempfile.mkdtemp(prefix="docs_pdf_")
    ruta_html = os.path.join(tmp, "doc.html")
    ruta_pdf = os.path.join(tmp, "doc.pdf")
    open(ruta_html, "w", encoding="utf-8").write(html_texto)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--user-data-dir={os.path.join(tmp, 'perfil')}",
                    f"--print-to-pdf={ruta_pdf}", "file:///" + ruta_html.replace("\\", "/")],
                   capture_output=True, timeout=120)
    # msedge.exe puede terminar antes que el proceso que imprime: esperar a que el
    # PDF exista y su tamaño deje de cambiar.
    tamano, fin = -1, time.time() + 90
    while time.time() < fin:
        if os.path.exists(ruta_pdf) and os.path.getsize(ruta_pdf) == tamano and tamano > 0:
            break
        tamano = os.path.getsize(ruta_pdf) if os.path.exists(ruta_pdf) else -1
        time.sleep(0.5)
    else:
        raise RuntimeError("Edge no generó el PDF")
    shutil.copy(ruta_pdf, destino)
    shutil.rmtree(tmp, ignore_errors=True)


def buscar_paginas(pdf, titulos):
    """Página (1 = portada) donde aparece cada título de sección."""
    textos = [re.sub(r"\s+", "", p.extract_text() or "") for p in PdfReader(pdf).pages]
    paginas, desde = [], 2  # la 1 es la portada y la 2 el índice
    for t in titulos:
        clave = re.sub(r"\s+", "", t)[:35]  # sin espacios: el PDF a veces los agrega junto al código
        n = next((i + 1 for i in range(desde, len(textos)) if clave in textos[i]), None)
        paginas.append(n or "")
        if n:
            desde = n - 1
    return paginas


def numerar(pdf, titulo):
    """Agrega pie de página (título del documento y número) a todas menos la portada."""
    lector = PdfReader(pdf)
    total = len(lector.pages)
    escritor = PdfWriter()
    for i, pagina in enumerate(lector.pages):
        if i > 0:
            capa = io.BytesIO()
            c = canvas.Canvas(capa, pagesize=A4)
            ancho, _ = A4
            c.setStrokeColor(HexColor("#cbd5df"))
            c.line(48, 40, ancho - 48, 40)
            c.setFont("Helvetica", 8)
            c.setFillColor(HexColor("#52606d"))
            c.drawString(48, 28, f"{PROYECTO} - {titulo}")
            c.drawRightString(ancho - 48, 28, f"{i + 1} / {total}")
            c.save()
            capa.seek(0)
            pagina.merge_page(PdfReader(capa).pages[0])
        escritor.add_page(pagina)
    escritor.add_metadata({"/Title": f"{titulo} - {PROYECTO}", "/Subject": CURSO})
    with open(pdf, "wb") as f:
        escritor.write(f)


def main():
    if not EDGE:
        raise SystemExit("No encontré Microsoft Edge para imprimir a PDF.")
    for doc in DOCUMENTOS:
        cuerpo = a_html(open(os.path.join(AQUI, doc["md"]), encoding="utf-8").read())
        destino = os.path.join(AQUI, doc["pdf"])
        imprimir(pagina_html(doc, cuerpo), destino)                       # 1ª pasada: ver dónde cae cada sección
        paginas = buscar_paginas(destino, [t for _, t in secciones(cuerpo)])
        imprimir(pagina_html(doc, cuerpo, paginas), destino)              # 2ª pasada: índice con páginas
        numerar(destino, doc["titulo"])
        print(f"{doc['pdf']}: {len(PdfReader(destino).pages)} páginas")


if __name__ == "__main__":
    main()

"""Genera docs/manual_usuario.pdf y docs/manual_tecnico.pdf a partir de los manuales en Markdown.

pandoc convierte cada manual en HTML autocontenido (imágenes incrustadas, tabla de contenido) y
Chromium (Playwright) lo imprime en A4 con encabezado y numeración de páginas.

Uso: python scripts/manuales_pdf.py   (requiere pandoc y playwright)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
MANUALES = {
    "manual_usuario": "Manual de usuario",
    "manual_tecnico": "Manual técnico",
}
SUBTITULO = (
    "Sistema de estimación de la susceptibilidad a deslizamientos por El Niño en el norte del Perú"
)
CSS = """
@page { size: A4; margin: 22mm 16mm 20mm 16mm; }
html { font-family: 'Noto Sans', 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt;
       line-height: 1.45; color: #111; }
body { margin: 0; max-width: none; }
header#title-block-header { text-align: center; padding: 70mm 0 0; page-break-after: always; }
header#title-block-header .title { font-size: 26pt; margin-bottom: 6mm; color: #1e3a8a; }
header#title-block-header .subtitle { font-size: 13pt; font-weight: normal; color: #333; }
header#title-block-header .author,
header#title-block-header .date { font-size: 11pt; color: #444; }
nav#TOC { page-break-after: always; }
nav#TOC > ul { padding-left: 0; } nav#TOC ul { list-style: none; } nav#TOC li { margin: 1.5mm 0; }
nav#TOC a { color: #111; text-decoration: none; }
h1, h2 { color: #1e3a8a; } h2 { page-break-before: always; border-bottom: 1px solid #c7d2fe;
       padding-bottom: 2mm; font-size: 16pt; }
h3 { font-size: 12.5pt; color: #1f2937; margin-top: 7mm; } h4 { font-size: 11pt; }
h2, h3, h4 { page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
img { max-width: 100%; max-height: 190mm; display: block; margin: 3mm auto;
      border: 1px solid #d1d5db; page-break-inside: avoid; }
figure { margin: 3mm 0 5mm; page-break-inside: avoid; }
figcaption { text-align: center; font-size: 9pt; color: #4b5563; }
table { border-collapse: collapse; width: 100%; margin: 3mm 0; font-size: 9pt;
        page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { background: #1e3a8a; color: #fff; text-align: left; padding: 1.5mm 2mm; }
td { border-bottom: 1px solid #e5e7eb; padding: 1.5mm 2mm; vertical-align: top; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.8pt; background: #f3f4f6;
       padding: 0 1mm; border-radius: 1mm; }
pre { background: #f3f4f6; padding: 3mm; border-radius: 1.5mm; white-space: pre-wrap;
      font-size: 8.5pt; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
hr { display: none; }
a { color: #1d4ed8; }
"""


def a_html(nombre: str, titulo: str, carpeta: Path) -> Path:
    """Convierte el manual en HTML autocontenido con portada y tabla de contenido."""
    css = carpeta / "manual.css"
    css.write_text(CSS, encoding="utf-8")
    texto = (DOCS / f"{nombre}.md").read_text(encoding="utf-8")
    # Título y versión van en la portada; el índice lo genera pandoc.
    lineas = texto.split("\n")
    texto = "\n".join(lineas[4:])
    texto = re.sub(r"\n## Contenido\n.*?(?=\n## |\n---)", "\n", texto, flags=re.S)
    fuente = carpeta / f"{nombre}.md"
    fuente.write_text(texto, encoding="utf-8")
    salida = carpeta / f"{nombre}.html"
    subprocess.run(
        [
            "pandoc",
            str(fuente),
            "-f",
            "gfm+attributes",
            "-t",
            "html5",
            "-s",
            "--embed-resources",
            "--resource-path",
            str(DOCS),
            "--toc",
            "--toc-depth=3",
            "--css",
            str(css),
            "--metadata",
            f"title={titulo}",
            "--metadata",
            f"subtitle={SUBTITULO}",
            "--metadata",
            "date=Versión 1.0.0 · noviembre de 2026",
            "--metadata",
            "author=Maxi Salas, Andrea Sofía · Treviño Ticlavilca, Juan Diego",
            "--metadata",
            "lang=es-PE",
            "--metadata",
            "toc-title=Contenido",
            "-o",
            str(salida),
        ],
        check=True,
    )
    return salida


def main() -> None:
    if not shutil.which("pandoc"):
        raise SystemExit("se requiere pandoc")
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        carpeta = Path(tmp)
        navegador = pw.chromium.launch()
        for nombre, titulo in MANUALES.items():
            html = a_html(nombre, titulo, carpeta)
            pagina = navegador.new_page()
            pagina.goto(html.as_uri())
            pagina.wait_for_load_state("networkidle")
            pie = (
                '<div style="width:100%;font-size:8px;color:#6b7280;padding:0 16mm;'
                'display:flex;justify-content:space-between;font-family:sans-serif">'
                f"<span>{titulo} · pfc-susceptibilidad</span>"
                '<span>Página <span class="pageNumber"></span> de '
                '<span class="totalPages"></span></span></div>'
            )
            pagina.pdf(
                path=DOCS / f"{nombre}.pdf",
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<span></span>",
                footer_template=pie,
                prefer_css_page_size=True,
            )
            pagina.close()
            print("pdf", nombre, flush=True)
        navegador.close()


if __name__ == "__main__":
    main()

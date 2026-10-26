"""Figura de la sección 2.9.5: ejecuciones del pipeline ci-cd (resultados/ejecuciones_ci.json)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).parent))
import estilo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
TITULOS = ["calidad-estatica", "pruebas", "analisis-sonarqube", "desplegar-staging"]
COLOR = {"exito": "#1baf7a", "falla": "#e34948", "no ejecutado": "#e4e3df"}
ETIQUETA = {"exito": "éxito", "falla": "falla", "no ejecutado": "no ejecutado"}
# Causa de cada falla, leída del log de la ejecución correspondiente
CAUSA = {
    1: "black: 32 archivos",
    2: "ruff BLE001",
    3: "pip-audit: setuptools",
    4: "host db no resuelto",
    5: "puerta de calidad",
    7: "humo: worker caído",
    8: "humo: proxy 502",
}


def figura_pipeline() -> None:
    ejecuciones = json.loads((RAIZ / "resultados" / "ejecuciones_ci.json").read_text())
    n = len(ejecuciones)
    fig, ax = plt.subplots(figsize=(9.2, 0.42 * n + 1.0))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(n + 0.5, -0.9)
    ax.axis("off")
    for j, titulo in enumerate(TITULOS):
        ax.text(3.0 + j * 1.9, -0.45, titulo, ha="center", fontsize=8, weight="bold")
    ax.text(10.6, -0.45, "total", ha="center", fontsize=8, weight="bold")
    for i, e in enumerate(ejecuciones):
        ax.text(
            0.0,
            i,
            f"#{e['ejecucion']}  {e['commit']}  {e['fecha'][-5:]}",
            va="center",
            fontsize=8,
            family="DejaVu Sans Mono",
        )
        for j, titulo in enumerate(TITULOS):
            t = e["trabajos"][titulo]
            x = 2.15 + j * 1.9
            ax.add_patch(
                FancyBboxPatch(
                    (x, i - 0.33),
                    1.7,
                    0.66,
                    boxstyle="round,pad=0.02",
                    fc=COLOR[t["estado"]],
                    ec="none",
                )
            )
            if t["estado"] == "falla":
                texto = CAUSA.get(e["ejecucion"], "falla")
            elif t["estado"] == "exito":
                texto = f"{t['segundos']:.0f} s"
            else:
                texto = "—"
            ax.text(
                x + 0.85,
                i,
                texto,
                ha="center",
                va="center",
                fontsize=7,
                color="white" if t["estado"] != "no ejecutado" else estilo.TINTA_2,
            )
        m, s = divmod(e["segundos_total"], 60)
        ax.text(
            10.6, i, f"{m} min {s:02d} s" if m else f"{s} s", ha="center", va="center", fontsize=8
        )
    for k, (estado, color) in enumerate(COLOR.items()):
        ax.add_patch(Rectangle((2.15 + k * 2.2, n - 0.05), 0.3, 0.3, fc=color, ec="none"))
        ax.text(2.55 + k * 2.2, n + 0.1, ETIQUETA[estado], va="center", fontsize=7.5)
    destino = RAIZ / "resultados" / "figuras" / "fig47_pipeline_ci.png"
    fig.savefig(destino)
    print(destino)


if __name__ == "__main__":
    figura_pipeline()

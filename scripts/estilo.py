"""Estilo común de las figuras de la tesis (paleta validada, ejes recesivos)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
GRILLA = "#e4e3df"
SERIE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SECUENCIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
DIVERGENTE = ["#184f95", "#3987e5", "#9ec5f4", "#f0efec", "#f3a5a4", "#e34948", "#a32828"]
NIVELES = {1: ("Baja", "#0ca30c"), 2: ("Media", "#fab219"), 3: ("Alta", "#ec835a"),
           4: ("Muy alta", "#d03b3b")}
CMAP_SEC = LinearSegmentedColormap.from_list("sec", SECUENCIAL)
CMAP_DIV = LinearSegmentedColormap.from_list("div", DIVERGENTE)


def aplicar():
    plt.rcParams.update({
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE, "font.family": "DejaVu Sans", "font.size": 9,
        "axes.edgecolor": TINTA_2, "axes.labelcolor": TINTA, "xtick.color": TINTA_2,
        "ytick.color": TINTA_2, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRILLA, "grid.linewidth": 0.6,
        "axes.titleweight": "bold", "axes.titlesize": 10, "legend.frameon": False,
        "lines.linewidth": 2, "figure.dpi": 150, "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


aplicar()

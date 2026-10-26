"""Figuras de la sección 2.9.6: curvas ROC en validación e importancia por ganancia."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
import estilo  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
NOMBRES = {
    "precip_mes_mm": "Precipitación mensual",
    "precip_ant90_mm": "Precipitación antecedente 90 d",
    "precip_max3d_mm": "Máximo acumulado 3 días",
    "tsm_c": "TSM Niño 1+2",
    "anom_tsm": "Anomalía TSM (t)",
    "anom_tsm_l1": "Anomalía TSM (t−1)",
    "anom_tsm_l2": "Anomalía TSM (t−2)",
    "anom_tsm_l3": "Anomalía TSM (t−3)",
    "anom_tsm_mm3": "Anomalía TSM media 3 meses",
    "pend_media_g": "Pendiente media",
    "pend_p90_g": "Pendiente percentil 90",
    "pend_max_g": "Pendiente máxima",
    "mes": "Mes del año",
}


def main(entrada: Path, salida: Path) -> None:
    d = json.loads(entrada.read_text())
    salida.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    for clave, nombre, color in (
        ("xgboost", "XGBoost (versión candidata 1)", estilo.SERIE[0]),
        ("random_forest", "Random Forest (línea base)", estilo.SERIE[1]),
    ):
        roc = d[clave]["roc"]
        ax.plot(
            roc["fpr"],
            roc["tpr"],
            color=color,
            label=f"{nombre}: AUC-ROC = {d[clave]['auc_validacion']:.3f}",
        )
    ax.plot([0, 1], [0, 1], color=estilo.TINTA_2, lw=1, ls="--", label="Clasificador aleatorio")
    ax.set(
        xlabel="Tasa de falsos positivos (FPR)",
        ylabel="Tasa de verdaderos positivos (TPR)",
        xlim=(0, 1),
        ylim=(0, 1.01),
        aspect="equal",
    )
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(salida / "fig48_roc_validacion.png")

    imp = sorted(d["xgboost"]["importancia"].items(), key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    grupos = {
        "precip": estilo.SERIE[0],
        "tsm": estilo.SERIE[1],
        "anom": estilo.SERIE[1],
        "pend": estilo.SERIE[2],
        "mes": estilo.SERIE[3],
    }
    colores = [next(c for k, c in grupos.items() if v.startswith(k)) for v, _ in imp]
    barras = ax.barh([NOMBRES[v] for v, _ in imp], [100 * g for _, g in imp], color=colores)
    ax.bar_label(barras, fmt="%.1f %%", padding=3, fontsize=7.5, color=estilo.TINTA_2)
    ax.set_xlabel("Ganancia relativa (%)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 100 * imp[-1][1] * 1.18)
    from matplotlib.patches import Patch

    ax.legend(
        handles=[
            Patch(color=estilo.SERIE[0], label="Precipitación"),
            Patch(color=estilo.SERIE[1], label="Oceánica"),
            Patch(color=estilo.SERIE[2], label="Terreno"),
            Patch(color=estilo.SERIE[3], label="Calendario"),
        ],
        loc="lower right",
        fontsize=8,
    )
    fig.savefig(salida / "fig49_importancia_gain.png")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))

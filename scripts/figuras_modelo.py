"""Figuras y cifras de la sección 2.8 (explicación del modelo) y de la 2.9.9 (evidencia técnica).

Carga la versión candidata 1 sin reentrenar. Solo lee variables de 2000-2019: la prueba
(2020-2026) sigue sellada y de ella se usan únicamente los conteos anuales ya registrados.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xgboost as xgb
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from pfc_datos.almacen import MatrizParquet
from pfc_datos.config import cargar_config, ruta_d2
from pfc_datos.modelos import RepositorioModelos
from pfc_predictiva.__main__ import VARIABLES
from pfc_predictiva.entrenamiento.particion import bloques_espaciales, pliegues_espaciales
from pfc_predictiva.evaluacion.metricas import auc_roc

sys.path.insert(0, str(Path(__file__).parent))
import estilo  # noqa: E402
from figuras_entrenamiento import NOMBRES  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
GRUPOS = {
    "precip": estilo.SERIE[0],
    "tsm": estilo.SERIE[1],
    "anom": estilo.SERIE[1],
    "pend": estilo.SERIE[2],
    "mes": estilo.SERIE[3],
}
LEYENDA_GRUPOS = [
    Patch(color=estilo.SERIE[0], label="Precipitación"),
    Patch(color=estilo.SERIE[1], label="Oceánica"),
    Patch(color=estilo.SERIE[2], label="Terreno"),
    Patch(color=estilo.SERIE[3], label="Calendario"),
]
SUBE, BAJA = estilo.DIVERGENTE[-1], estilo.DIVERGENTE[0]
FRACCIONES = (0.01, 0.05, 0.10, 0.20)


def color_variable(variable: str) -> str:
    return next(c for k, c in GRUPOS.items() if variable.startswith(k))


def sigmoide(x: np.ndarray | float) -> np.ndarray | float:
    return 1 / (1 + np.exp(-np.asarray(x)))


def caja(
    ax: plt.Axes,
    x: float,
    y: float,
    ancho: float,
    alto: float,
    titulo: str,
    cuerpo: str = "",
    color: str = estilo.SERIE[0],
    relleno: str = "#ffffff",
    tam: float = 7.5,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            ancho,
            alto,
            boxstyle="round,pad=0,rounding_size=0.08",
            facecolor=relleno,
            edgecolor=color,
            linewidth=1.3,
        )
    )
    cy = y + alto - 0.09 if cuerpo else y + alto / 2
    ax.text(
        x + ancho / 2,
        cy,
        titulo,
        ha="center",
        va="top" if cuerpo else "center",
        fontsize=tam + 0.5,
        fontweight="bold",
        color=estilo.TINTA,
    )
    if cuerpo:
        ax.text(
            x + ancho / 2,
            y + alto - 0.33,
            cuerpo,
            ha="center",
            va="top",
            fontsize=tam,
            color=estilo.TINTA_2,
            linespacing=1.25,
        )


def flecha(
    ax: plt.Axes,
    origen: tuple[float, float],
    destino: tuple[float, float],
    texto: str = "",
    curva: float = 0.0,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            origen,
            destino,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1,
            color=estilo.TINTA_2,
            connectionstyle=f"arc3,rad={curva}",
            shrinkA=0,
            shrinkB=0,
        )
    )
    if texto:
        ax.text(
            (origen[0] + destino[0]) / 2,
            (origen[1] + destino[1]) / 2 + 0.06,
            texto,
            ha="center",
            va="bottom",
            fontsize=6.8,
            color=estilo.TINTA_2,
        )


def lienzo(ancho: float, alto: float, xmax: float, ymax: float) -> tuple[plt.Figure, plt.Axes]:
    fig, ax = plt.subplots(figsize=(ancho, alto))
    ax.set(xlim=(0, xmax), ylim=(0, ymax))
    ax.axis("off")
    return fig, ax


def figura_flujo(d: dict[str, Any], salida: Path) -> None:
    """Recorrido de los datos: de la matriz de E4 a la probabilidad por celda y mes."""
    p = {f["conjunto"]: f for f in d["particion"]}
    filas = sum(f["filas"] for f in d["particion"]) / 1e6
    positivos = sum(f["positivos"] for f in d["particion"])
    x = d["xgboost"]
    fig, ax = lienzo(7.6, 5.9, 10, 7.9)

    caja(
        ax,
        2.6,
        6.95,
        4.8,
        0.9,
        "Matriz de variables (E4)",
        f"{filas:.2f} M de filas celda × mes\n13 variables; {positivos:,} positivos".replace(
            ",", " "
        ),
        estilo.SERIE[2],
    )
    entrada = (5.0, 6.95)
    conjuntos = [
        (0.1, "Entrenamiento 2000–2016", p["Entrenamiento"], estilo.SERIE[0], "#ffffff"),
        (3.5, "Validación 2017–2019", p["Validacion"], estilo.SERIE[1], "#ffffff"),
        (6.9, "Prueba 2020–2026", p["Prueba"], estilo.TINTA_2, "#f0efec"),
    ]
    for cx, titulo, f, color, relleno in conjuntos:
        cuerpo = f"{f['filas'] / 1e6:.2f} M de filas\n{f['positivos']:,} positivos".replace(
            ",", " "
        )
        caja(ax, cx, 5.35, 3.0, 0.95, titulo, cuerpo, color, relleno)
        flecha(ax, entrada, (cx + 1.5, 6.3))
    ax.text(6.9, 6.65, "división por tiempo", ha="left", fontsize=6.8, color=estilo.TINTA_2)
    ax.text(
        8.4, 5.12, "Sellada: no entra al modelo", ha="center", fontsize=7, color=estilo.TINTA_2
    )

    caja(
        ax,
        0.1,
        3.55,
        3.0,
        1.25,
        "Búsqueda (M1)",
        f"12 combinaciones × 5 pliegues\n{d['bloques']} bloques de 50 km\n"
        f"AUC-ROC = {x['auc_cv']:.3f} ± {x['auc_cv_std']:.3f}",
    )
    flecha(ax, (1.6, 5.35), (1.6, 4.8))
    caja(
        ax,
        0.1,
        1.8,
        3.0,
        1.25,
        "Entrenamiento final (M1)",
        f"{x['params']['n_estimators']} árboles, profundidad {x['params']['max_depth']}\n"
        f"todas las filas de 2000–2016\n{x['segundos_final']:.0f} s en GPU",
    )
    flecha(ax, (1.6, 3.55), (1.6, 3.05))
    caja(
        ax,
        3.5,
        2.6,
        3.0,
        1.75,
        "Evaluación (M3)",
        f"AUC-ROC = {x['auc_validacion']:.3f} (mínimo 0.80)\n"
        f"PSI anomalía TSM = {d['psi_entreno_validacion']['anom_tsm']:.2f}\n"
        f"Estado: {x['estado']}",
        estilo.SERIE[1],
    )
    flecha(ax, (3.1, 2.8), (3.5, 2.8))
    flecha(ax, (5.0, 5.35), (5.0, 4.35))
    caja(
        ax,
        6.9,
        2.6,
        3.0,
        1.75,
        "Registro (D2)",
        f"xgboost_v1.ubj ({x['bytes'] / 1024:.0f} KB)\nSHA-256 {x['sha256'][:10]}…\n"
        "tarjeta JSON con métricas\ne importancias",
        estilo.SERIE[2],
    )
    flecha(ax, (6.5, 3.45), (6.9, 3.45))
    caja(
        ax,
        3.5,
        0.35,
        6.4,
        1.45,
        "Inferencia por lotes (M2)",
        "Verifica el SHA-256 y calcula el puntaje de cada\n"
        "celda y mes, un año a la vez. Los niveles Baja a Muy alta\n"
        "se calibran con el Especialista en el hito 2.",
        estilo.SERIE[3],
    )
    flecha(ax, (8.4, 2.6), (8.4, 1.8))
    fig.savefig(salida / "fig52_flujo_modelo.png")
    plt.close(fig)


def figura_modulos(salida: Path) -> None:
    """Módulos de pfc_predictiva y sus llamadas principales en la versión v0.1.0."""
    fig, ax = lienzo(7.6, 4.9, 10, 6.5)
    filas = {"arriba": 5.0, "medio": 2.65, "abajo": 0.3}
    alto = 1.4
    caja(
        ax,
        0.1,
        filas["arriba"],
        3.05,
        alto,
        "pfc_datos.almacen (D2)",
        "MatrizParquet.leer():\nlee la matriz por años",
        estilo.SERIE[2],
    )
    caja(
        ax,
        3.45,
        filas["arriba"],
        3.05,
        alto,
        "__main__.py",
        "main(): ejecuta todo y escribe\nentrenamiento_v1.json",
        estilo.TINTA_2,
    )
    caja(
        ax,
        6.85,
        filas["arriba"],
        3.05,
        alto,
        "inferencia.py (M2)",
        "inferir(), clasificar()\nfuera de main()",
        estilo.SERIE[3],
    )
    caja(
        ax,
        0.1,
        filas["medio"],
        3.05,
        alto,
        "busqueda.py (M1)",
        "buscar(), validacion_cruzada()\nvalidacion_cruzada_rf()",
    )
    caja(
        ax,
        3.45,
        filas["medio"],
        3.05,
        alto,
        "entrenador.py (M1)",
        "entrenar_version()\nUMBRAL_AUC_MINIMO = 0.80",
    )
    caja(
        ax,
        6.85,
        filas["medio"],
        3.05,
        alto,
        "pfc_datos.modelos (D2)",
        "RepositorioModelos: guardar(),\ncargar(), huella SHA-256",
        estilo.SERIE[2],
    )
    caja(
        ax,
        0.1,
        filas["abajo"],
        3.05,
        alto,
        "particion.py (M1)",
        "bloques_espaciales()\npliegues_espaciales()\nsubmuestrear_negativos()",
    )
    caja(
        ax,
        3.45,
        filas["abajo"],
        3.05,
        alto,
        "clasificadores.py (M1)",
        "crear_xgboost()\ncrear_random_forest()",
    )
    caja(
        ax,
        6.85,
        filas["abajo"],
        3.05,
        alto,
        "metricas.py (M3)",
        "auc_roc(), curva_roc(), psi()\ndeciles_referencia()\nmetricas_umbral()",
        estilo.SERIE[1],
    )
    for origen, destino in (
        ((3.45, 5.7), (3.15, 5.7)),
        ((4.0, 5.0), (2.0, 4.05)),
        ((5.0, 5.0), (5.0, 4.05)),
        ((6.0, 5.0), (7.6, 4.05)),
        ((8.4, 5.0), (8.4, 4.05)),
        ((6.5, 3.35), (6.85, 3.35)),
        ((1.6, 2.65), (1.6, 1.7)),
        ((2.4, 2.65), (4.2, 1.7)),
        ((2.9, 2.65), (7.3, 1.7)),
        ((5.0, 2.65), (5.0, 1.7)),
        ((6.0, 2.65), (7.8, 1.7)),
    ):
        flecha(ax, origen, destino)
    fig.savefig(salida / "fig53_modulos_modelo.png")
    plt.close(fig)


def figura_particion(
    d: dict[str, Any],
    procesamiento: dict[str, Any],
    d2: Path,
    config: dict[str, Any],
    salida: Path,
) -> dict[str, Any]:
    """Positivos por año (conteos registrados) y bloques espaciales asignados a cada pliegue."""
    celdas = pd.read_parquet(d2 / "celdas.parquet")
    bloque = bloques_espaciales(celdas, config["modelo"]["bloque_espacial_km"])
    ids = MatrizParquet(d2).leer(
        range(2000, config["particion"]["fin_entrenamiento"] + 1), ["id_celda"]
    )
    grupos = bloque.loc[ids["id_celda"]].to_numpy()
    pliegue_por_bloque: dict[int, int] = {}
    for i, (_, i_va) in enumerate(pliegues_espaciales(grupos, config["modelo"]["pliegues"])):
        pliegue_por_bloque.update(dict.fromkeys(np.unique(grupos[i_va]).tolist(), i))
    if len(pliegue_por_bloque) != d["bloques"]:
        raise ValueError("Los bloques no coinciden con entrenamiento_v1.json")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.8, 4.3), width_ratios=[1.45, 1])
    anios = np.array(sorted(int(a) for a in procesamiento["matriz"]))
    positivos = np.array([procesamiento["matriz"][str(a)][1] for a in anios])
    colores = [
        estilo.SERIE[0] if a <= 2016 else estilo.SERIE[1] if a <= 2019 else "#a9a8a3"
        for a in anios
    ]
    a1.bar(anios, positivos, color=colores, width=0.8)
    a1.set(xlabel="Año", ylabel="Celdas-mes con deslizamiento")
    a1.grid(axis="x", visible=False)
    a1.legend(
        handles=[
            Patch(color=estilo.SERIE[0], label="Entrenamiento (2000–2016)"),
            Patch(color=estilo.SERIE[1], label="Validación (2017–2019)"),
            Patch(color="#a9a8a3", label="Prueba sellada (2020–2026): solo conteo"),
        ],
        loc="upper left",
        fontsize=7.5,
    )
    a1.set_title("Reparto en el tiempo", loc="left")

    pliegues = bloque.map(pliegue_por_bloque).to_numpy()
    for i in range(config["modelo"]["pliegues"]):
        marca = pliegues == i
        a2.scatter(
            celdas["x"].to_numpy()[marca] / 1000,
            celdas["y"].to_numpy()[marca] / 1000,
            s=0.15,
            color=estilo.SERIE[i],
            rasterized=True,
            label=f"Pliegue {i + 1}",
        )
    a2.set_aspect("equal")
    a2.set(xlabel="Este UTM (km)", ylabel="Norte UTM (km)")
    a2.grid(visible=False)
    a2.legend(markerscale=14, fontsize=7, loc="lower left")
    a2.set_title(f"Reparto en el espacio ({d['bloques']} bloques)", loc="left")
    fig.tight_layout()
    fig.savefig(salida / "fig54_particion_bloques.png")
    plt.close(fig)
    return {"celdas_por_pliegue": np.bincount(pliegues).tolist()}


def dibujar_arbol(ax: plt.Axes, arbol: pd.DataFrame) -> None:
    """Dibuja los tres primeros niveles del árbol; lo más profundo se resume en una rama."""
    nodos = arbol.set_index("ID")
    ax.set(xlim=(0, 10), ylim=(0, 4.2))
    ax.axis("off")

    def nodo(ident: str, x: float, y: float, dx: float, nivel: int) -> None:
        fila = nodos.loc[ident]
        hoja = fila["Feature"] == "Leaf"
        if hoja or nivel == 3:
            texto = f"hoja\n{fila['Gain']:+.2f}" if hoja else "más\ndivisiones"
            ax.text(
                x,
                y,
                texto,
                ha="center",
                va="center",
                fontsize=6.5,
                color=estilo.TINTA_2,
                bbox={"boxstyle": "round", "fc": "#f0efec", "ec": "none"},
            )
            return
        for hijo, signo, etiqueta in ((fila["Yes"], -1, "sí"), (fila["No"], 1, "no")):
            xh, yh = x + signo * dx, y - 1.25
            ax.plot([x, xh], [y, yh], color=estilo.TINTA_2, lw=0.8, zorder=1)
            ax.text(
                (x + xh) / 2 + signo * 0.12,
                (y + yh) / 2 + 0.08,
                etiqueta,
                fontsize=6.3,
                color=estilo.TINTA_2,
                ha="center",
            )
            nodo(hijo, xh, yh, dx / 2, nivel + 1)
        ax.text(
            x,
            y,
            f"{NOMBRES[fila['Feature']]}\n< {fila['Split']:.1f}",
            ha="center",
            va="center",
            fontsize=6.3,
            color=estilo.TINTA,
            zorder=2,
            bbox={"boxstyle": "round", "fc": "#ffffff", "ec": color_variable(fila["Feature"])},
        )

    nodo(arbol.iloc[0]["ID"], 5, 3.85, 2.5, 0)


def figura_arbol(
    booster: xgb.Booster,
    positivo: pd.DataFrame,
    negativo: pd.DataFrame,
    salida: Path,
) -> dict[str, Any]:
    """Un árbol real y la suma de los 23 árboles sobre dos celdas-mes reales de validación."""
    arboles = booster.trees_to_dataframe()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.6, 7.0), height_ratios=[1.25, 1])
    dibujar_arbol(a1, arboles[arboles["Tree"] == 0])
    a1.set_title("Primer árbol del modelo: primeros niveles", loc="left")
    a1.legend(handles=LEYENDA_GRUPOS[:2], fontsize=7, loc="upper right")

    total = booster.num_boosted_rounds()
    rondas = np.arange(1, total + 1)
    trayectorias = {}
    for nombre, fila, color in (
        ("Celda-mes con deslizamiento", positivo, estilo.SERIE[1]),
        ("Celda-mes sin deslizamiento", negativo, estilo.SERIE[0]),
    ):
        matriz = xgb.DMatrix(fila[VARIABLES])
        margen = [
            float(booster.predict(matriz, output_margin=True, iteration_range=(0, k))[0])
            for k in rondas
        ]
        a2.plot(rondas, margen, color=color, marker="o", markersize=3, label=nombre)
        a2.annotate(
            f"puntaje final {sigmoide(margen[-1]):.3f}",
            (rondas[-1], margen[-1]),
            xytext=(-4, 7),
            textcoords="offset points",
            ha="right",
            fontsize=7.5,
            color=estilo.TINTA,
        )
        trayectorias[nombre] = margen
    a2.axhline(0, color=estilo.TINTA_2, lw=0.8, ls="--")
    a2.text(1, -0.2, "log-odds 0 = puntaje 0.5", fontsize=7, color=estilo.TINTA_2)
    a2.set(xlabel="Árboles sumados", ylabel="Suma acumulada (log-odds)", xlim=(0.5, total + 0.5))
    a2.set_title("Cada árbol suma o resta: así se llega al puntaje", loc="left")
    a2.legend(fontsize=7.5, loc="center right")
    fig.tight_layout()
    fig.savefig(salida / "fig55_arbol_y_suma.png")
    plt.close(fig)
    return trayectorias


def figura_contribuciones(
    variables: list[str], contribuciones: np.ndarray, fila: int, salida: Path
) -> dict[str, Any]:
    """TreeSHAP: peso medio de cada variable en validación y desglose de una celda-mes."""
    media = np.abs(contribuciones[:, :-1]).mean(axis=0)
    orden = np.argsort(media)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.0, 4.4), sharey=False)
    barras = a1.barh(
        [NOMBRES[variables[i]] for i in orden],
        media[orden],
        color=[color_variable(variables[i]) for i in orden],
    )
    a1.bar_label(barras, fmt="%.2f", padding=2, fontsize=7, color=estilo.TINTA_2)
    a1.grid(axis="y", visible=False)
    a1.set_xlabel("Contribución absoluta media (log-odds)")
    a1.set_title("Peso medio en 2017–2019", loc="left")
    a1.legend(handles=LEYENDA_GRUPOS, fontsize=7, loc="lower right")
    a1.tick_params(axis="y", labelsize=7)

    base = float(contribuciones[fila, -1])
    aportes = contribuciones[fila, :-1]
    orden_local = np.argsort(np.abs(aportes))
    acumulado = base + np.concatenate(([0.0], np.cumsum(aportes[orden_local])))
    for pos, i in enumerate(orden_local):
        a2.barh(
            pos,
            aportes[i],
            left=acumulado[pos],
            color=SUBE if aportes[i] > 0 else BAJA,
            height=0.7,
        )
    a2.set_yticks(
        range(len(orden_local)), [NOMBRES[variables[i]] for i in orden_local], fontsize=7
    )
    a2.axvline(base, color=estilo.TINTA_2, lw=0.8, ls="--")
    a2.set_axisbelow(True)
    a1.set_axisbelow(True)
    final = float(contribuciones[fila].sum())
    a2.annotate(
        f"base {base:.2f}",
        (base, 3.5),
        xytext=(5, 0),
        textcoords="offset points",
        fontsize=7,
        color=estilo.TINTA_2,
    )
    a2.annotate(
        f"final {final:.2f}\npuntaje {sigmoide(final):.3f}",
        (final, len(orden_local) - 3.5),
        ha="right",
        fontsize=7.5,
        color=estilo.TINTA,
    )
    a2.grid(axis="y", visible=False)
    a2.set_xlabel("Log-odds acumulados")
    a2.set_title("Desglose de una celda-mes", loc="left")
    a2.legend(
        handles=[
            Patch(color=SUBE, label="Sube el puntaje"),
            Patch(color=BAJA, label="Baja el puntaje"),
        ],
        fontsize=7,
        loc="lower right",
    )
    fig.tight_layout()
    fig.savefig(salida / "fig56_contribuciones.png")
    plt.close(fig)
    return {
        "media_abs": {variables[i]: float(media[i]) for i in orden[::-1]},
        "base_log_odds": base,
        "suma_log_odds": float(contribuciones[fila].sum()),
        "aportes_ejemplo": {variables[i]: float(aportes[i]) for i in orden_local[::-1]},
    }


def curva_captura(y: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fracción revisada y de positivos capturados; las filas empatadas avanzan juntas."""
    valores, inverso = np.unique(-p, return_inverse=True)
    total = np.bincount(inverso, minlength=len(valores))
    aciertos = np.bincount(inverso, weights=y, minlength=len(valores))
    return (
        np.concatenate(([0.0], np.cumsum(total) / len(y))),
        np.concatenate(([0.0], np.cumsum(aciertos) / y.sum())),
    )


def figura_captura(y: np.ndarray, p: np.ndarray, salida: Path) -> dict[str, float]:
    revisada, capturada = curva_captura(y, p)
    captura = {f: float(np.interp(f, revisada, capturada)) for f in FRACCIONES}
    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    ax.plot(revisada * 100, capturada * 100, color=estilo.SERIE[0], label="XGBoost, versión 1")
    ax.plot([0, 100], [0, 100], color=estilo.TINTA_2, lw=1, ls="--", label="Revisión al azar")
    for f, c in captura.items():
        ax.scatter(
            f * 100, c * 100, s=26, color=estilo.SERIE[0], edgecolor=estilo.SUPERFICIE, zorder=3
        )
        ax.annotate(
            f"{f * 100:.0f} % → {c * 100:.1f} %",
            (f * 100, c * 100),
            xytext=(7, -9),
            textcoords="offset points",
            fontsize=7.5,
            color=estilo.TINTA,
            bbox={"fc": estilo.SUPERFICIE, "ec": "none", "pad": 1},
            zorder=4,
        )
    ax.set(
        xlabel="Celdas-mes revisadas, de mayor a menor puntaje (%)",
        ylabel="Deslizamientos capturados (%)",
        xlim=(0, 100),
        ylim=(0, 101),
    )
    ax.legend(loc="lower right", fontsize=8)
    fig.savefig(salida / "fig57_captura_validacion.png")
    plt.close(fig)
    return {f"{f:.2f}": c for f, c in captura.items()}


def error_hanley_mcneil(auc: float, positivos: int, negativos: int) -> float:
    """Error estándar del AUC según Hanley y McNeil (1982)."""
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    varianza = (
        auc * (1 - auc) + (positivos - 1) * (q1 - auc**2) + (negativos - 1) * (q2 - auc**2)
    ) / (positivos * negativos)
    return math.sqrt(varianza)


def intervalo(auc: float, positivos: int, negativos: int) -> dict[str, float]:
    ee = error_hanley_mcneil(auc, positivos, negativos)
    return {"auc": auc, "ee": ee, "ic95": [auc - 1.96 * ee, auc + 1.96 * ee]}


def main(salida: Path) -> None:
    config = cargar_config()
    d2 = ruta_d2()
    salida.mkdir(parents=True, exist_ok=True)
    d = json.loads((RAIZ / "resultados" / "entrenamiento_v1.json").read_text())
    procesamiento = json.loads((RAIZ / "resultados" / "procesamiento_e1_e4.json").read_text())

    figura_flujo(d, salida)
    figura_modulos(salida)
    espacial = figura_particion(d, procesamiento, d2, config, salida)

    modelo, version = RepositorioModelos(d2).cargar("XGBOOST", "1")  # verifica el SHA-256
    booster = modelo.get_booster()
    booster.set_param({"device": "cpu"})

    desde, hasta = config["particion"]["validacion"]
    columnas = ["id_celda", "periodo", "objetivo", *VARIABLES]
    valid = MatrizParquet(d2).leer(range(desde, hasta + 1), columnas)
    matriz = xgb.DMatrix(valid[VARIABLES])
    prob = booster.predict(matriz)
    y = valid["objetivo"].to_numpy()

    auc = auc_roc(y, prob)
    if not math.isclose(auc, d["xgboost"]["auc_validacion"], abs_tol=1e-6):
        raise ValueError(f"AUC {auc} distinto del registrado {d['xgboost']['auc_validacion']}")

    # Ejemplos reales: el positivo de 2017 con mayor puntaje y un negativo del mismo mes
    # con el puntaje mediano de ese mes.
    anio = valid["periodo"].dt.year.to_numpy()
    candidatos = np.flatnonzero((y == 1) & (anio == 2017))
    i_pos = int(candidatos[np.argmax(prob[candidatos])])
    mismo_mes = np.flatnonzero(
        (valid["periodo"].to_numpy() == valid["periodo"].to_numpy()[i_pos]) & (y == 0)
    )
    i_neg = int(mismo_mes[np.argsort(prob[mismo_mes])[len(mismo_mes) // 2]])

    contribuciones = booster.predict(matriz, pred_contribs=True)
    trayectorias = figura_arbol(booster, valid.iloc[[i_pos]], valid.iloc[[i_neg]], salida)
    explicacion = figura_contribuciones(VARIABLES, contribuciones, i_pos, salida)
    captura = figura_captura(y, prob, salida)

    n_pos, n_neg = int(y.sum()), int((y == 0).sum())
    por_anio = {
        str(a): {
            "auc": auc_roc(y[anio == a], prob[anio == a]),
            "positivos": int(y[anio == a].sum()),
        }
        for a in range(desde, hasta + 1)
    }
    ejemplo = {
        "positivo": {
            **{k: valid.iloc[i_pos][k] for k in ("id_celda", "periodo", *VARIABLES)},
            "puntaje": float(prob[i_pos]),
        },
        "negativo": {
            **{k: valid.iloc[i_neg][k] for k in ("id_celda", "periodo", *VARIABLES)},
            "puntaje": float(prob[i_neg]),
        },
    }
    corte_1 = np.quantile(prob, 0.99)
    resultado = {
        "version": {"sha256": version.sha256, "estado": str(version.estado)},
        "validacion": {"filas": len(y), "positivos": n_pos, "prevalencia": float(y.mean())},
        "auc_xgboost": intervalo(auc, n_pos, n_neg),
        "auc_random_forest": intervalo(d["random_forest"]["auc_validacion"], n_pos, n_neg),
        "auc_por_anio": por_anio,
        "captura": captura,
        "puntaje": {
            "medio": float(prob.mean()),
            "mediana": float(np.median(prob)),
            "p99": float(corte_1),
            "valores_distintos": int(np.unique(prob).size),
            "medio_positivos": float(prob[y == 1].mean()),
            "medio_negativos": float(prob[y == 0].mean()),
        },
        "espacial": espacial,
        "ejemplo": ejemplo,
        "explicacion": explicacion,
        "trayectorias_log_odds": trayectorias,
        "arboles": booster.num_boosted_rounds(),
    }
    (RAIZ / "resultados" / "explicacion_modelo.json").write_text(
        json.dumps(resultado, indent=2, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in resultado.items() if k != "trayectorias_log_odds"},
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "resultados" / "figuras")

"""M3. Métricas de evaluación por versión y deriva de datos (PSI)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

N_DECILES = 10
EPSILON = 1e-6


def auc_roc(y: np.ndarray, probabilidad: np.ndarray) -> float:
    """AUC-ROC sobre probabilidades: no depende de ningún umbral de clasificación."""
    return float(roc_auc_score(y, probabilidad))


def curva_roc(
    y: np.ndarray, probabilidad: np.ndarray, puntos: int = 400
) -> dict[str, list[float]]:
    """Curva ROC interpolada en una malla fija de tasas de falsos positivos, para graficar."""
    fpr, tpr, _ = roc_curve(y, probabilidad)
    malla = np.linspace(0, 1, puntos)
    return {"fpr": malla.tolist(), "tpr": np.interp(malla, fpr, tpr).tolist()}


def metricas_umbral(y: np.ndarray, probabilidad: np.ndarray, umbral: float) -> dict[str, float]:
    """Exactitud, sensibilidad, precisión y F1 al clasificar con un umbral dado."""
    prediccion = (probabilidad >= umbral).astype(int)
    return {
        "accuracy": float(accuracy_score(y, prediccion)),
        "recall": float(recall_score(y, prediccion, zero_division=0)),
        "precision": float(precision_score(y, prediccion, zero_division=0)),
        "f1": float(f1_score(y, prediccion, zero_division=0)),
    }


def metricas_balanceadas(
    y: np.ndarray,
    probabilidad: np.ndarray,
    umbral: float,
    grupos: np.ndarray,
    repeticiones: int,
    semilla: int,
) -> dict[str, dict[str, float]]:
    """Métricas de umbral en muestras caso-control 1:1, con la media e IC 95 % por percentiles.

    Cada repetición conserva todos los positivos y sortea, sin reemplazo y dentro de cada grupo
    (por ejemplo, el año), tantos negativos como positivos tiene ese grupo.
    """
    rng = np.random.default_rng(semilla)
    positivos = np.flatnonzero(y == 1)
    negativos = {g: np.flatnonzero((y == 0) & (grupos == g)) for g in np.unique(grupos[positivos])}
    cuota = {g: int((grupos[positivos] == g).sum()) for g in negativos}
    valores: dict[str, list[float]] = {}
    for _ in range(repeticiones):
        sorteo = [rng.choice(negativos[g], cuota[g], replace=False) for g in negativos]
        indices = np.concatenate([positivos, *sorteo])
        for nombre, valor in metricas_umbral(y[indices], probabilidad[indices], umbral).items():
            valores.setdefault(nombre, []).append(valor)
    return {
        nombre: {
            "media": float(np.mean(v)),
            "ic95_inf": float(np.percentile(v, 2.5)),
            "ic95_sup": float(np.percentile(v, 97.5)),
        }
        for nombre, v in valores.items()
    }


def deciles_referencia(columna: pd.Series) -> list[float]:
    """Cortes de deciles de la distribución de entrenamiento (referencia del PSI)."""
    cortes = np.unique(np.quantile(columna.dropna(), np.linspace(0, 1, N_DECILES + 1)[1:-1]))
    return cortes.tolist()


def psi(referencia: pd.Series, actual: pd.Series, cortes: list[float]) -> float:
    """Índice de estabilidad poblacional: sum((a - e) * ln(a / e)) por deciles."""
    bordes = [-np.inf, *cortes, np.inf]
    e = np.histogram(referencia.dropna(), bordes)[0] / max(referencia.notna().sum(), 1)
    a = np.histogram(actual.dropna(), bordes)[0] / max(actual.notna().sum(), 1)
    e, a = np.clip(e, EPSILON, None), np.clip(a, EPSILON, None)
    return float(np.sum((a - e) * np.log(a / e)))

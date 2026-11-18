"""M1. Protocolo Clasificador y fábricas de XGBoost y Random Forest (línea base)."""

from __future__ import annotations

import os
from typing import Any, Protocol

import numpy as np


class Clasificador(Protocol):
    """Interfaz común de XGBoost y Random Forest que usan el entrenamiento y la inferencia."""

    def fit(self, X: Any, y: Any, **kwargs: Any) -> Any:
        """Ajusta el clasificador a las variables X y al objetivo y."""

    def predict_proba(self, X: Any) -> np.ndarray:
        """Probabilidades por clase; la columna 1 es la de deslizamiento."""


def crear_xgboost(params: dict[str, Any], semilla: int, **extra: Any) -> Clasificador:
    """XGBoost con los hiperparámetros dados, histogramas y la semilla del proyecto.

    El dispositivo se toma de PFC_DISPOSITIVO_XGB: cuda en la estación y cpu en CI y en el VPS.
    """
    import xgboost as xgb

    return xgb.XGBClassifier(
        **params,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        device=os.environ.get("PFC_DISPOSITIVO_XGB", "cuda"),  # cpu en CI sin GPU
        eval_metric="auc",
        random_state=semilla,
        **extra,
    )


def crear_random_forest(semilla: int) -> Clasificador:
    """Random Forest de la línea base, con pesos de clase balanceados por muestra."""
    from sklearn.ensemble import RandomForestClassifier

    return RandomForestClassifier(
        n_estimators=500,
        max_depth=14,
        min_samples_leaf=20,
        max_features="sqrt",
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=semilla,
    )

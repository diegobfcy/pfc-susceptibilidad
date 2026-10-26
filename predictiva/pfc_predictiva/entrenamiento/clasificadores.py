"""M1. Protocolo Clasificador y fábricas de XGBoost y Random Forest (línea base)."""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np


class Clasificador(Protocol):
    def fit(self, X: Any, y: Any, **kwargs: Any) -> Any: ...

    def predict_proba(self, X: Any) -> np.ndarray: ...


def crear_xgboost(params: dict[str, Any], semilla: int, **extra: Any) -> Clasificador:
    import xgboost as xgb

    return xgb.XGBClassifier(
        **params,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        device="cuda",
        eval_metric="auc",
        random_state=semilla,
        **extra,
    )


def crear_random_forest(semilla: int) -> Clasificador:
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

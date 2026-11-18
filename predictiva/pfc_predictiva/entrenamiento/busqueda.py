"""M1. Búsqueda de hiperparámetros con validación cruzada por bloques espaciales."""

from __future__ import annotations

import itertools
import time
from collections.abc import Iterator
from typing import Any

import numpy as np
import pandas as pd

from pfc_predictiva.entrenamiento.clasificadores import crear_random_forest, crear_xgboost
from pfc_predictiva.entrenamiento.particion import pliegues_espaciales, submuestrear_negativos
from pfc_predictiva.evaluacion.metricas import auc_roc

MAX_ARBOLES = 2000
PARADA_TEMPRANA = 50


def combinaciones(grilla: dict[str, list[Any]]) -> Iterator[dict[str, Any]]:
    """Recorre todas las combinaciones de la grilla de hiperparámetros."""
    claves = list(grilla)
    for valores in itertools.product(*(grilla[c] for c in claves)):
        yield dict(zip(claves, valores, strict=True))


def _pliegue(
    entreno: pd.DataFrame, i_tr: np.ndarray, i_va: np.ndarray, fraccion: float, semilla: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    parte = submuestrear_negativos(entreno.iloc[i_tr], fraccion, semilla)
    return parte, entreno.iloc[i_va]


def validacion_cruzada(
    entreno: pd.DataFrame,
    variables: list[str],
    params: dict[str, Any],
    pliegues: list[tuple[np.ndarray, np.ndarray]],
    fraccion: float,
    semilla: int,
) -> tuple[list[float], list[int]]:
    """AUC-ROC y mejor iteración de XGBoost en cada pliegue espacial."""
    aucs, iteraciones = [], []
    for i_tr, i_va in pliegues:
        parte, valid = _pliegue(entreno, i_tr, i_va, fraccion, semilla)
        y = parte["objetivo"].to_numpy()
        modelo = crear_xgboost(
            params,
            semilla,
            n_estimators=MAX_ARBOLES,
            early_stopping_rounds=PARADA_TEMPRANA,
            scale_pos_weight=float((y == 0).sum() / y.sum()),
        )
        modelo.fit(
            parte[variables], y, eval_set=[(valid[variables], valid["objetivo"])], verbose=False
        )
        aucs.append(
            auc_roc(valid["objetivo"].to_numpy(), modelo.predict_proba(valid[variables])[:, 1])
        )
        iteraciones.append(int(modelo.best_iteration) + 1)
    return aucs, iteraciones


def buscar(
    entreno: pd.DataFrame,
    variables: list[str],
    bloque: np.ndarray,
    config: dict[str, Any],
    semilla: int,
) -> dict[str, Any]:
    """Grilla completa; elige por AUC-ROC medio y fija n_estimators con la mediana de pliegues."""
    m = config["modelo"]
    pliegues = pliegues_espaciales(bloque, m["pliegues"])
    tabla, t0 = [], time.perf_counter()
    for params in combinaciones(m["grilla"]):
        aucs, iteraciones = validacion_cruzada(
            entreno, variables, params, pliegues, m["submuestreo_negativos_busqueda"], semilla
        )
        tabla.append(
            {
                **params,
                "auc_media": float(np.mean(aucs)),
                "auc_std": float(np.std(aucs)),
                "aucs": aucs,
                "iteraciones": iteraciones,
            }
        )
    mejor = max(tabla, key=lambda f: f["auc_media"])
    params = {k: mejor[k] for k in m["grilla"]}
    params["n_estimators"] = int(np.median(mejor["iteraciones"]))
    return {
        "params": params,
        "auc_cv": mejor["auc_media"],
        "auc_cv_std": mejor["auc_std"],
        "tabla": tabla,
        "segundos": round(time.perf_counter() - t0, 1),
        "pliegues": pliegues,
    }


def validacion_cruzada_rf(
    entreno: pd.DataFrame,
    variables: list[str],
    pliegues: list[tuple[np.ndarray, np.ndarray]],
    fraccion: float,
    semilla: int,
) -> list[float]:
    """AUC-ROC de Random Forest en cada pliegue espacial, con el mismo submuestreo que XGBoost."""
    aucs = []
    for i_tr, i_va in pliegues:
        parte, valid = _pliegue(entreno, i_tr, i_va, fraccion, semilla)
        modelo = crear_random_forest(semilla).fit(parte[variables], parte["objetivo"])
        aucs.append(
            auc_roc(valid["objetivo"].to_numpy(), modelo.predict_proba(valid[variables])[:, 1])
        )
    return aucs

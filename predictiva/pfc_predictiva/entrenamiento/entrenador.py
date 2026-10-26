"""M1. Entrenamiento de una versión del modelo con partición temporal y criterio de aceptación."""

from __future__ import annotations

from typing import Any, Final

import pandas as pd
from pfc_datos.modelos import EstadoVersion, RepositorioModelos, VersionModelo

from pfc_predictiva.entrenamiento.clasificadores import crear_xgboost
from pfc_predictiva.evaluacion.metricas import auc_roc, deciles_referencia

UMBRAL_AUC_MINIMO: Final = 0.80  # criterio de aceptación (RNF-02)
SEMILLA: Final = 42
ANIO_FIN_ENTRENO: Final = 2016
ANIOS_VALIDACION: Final = (2017, 2019)
VARIABLES_DERIVA: Final = ["precip_max3d_mm", "precip_ant90_mm", "anom_tsm"]


def entrenar_version(
    matriz: pd.DataFrame,
    variables: list[str],
    params: dict[str, Any],
    modelos: RepositorioModelos,
    version: str = "1",
) -> VersionModelo:
    """M1: entrena XGBoost con partición temporal y registra la versión.

    matriz: particiones Parquet 2000-2019 leídas desde D2. params: hiperparámetros
    de la validación cruzada espacial, incluido n_estimators (mediana de pliegues).
    """
    anio = matriz["periodo"].dt.year
    entreno = matriz[anio <= ANIO_FIN_ENTRENO]
    valid = matriz[anio.between(*ANIOS_VALIDACION)]
    # La prueba (2020-2026) queda sellada: sus particiones Parquet no se leen.

    y = entreno["objetivo"]
    n_pos = int(y.sum())
    clasificador = crear_xgboost(
        params,
        SEMILLA,
        scale_pos_weight=(len(y) - n_pos) / n_pos,  # desbalance sin datos sintéticos
    )
    clasificador.fit(entreno[variables], y)

    prob = clasificador.predict_proba(valid[variables])[:, 1]
    auc = auc_roc(valid["objetivo"].to_numpy(), prob)  # independiente del umbral
    estado = EstadoVersion.CANDIDATA if auc >= UMBRAL_AUC_MINIMO else EstadoVersion.RECHAZADA

    return modelos.guardar(  # D2 con SHA-256; métricas e importancias en la tarjeta
        clasificador,
        "XGBOOST",
        version,
        estado,
        metricas={"auc_validacion": auc},
        importancia=clasificador.get_booster().get_score(importance_type="gain"),
        referencia_psi={v: deciles_referencia(entreno[v]) for v in VARIABLES_DERIVA},
        hiperparametros={**params, "scale_pos_weight": (len(y) - n_pos) / n_pos},
    )

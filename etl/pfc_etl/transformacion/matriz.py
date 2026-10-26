"""E4. Matriz de variables celda x mes (Tabla 78), escrita en Parquet particionado por año."""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd
from pfc_datos.protocolos import EscritorMatriz

VARIABLES_MODELO: Final = [
    "tsm_c",
    "anom_tsm",
    "anom_tsm_l1",
    "anom_tsm_l2",
    "anom_tsm_l3",
    "anom_tsm_mm3",
    "precip_mes_mm",
    "precip_max3d_mm",
    "precip_ant90_mm",
    "pend_media_g",
    "pend_p90_g",
    "pend_max_g",
    "mes",
]


def construir_anio(
    anio: int,
    celdas: pd.DataFrame,
    oceanicas: pd.DataFrame,
    precipitacion: pd.DataFrame,
    terreno: pd.DataFrame,
    positivos: pd.DataFrame,
) -> pd.DataFrame:
    """Une los cuatro grupos de variables por la clave (id_celda, periodo) para un año."""
    meses = oceanicas[oceanicas["periodo"].dt.year == anio]
    base = celdas[["id_celda", "id_pixel", "ubigeo_prov"]].merge(terreno, on="id_celda")
    filas = base.merge(meses, how="cross")
    filas = filas.merge(precipitacion, on=["id_pixel", "periodo"], how="inner")
    marcados = positivos.assign(objetivo=np.int8(1))
    filas = filas.merge(marcados, on=["id_celda", "periodo"], how="left")
    filas["objetivo"] = filas["objetivo"].fillna(0).astype("int8")
    filas["mes"] = filas["periodo"].dt.month.astype("int8")
    filas = filas.dropna(subset=VARIABLES_MODELO)
    columnas = ["id_celda", "periodo", *VARIABLES_MODELO, "ubigeo_prov", "objetivo"]
    return filas[columnas].astype({"id_celda": "int32"})


def construir_matriz(
    anios: range,
    escritor: EscritorMatriz,
    **grupos: pd.DataFrame,
) -> dict[int, tuple[int, int]]:
    """Escribe una partición por año y devuelve {anio: (filas, positivos)}."""
    resumen = {}
    for anio in anios:
        tabla = construir_anio(anio, **grupos)
        if tabla.empty:
            continue
        escritor.escribir_anio(anio, tabla)
        resumen[anio] = (len(tabla), int(tabla["objetivo"].sum()))
    return resumen

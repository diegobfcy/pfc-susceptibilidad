"""E4. Variable objetivo: 1 si el inventario registra al menos un evento con precisión de
fecha DIA o MES en la celda y el mes; 0 en caso contrario."""

from __future__ import annotations

import pandas as pd

PRECISIONES_CON_ETIQUETA = frozenset({"DIA", "MES"})


def celdas_mes_positivas(eventos: pd.DataFrame) -> pd.DataFrame:
    """eventos: id_celda, fecha, precision_fecha. Devuelve id_celda, periodo únicos."""
    utiles = eventos[
        eventos["precision_fecha"].isin(PRECISIONES_CON_ETIQUETA) & eventos["id_celda"].notna()
    ]
    positivos = pd.DataFrame(
        {
            "id_celda": utiles["id_celda"].astype("int32"),
            "periodo": pd.to_datetime(utiles["fecha"]).dt.to_period("M").dt.to_timestamp(),
        }
    )
    return positivos.drop_duplicates().reset_index(drop=True)

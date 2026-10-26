"""M1. Partición temporal y bloques espaciales de validación cruzada."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold


def bloques_espaciales(celdas: pd.DataFrame, tamano_km: float) -> pd.Series:
    """Bloque de tamano_km x tamano_km al que pertenece cada celda (índice id_celda)."""
    lado = tamano_km * 1000
    bx = (celdas["x"] // lado).astype(int)
    by = (celdas["y"] // lado).astype(int)
    return pd.Series((bx * 1000 + by).to_numpy(), index=celdas["id_celda"].to_numpy())


def pliegues_espaciales(
    bloque: np.ndarray, n_pliegues: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Pliegues con bloques completos: celdas de validación separadas geográficamente."""
    return list(GroupKFold(n_splits=n_pliegues).split(np.zeros(len(bloque)), groups=bloque))


def submuestrear_negativos(tabla: pd.DataFrame, fraccion: float, semilla: int) -> pd.DataFrame:
    """Todos los positivos y una fracción de negativos estratificada por año y provincia."""
    positivos = tabla[tabla["objetivo"] == 1]
    negativos = tabla[tabla["objetivo"] == 0]
    estratos = [negativos["periodo"].dt.year, negativos["ubigeo_prov"]]
    muestra = negativos.groupby(estratos, group_keys=False, observed=True).sample(
        frac=fraccion, random_state=semilla
    )
    return pd.concat([positivos, muestra]).sort_index()

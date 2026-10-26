"""M2. Inferencia por lotes: verifica el SHA-256 del artefacto y estima la probabilidad
por celda y mes, un año a la vez para acotar la memoria."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd

from pfc_datos.modelos import RepositorioModelos
from pfc_datos.protocolos import LectorMatriz


def clasificar(probabilidad: np.ndarray, limites: list[float]) -> np.ndarray:
    """Nivel 1 (Baja) a 4 (Muy alta) según los tres cortes calibrados con el Especialista."""
    return (np.searchsorted(np.asarray(limites), probabilidad, side="right") + 1).astype("int8")


def inferir(lector: LectorMatriz, modelos: RepositorioModelos, algoritmo: str, version: str,
            anios: range, variables: list[str]) -> Iterator[pd.DataFrame]:
    modelo, _ = modelos.cargar(algoritmo, version)  # IntegridadArtefactoError si no coincide
    for anio in anios:
        lote = lector.leer(range(anio, anio + 1), ["id_celda", "periodo", *variables])
        lote["probabilidad"] = modelo.predict_proba(lote[variables])[:, 1].astype("float32")
        yield lote[["id_celda", "periodo", "probabilidad", "precip_mes_mm", "precip_max3d_mm",
                    "precip_ant90_mm"]]

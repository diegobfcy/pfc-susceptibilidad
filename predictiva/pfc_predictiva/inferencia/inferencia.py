"""M2. Inferencia por lotes: verifica el SHA-256 del artefacto y estima la probabilidad
por celda y mes, un año a la vez para acotar la memoria."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
from pfc_datos.modelos import RepositorioModelos
from pfc_datos.protocolos import LectorMatriz


class ProbabilidadInvalidaError(ValueError):
    """Una probabilidad está fuera de [0, 1] o no es un número (RF-07)."""


def clasificar(probabilidad: np.ndarray, limites: list[float]) -> np.ndarray:
    """Nivel 1 (Baja) a 4 (Muy alta) según los cortes vigentes de la Tabla 27."""
    probabilidad = np.asarray(probabilidad)
    if not np.all((probabilidad >= 0) & (probabilidad <= 1)):  # NaN también incumple
        raise ProbabilidadInvalidaError("probabilidad fuera de [0, 1]")
    return (np.searchsorted(np.asarray(limites), probabilidad, side="right") + 1).astype("int8")


def inferir(
    lector: LectorMatriz,
    modelos: RepositorioModelos,
    algoritmo: str,
    version: str,
    anios: range,
    variables: list[str],
) -> Iterator[pd.DataFrame]:
    """Estima la probabilidad por celda-mes, un año por lote, después de verificar el artefacto.

    Lanza IntegridadArtefactoError si el artefacto no coincide con su huella.
    """
    modelo, _ = modelos.cargar(algoritmo, version)  # IntegridadArtefactoError si no coincide
    for anio in anios:
        lote = lector.leer(range(anio, anio + 1), ["id_celda", "periodo", *variables])
        lote["probabilidad"] = modelo.predict_proba(lote[variables])[:, 1].astype("float32")
        yield lote[
            [
                "id_celda",
                "periodo",
                "probabilidad",
                "precip_mes_mm",
                "precip_max3d_mm",
                "precip_ant90_mm",
            ]
        ]

"""E3. Verificación de calidad de los datasets (RF-06): integridad de campos, valores nulos,
rango documentado y continuidad temporal. Los registros que no cumplen se separan con el
código de la regla incumplida; un faltante en la serie detiene el procesamiento."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from pfc_etl.verificacion.reglas import ReglaIntegridad, construir_reglas


@dataclass
class ResultadoVerificacion:
    """Resultado de verificar una fuente: filas válidas, rechazos por regla y faltantes."""

    fuente: str
    filas: int
    validos: pd.DataFrame
    rechazados: dict[str, int] = field(default_factory=dict)
    faltantes: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        """True si la serie no tiene faltantes: solo entonces sigue el procesamiento."""
        return not self.faltantes


def verificar_dataset(
    fuente: str, tabla: pd.DataFrame, reglas: dict[str, Any], tolerancia: float = 0.0
) -> ResultadoVerificacion:
    """Aplica las reglas de RF-06 configuradas para la fuente (ver reglas.py)."""
    resultado = ResultadoVerificacion(fuente, len(tabla), tabla)
    validos = pd.Series(True, index=tabla.index)
    for regla in construir_reglas(reglas, tolerancia):
        for codigo, incumple in regla.evaluar(tabla, resultado.faltantes):
            n = int((incumple & validos).sum())
            if n:
                resultado.rechazados[codigo] = resultado.rechazados.get(codigo, 0) + n
            validos &= ~incumple
        if isinstance(regla, ReglaIntegridad) and resultado.faltantes:
            break  # sin las columnas declaradas no se pueden evaluar las demás reglas
    resultado.validos = tabla[validos]
    return resultado

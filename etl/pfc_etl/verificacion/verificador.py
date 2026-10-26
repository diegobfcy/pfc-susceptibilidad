"""E3. Verificación de calidad de los datasets (RF-06): integridad de campos, valores nulos,
rango documentado y continuidad temporal. Los registros que no cumplen se separan con el
código de la regla incumplida; un faltante en la serie detiene el procesamiento."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class ResultadoVerificacion:
    fuente: str
    filas: int
    validos: pd.DataFrame
    rechazados: dict[str, int] = field(default_factory=dict)
    faltantes: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.faltantes


def verificar_dataset(
    fuente: str, tabla: pd.DataFrame, reglas: dict[str, Any]
) -> ResultadoVerificacion:
    """Aplica las cuatro reglas de RF-06 configuradas para la fuente."""
    resultado = ResultadoVerificacion(fuente, len(tabla), tabla)
    faltan = [c for c in reglas.get("columnas", []) if c not in tabla.columns]
    if faltan:
        resultado.rechazados["INTEGRIDAD_CAMPOS"] = len(tabla)
        resultado.validos = tabla.iloc[0:0]
        resultado.faltantes = [f"columna {c}" for c in faltan]
        return resultado
    mascara = pd.Series(True, index=tabla.index)
    for columna in reglas.get("columnas", []):
        nulos = tabla[columna].isna()
        if nulos.any():
            resultado.rechazados["VALOR_NULO"] = resultado.rechazados.get("VALOR_NULO", 0) + int(
                (nulos & mascara).sum()
            )
            mascara &= ~nulos
    for columna, (minimo, maximo) in reglas.get("rango", {}).items():
        fuera = (tabla[columna] < minimo) | (tabla[columna] > maximo)
        if fuera.any():
            codigo = f"RANGO_{columna.upper()}"
            resultado.rechazados[codigo] = int((fuera & mascara).sum())
            mascara &= ~fuera
    resultado.validos = tabla[mascara]
    frecuencia = reglas.get("frecuencia")
    if frecuencia:
        if "fecha" in tabla.columns:
            fechas = pd.DatetimeIndex(tabla["fecha"].unique())
        else:
            fechas = pd.DatetimeIndex(
                pd.to_datetime({"year": tabla["anio"], "month": tabla["mes"], "day": 1})
            )
        esperadas = pd.date_range(fechas.min(), fechas.max(), freq=frecuencia)
        ausentes = esperadas.difference(fechas)
        if len(ausentes) > 0:
            resultado.faltantes = [f"{f:%Y-%m-%d}" for f in ausentes]
    return resultado

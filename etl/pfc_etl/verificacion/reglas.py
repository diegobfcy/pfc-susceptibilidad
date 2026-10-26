"""E3. Reglas de calidad de RF-06 (patrón Strategy): cada regla es una clase independiente y
el verificador solo recorre las reglas configuradas para la fuente en config.yaml."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

import pandas as pd

Incumplimiento = tuple[str, pd.Series]  # código de la regla y máscara de filas que no cumplen


class ReglaCalidad(ABC):
    """Interfaz común: devuelve los incumplimientos y registra los faltantes de la serie."""

    @abstractmethod
    def evaluar(self, tabla: pd.DataFrame, faltantes: list[str]) -> Iterator[Incumplimiento]: ...


class ReglaIntegridad(ReglaCalidad):
    """Todas las columnas declaradas existen; si falta alguna, se rechaza el dataset completo."""

    def __init__(self, columnas: list[str]) -> None:
        self._columnas = columnas

    def evaluar(self, tabla: pd.DataFrame, faltantes: list[str]) -> Iterator[Incumplimiento]:
        ausentes = [c for c in self._columnas if c not in tabla.columns]
        if ausentes:
            faltantes.extend(f"columna {c}" for c in ausentes)
            yield "INTEGRIDAD_CAMPOS", pd.Series(True, index=tabla.index)


class ReglaNulos(ReglaCalidad):
    def __init__(self, columnas: list[str]) -> None:
        self._columnas = columnas

    def evaluar(self, tabla: pd.DataFrame, faltantes: list[str]) -> Iterator[Incumplimiento]:
        yield "VALOR_NULO", tabla[self._columnas].isna().any(axis=1)


class ReglaRango(ReglaCalidad):
    """Rango físico documentado por columna, con la tolerancia de config.yaml en los bordes."""

    def __init__(self, rangos: dict[str, list[float]], tolerancia: float = 0.0) -> None:
        self._rangos = rangos
        self._tolerancia = tolerancia

    def evaluar(self, tabla: pd.DataFrame, faltantes: list[str]) -> Iterator[Incumplimiento]:
        for columna, (minimo, maximo) in self._rangos.items():
            valores = tabla[columna]
            fuera = (valores < minimo - self._tolerancia) | (valores > maximo + self._tolerancia)
            yield f"RANGO_{columna.upper()}", fuera


class ReglaContinuidad(ReglaCalidad):
    """Sin huecos en la serie temporal: cada fecha ausente detiene el procesamiento."""

    def __init__(self, frecuencia: str) -> None:
        self._frecuencia = frecuencia

    def evaluar(self, tabla: pd.DataFrame, faltantes: list[str]) -> Iterator[Incumplimiento]:
        fechas = self._fechas(tabla)
        esperadas = pd.date_range(fechas.min(), fechas.max(), freq=self._frecuencia)
        faltantes.extend(f"{f:%Y-%m-%d}" for f in esperadas.difference(fechas))
        return iter(())

    @staticmethod
    def _fechas(tabla: pd.DataFrame) -> pd.DatetimeIndex:
        if "fecha" in tabla.columns:
            return pd.DatetimeIndex(tabla["fecha"].unique())
        return pd.DatetimeIndex(
            pd.to_datetime({"year": tabla["anio"], "month": tabla["mes"], "day": 1})
        )


def construir_reglas(config_fuente: dict[str, Any], tolerancia: float = 0.0) -> list[ReglaCalidad]:
    """Reglas de una fuente, en el orden de RF-06, a partir de su bloque de config.yaml."""
    columnas = config_fuente.get("columnas", [])
    reglas: list[ReglaCalidad] = [ReglaIntegridad(columnas), ReglaNulos(columnas)]
    if config_fuente.get("rango"):
        reglas.append(ReglaRango(config_fuente["rango"], tolerancia))
    if config_fuente.get("frecuencia"):
        reglas.append(ReglaContinuidad(config_fuente["frecuencia"]))
    return reglas

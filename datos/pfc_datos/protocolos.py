"""Interfaces (typing.Protocol) que las capas superiores usan para acceder a D1, D2 y D3.

Cada consumidor depende solo de la interfaz que necesita (ISP) y la recibe por constructor
(DIP); las pruebas unitarias las sustituyen por dobles en memoria."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


@dataclass(frozen=True)
class ArchivoRegistrado:
    """Archivo de una fuente conservado en D2 con su huella de integridad."""

    fuente: str
    ruta: Path
    sha256: str
    bytes: int


class AlmacenArtefactos(Protocol):
    def ruta_temporal(self, fuente: str, nombre: str) -> Path: ...

    def registrar(self, fuente: str, ruta: Path, sha256: str) -> ArchivoRegistrado: ...


class RegistroBitacora(Protocol):
    def registrar(self, tipo: str, componente: str, descripcion: str, **detalle: Any) -> None: ...


class LectorMatriz(Protocol):
    def leer(self, anios: range, columnas: list[str] | None = None) -> pd.DataFrame: ...


class EscritorMatriz(Protocol):
    def escribir_anio(self, anio: int, matriz: pd.DataFrame) -> Path: ...

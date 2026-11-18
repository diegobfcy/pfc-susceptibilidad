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
    """Interfaz del almacén de archivos de fuentes en D2."""

    def ruta_temporal(self, fuente: str, nombre: str) -> Path:
        """Ruta donde descargar un archivo antes de verificarlo."""

    def registrar(self, fuente: str, ruta: Path, sha256: str) -> ArchivoRegistrado:
        """Conserva el archivo en D2 si su huella coincide con la esperada."""


class RegistroBitacora(Protocol):
    """Interfaz de la bitácora de solo inserción (D3)."""

    def registrar(self, tipo: str, componente: str, descripcion: str, **detalle: Any) -> None:
        """Registra un evento INFORMATIVO, ADVERTENCIA o ERROR de un componente."""


class LectorMatriz(Protocol):
    """Interfaz de lectura de la matriz de variables por celda-mes."""

    def leer(self, anios: range, columnas: list[str] | None = None) -> pd.DataFrame:
        """Lee la matriz de los años pedidos, con las columnas indicadas o con todas."""


class EscritorMatriz(Protocol):
    """Interfaz de escritura de la matriz de variables, un año por archivo."""

    def escribir_anio(self, anio: int, matriz: pd.DataFrame) -> Path:
        """Escribe la matriz de un año y devuelve la ruta del archivo."""

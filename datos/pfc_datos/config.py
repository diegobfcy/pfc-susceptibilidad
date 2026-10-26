"""Lectura de config.yaml y rutas de los almacenes D2 (archivos) del sistema."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def cargar_config(ruta: Path | None = None) -> dict[str, Any]:
    """Devuelve la configuración central (config/config.yaml)."""
    ruta = ruta or Path(os.environ.get("PFC_CONFIG", RAIZ / "config" / "config.yaml"))
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def ruta_datos_origen() -> Path:
    """Carpeta con los insumos crudos y procesados de las fuentes (fuera del repositorio)."""
    return Path(os.environ.get("PFC_DATOS_ORIGEN", RAIZ / "data" / "origen"))


def ruta_d2() -> Path:
    """Repositorio de archivos D2: matriz de variables, artefactos y resultados."""
    ruta = Path(os.environ.get("PFC_D2", RAIZ / "data" / "d2"))
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta

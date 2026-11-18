"""D1: conexión a PostgreSQL 18 + PostGIS 3.7 con consultas parametrizadas."""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def crear_motor(url: str | None = None) -> Engine:
    """Motor SQLAlchemy a partir de PFC_BD_URL (nunca se escribe en el código)."""
    url = url or os.environ["PFC_BD_URL"]
    return create_engine(url, pool_pre_ping=True)


def consultar(motor: Engine, sql: str, **parametros: Any) -> list[dict[str, Any]]:
    """Ejecuta una consulta de lectura con parámetros enlazados y devuelve las filas como
    diccionarios.
    """
    with motor.connect() as conexion:
        return [dict(f) for f in conexion.execute(text(sql), parametros).mappings()]


def ejecutar(motor: Engine, sql: str, **parametros: Any) -> Any:
    """Ejecuta una sentencia de escritura con parámetros enlazados dentro de una transacción."""
    with motor.begin() as conexion:
        return conexion.execute(text(sql), parametros)

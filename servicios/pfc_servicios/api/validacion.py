"""S1. Validación estricta de entradas según el contrato OpenAPI."""

from __future__ import annotations

import datetime as dt
from typing import Any

from flask import abort, request

FECHA_MIN = dt.date(2000, 1, 1)
FECHA_MAX = dt.date(2026, 12, 31)


def cuerpo_json() -> dict[str, Any]:
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "cuerpo JSON requerido")
    return datos


def texto(datos: dict[str, Any], campo: str, largo_max: int) -> str:
    valor = datos.get(campo)
    if not isinstance(valor, str) or not 0 < len(valor) <= largo_max:
        abort(400, f"{campo} inválido")
    return valor


def fecha(datos: dict[str, Any], campo: str) -> dt.date:
    try:
        valor = dt.date.fromisoformat(str(datos.get(campo, "")))
    except ValueError:
        abort(400, f"{campo} inválida")
    if not FECHA_MIN <= valor <= FECHA_MAX:
        abort(400, f"{campo} fuera del periodo")
    return valor


def opcion(datos: dict[str, Any], campo: str, permitidas: frozenset[str]) -> str:
    valor = datos.get(campo)
    if valor not in permitidas:
        abort(400, f"{campo} inválido")
    return str(valor)

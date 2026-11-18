"""S1. Validación estricta de entradas según el contrato OpenAPI."""

from __future__ import annotations

import datetime as dt
from typing import Any

from flask import abort, request

FECHA_MIN = dt.date(2000, 1, 1)
FECHA_MAX = dt.date(2026, 12, 31)


def cuerpo_json() -> dict[str, Any]:
    """Cuerpo JSON de la solicitud como objeto; 400 si falta o no es un objeto."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        abort(400, "cuerpo JSON requerido")
    return datos


def texto(datos: dict[str, Any], campo: str, largo_max: int) -> str:
    """Campo de texto no vacío y de largo acotado; 400 si no lo es."""
    valor = datos.get(campo)
    if not isinstance(valor, str) or not 0 < len(valor) <= largo_max:
        abort(400, f"{campo} inválido")
    return valor


def fecha(datos: dict[str, Any], campo: str) -> dt.date:
    """Campo de fecha ISO 8601 dentro de la serie 2000–2026; 400 si no lo es."""
    try:
        valor = dt.date.fromisoformat(str(datos.get(campo, "")))
    except ValueError:
        abort(400, f"{campo} inválida")
    if not FECHA_MIN <= valor <= FECHA_MAX:
        abort(400, f"{campo} fuera del periodo")
    return valor


def opcion(datos: dict[str, Any], campo: str, permitidas: frozenset[str]) -> str:
    """Campo cuyo valor debe estar entre los permitidos; 400 si no lo está."""
    valor = datos.get(campo)
    if valor not in permitidas:
        abort(400, f"{campo} inválido")
    return str(valor)


def periodo_mensual(valor: str | None) -> dt.date:
    """Periodo AAAA-MM de la serie, como primer día del mes."""
    try:
        resultado = dt.date.fromisoformat(f"{valor}-01")
    except (TypeError, ValueError):
        abort(400, "periodo inválido; formato AAAA-MM")
    if not FECHA_MIN <= resultado <= FECHA_MAX:
        abort(400, "periodo fuera de la serie")
    return resultado


def fecha_opcional(valor: str | None, campo: str) -> dt.date | None:
    """Fecha ISO 8601 de un parámetro de consulta, o None si viene vacío; 400 si es inválida."""
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(valor)
    except ValueError:
        abort(400, f"{campo} inválida")


def coordenada(valor: str | None, minimo: float, maximo: float, campo: str) -> float:
    """Número dentro del rango dado (también rechaza NaN); 400 si no lo es."""
    try:
        numero = float(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        abort(400, f"{campo} inválida")
    if not minimo <= numero <= maximo:  # NaN también se rechaza
        abort(400, f"{campo} fuera de rango")
    return numero


def entero_positivo(datos: dict[str, Any], campo: str) -> int:
    """Campo entero mayor que cero (no booleano); 400 si no lo es."""
    valor = datos.get(campo)
    if not isinstance(valor, int) or isinstance(valor, bool) or valor < 1:
        abort(400, f"{campo} inválido")
    return valor


def rechazar_campos_extra(datos: dict[str, Any], permitidos: frozenset[str]) -> None:
    """400 si el cuerpo trae campos fuera de los permitidos."""
    if set(datos) - permitidos:
        abort(400, "campos no permitidos")

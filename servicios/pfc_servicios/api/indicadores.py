"""S1. Panel de indicadores (RF-12, CU-03) e historial de operaciones (RF-14, CU-05)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from pfc_servicios.api.ingestas import json_seguro
from pfc_servicios.api.validacion import fecha_opcional
from pfc_servicios.seguridad.acceso import requiere_rol

bp = Blueprint("indicadores", __name__)
ROLES = ("INVESTIGADOR", "ASESOR")
TIPOS_EVENTO = frozenset({"INFORMATIVO", "ADVERTENCIA", "ERROR"})


@bp.get("/indicadores")
@requiere_rol(*ROLES)
def indicadores() -> ResponseReturnValue:
    """GET /indicadores: métricas por versión, PSI, últimos procesamientos y distribución de
    niveles (RF-12).
    """
    datos = current_app.extensions["pfc"]["resultados"].indicadores()
    datos["procesamientos"] = [json_seguro(f) for f in datos["procesamientos"]]
    return jsonify(datos)


@bp.get("/bitacora")
@requiere_rol(*ROLES)
def bitacora() -> ResponseReturnValue:
    """GET /bitacora: eventos filtrados por fecha y tipo (RF-14); 400 si el tipo no es válido."""
    tipo = request.args.get("tipo") or None
    if tipo is not None and tipo not in TIPOS_EVENTO:
        abort(400, "tipo inválido")
    eventos = current_app.extensions["pfc"]["resultados"].bitacora(
        fecha_opcional(request.args.get("desde"), "desde"),
        fecha_opcional(request.args.get("hasta"), "hasta"),
        tipo,
    )
    return jsonify(eventos=[json_seguro(e) for e in eventos])

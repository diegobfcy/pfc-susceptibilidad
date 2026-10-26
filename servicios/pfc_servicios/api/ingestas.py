"""S1. Procesamientos de CU-01: crear (POST /ingestas) y consultar estado (GET /ingestas/{id})."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, session
from flask.typing import ResponseReturnValue

from pfc_servicios.api.validacion import cuerpo_json, fecha, opcion
from pfc_servicios.seguridad.acceso import requiere_rol

bp = Blueprint("ingestas", __name__)
TIPOS = frozenset({"INGESTA", "ENTRENAMIENTO", "INFERENCIA"})


@bp.post("/ingestas")
@requiere_rol("INVESTIGADOR")
def crear_ingesta() -> ResponseReturnValue:
    datos = cuerpo_json()
    tipo = opcion(datos, "tipo", TIPOS)
    desde, hasta = fecha(datos, "fecha_desde"), fecha(datos, "fecha_hasta")
    if hasta < desde:
        abort(400, "fecha_hasta anterior a fecha_desde")
    repo = current_app.extensions["pfc"]["procesamientos"]
    id_procesamiento = repo.crear(session["id_usuario"], tipo, desde, hasta)
    return jsonify(id_procesamiento=id_procesamiento, estado="PENDIENTE"), 202


@bp.get("/ingestas/<int:id_procesamiento>")
@requiere_rol("INVESTIGADOR", "ESPECIALISTA", "ASESOR")
def estado_ingesta(id_procesamiento: int) -> ResponseReturnValue:
    fila = current_app.extensions["pfc"]["procesamientos"].obtener(id_procesamiento)
    if fila is None:
        abort(404)
    return jsonify({k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in fila.items()})

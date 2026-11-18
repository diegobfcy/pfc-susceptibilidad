"""S1. Inferencia por lotes con una versión del modelo (RF-03, RF-07)."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify
from flask.typing import ResponseReturnValue
from pfc_datos.almacen import sha256_archivo

from pfc_servicios.api.ingestas import encolar, json_seguro, ventana
from pfc_servicios.api.validacion import (
    cuerpo_json,
    entero_positivo,
    rechazar_campos_extra,
    texto,
)
from pfc_servicios.seguridad.acceso import requiere_rol

bp = Blueprint("inferencias", __name__)
# La versión 1 sigue CANDIDATA hasta el hito 2; una RECHAZADA o en REVISION nunca se aplica.
ESTADOS_APLICABLES = frozenset({"APROBADA", "CANDIDATA"})


@bp.post("/inferencias")
@requiere_rol("INVESTIGADOR")
def crear_inferencia() -> ResponseReturnValue:
    """POST /inferencias: encola la inferencia de una ventana con una versión del modelo.

    Responde 422 si la versión no es aplicable o si su artefacto no coincide con la huella
    registrada, y 409 si ya hay un procesamiento activo.
    """
    datos = cuerpo_json()
    rechazar_campos_extra(
        datos, frozenset({"fecha_desde", "fecha_hasta", "id_modelo_version", "departamento"})
    )
    desde, hasta = ventana(datos)
    id_version = entero_positivo(datos, "id_modelo_version")
    pfc = current_app.extensions["pfc"]
    departamento = None
    if datos.get("departamento") is not None:  # zona (RF-01); sin ella, la macrorregión
        departamento = texto(datos, "departamento", 2)
        validos = {d["id"] for d in pfc["resultados"].ambitos()["departamentos"]}
        if departamento not in validos:
            abort(422, "el departamento no pertenece a la macrorregión")
    version = pfc["versiones"].obtener(id_version)
    if version is None or version["estado"] not in ESTADOS_APLICABLES:
        abort(422, "la versión del modelo no se puede aplicar")
    ruta = Path(version["ruta_artefacto"])
    if not ruta.is_file() or sha256_archivo(ruta) != version["sha256"]:
        if bitacora := pfc.get("bitacora"):
            bitacora.registrar("ERROR", "S1", "artefacto alterado", id_version=id_version)
        abort(422, "el SHA-256 del artefacto no coincide")
    return encolar("INFERENCIA", desde, hasta, id_version, departamento)


@bp.get("/inferencias/<int:id_procesamiento>")
@requiere_rol("INVESTIGADOR", "ASESOR")
def estado_inferencia(id_procesamiento: int) -> ResponseReturnValue:
    """GET /inferencias/{id}: estado, fase, tiempos y memoria; 404 si no existe."""
    fila = current_app.extensions["pfc"]["procesamientos"].obtener(id_procesamiento)
    if fila is None or fila["tipo"] != "INFERENCIA":
        abort(404)
    return jsonify(json_seguro(fila))

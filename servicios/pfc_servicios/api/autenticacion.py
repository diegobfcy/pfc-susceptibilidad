"""S1. Inicio y cierre de sesión (CU-00)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue

from pfc_servicios.api.validacion import cuerpo_json, texto
from pfc_servicios.seguridad.claves import autenticar

bp = Blueprint("autenticacion", __name__)


@bp.post("/sesion")
def iniciar_sesion() -> ResponseReturnValue:
    datos = cuerpo_json()
    correo = texto(datos, "correo", 150)
    clave = texto(datos, "clave", 128)
    usuario = autenticar(current_app.extensions["pfc"]["usuarios"], correo, clave)
    if usuario is None:
        abort(401)  # mensaje genérico: no revela si el correo existe
    session.clear()
    session.update(id_usuario=usuario.id_usuario, rol=usuario.rol)
    return jsonify(rol=usuario.rol), 200


@bp.delete("/sesion")
def cerrar_sesion() -> ResponseReturnValue:
    session.clear()
    return "", 204

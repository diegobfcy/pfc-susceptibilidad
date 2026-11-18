"""S1. Inicio y cierre de sesión (CU-00)."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, session
from flask.typing import ResponseReturnValue
from flask_wtf.csrf import generate_csrf

from pfc_servicios.api.validacion import cuerpo_json, texto
from pfc_servicios.seguridad.claves import CuentaBloqueadaError, autenticar

bp = Blueprint("autenticacion", __name__)


@bp.get("/sesion/csrf")
def token_csrf() -> ResponseReturnValue:
    """Token CSRF de la sesión actual; se renueva al iniciar sesión."""
    return jsonify(csrf=generate_csrf()), 200


@bp.get("/sesion")
def sesion_actual() -> ResponseReturnValue:
    """GET /sesion: rol y correo de la sesión activa; 401 sin sesión."""
    if "id_usuario" not in session:
        abort(401)
    return jsonify(rol=session["rol"], correo=session["correo"]), 200


@bp.post("/auth/login")
def iniciar_sesion() -> ResponseReturnValue:
    """204 con cookie de sesión; 401 genérico; 423 al quinto fallo; 429 lo aplica el proxy."""
    datos = cuerpo_json()
    correo = texto(datos, "correo", 150)
    clave = texto(datos, "clave", 128)
    pfc = current_app.extensions["pfc"]
    try:
        usuario = autenticar(pfc["usuarios"], correo, clave)
    except CuentaBloqueadaError:
        _registrar(pfc, "ADVERTENCIA", "cuenta bloqueada por intentos fallidos", correo=correo)
        abort(423, "cuenta bloqueada temporalmente")
    if usuario is None:
        _registrar(pfc, "ADVERTENCIA", "inicio de sesión rechazado", correo=correo)
        abort(401)  # mensaje genérico: no revela si el correo existe
    session.clear()
    session.update(id_usuario=usuario.id_usuario, rol=usuario.rol, correo=usuario.correo)
    return "", 204


@bp.delete("/sesion")
def cerrar_sesion() -> ResponseReturnValue:
    """DELETE /sesion: borra la sesión y responde 204."""
    session.clear()
    return "", 204


def _registrar(pfc: dict, tipo: str, descripcion: str, **detalle: str) -> None:
    bitacora = pfc.get("bitacora")
    if bitacora is not None:
        bitacora.registrar(tipo, "S2", descripcion, **detalle)

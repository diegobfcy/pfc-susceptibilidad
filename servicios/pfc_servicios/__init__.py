"""Capa de Servicios: aplicación Flask con los blueprints de S1 y la seguridad de S2."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask, jsonify
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from pfc_servicios.seguridad.acceso import registrar_cabeceras


def crear_app(dependencias: dict[str, Any] | None = None) -> Flask:
    """Fábrica de la aplicación; las dependencias (repositorios de D1) se inyectan (DIP)."""
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=os.environ.get("PFC_SECRETO_SESION", os.urandom(32)),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        MAX_CONTENT_LENGTH=16 * 1024,
        JSON_AS_ASCII=False,
    )
    app.extensions["pfc"] = dependencias if dependencias is not None else _dependencias_bd()
    CSRFProtect(app)  # POST/DELETE exigen la cabecera X-CSRFToken (OWASP A01)
    registrar_cabeceras(app)

    from pfc_servicios.api import autenticacion, ingestas, salud

    for modulo in (autenticacion, ingestas, salud):
        app.register_blueprint(modulo.bp, url_prefix="/api")

    @app.errorhandler(HTTPException)
    def error_http(error: HTTPException) -> tuple[Any, int]:
        return jsonify(error=error.name, detalle=error.description), error.code or 500

    return app


def _dependencias_bd() -> dict[str, Any]:
    from pfc_datos.bd import consultar, crear_motor
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD

    motor = crear_motor()
    return {
        "usuarios": UsuariosBD(motor),
        "procesamientos": ProcesamientosBD(motor),
        "comprobar_bd": lambda: consultar(motor, "SELECT 1 AS ok")[0]["ok"] == 1,
    }

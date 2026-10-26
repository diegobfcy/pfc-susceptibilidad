"""S1. Endpoint técnico de verificación de salud para las pruebas de humo del despliegue."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

bp = Blueprint("salud", __name__)


@bp.get("/salud")
def salud() -> ResponseReturnValue:
    comprobar = current_app.extensions["pfc"].get("comprobar_bd")
    bd_ok = bool(comprobar()) if comprobar else False
    return jsonify(estado="ok" if bd_ok else "degradado", base_datos=bd_ok), (
        200 if bd_ok else 503
    )

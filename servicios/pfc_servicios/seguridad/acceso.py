"""S2. Control de acceso basado en roles (RBAC) por endpoint y cabeceras de seguridad."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Flask, Response, abort, session

CSP = (
    "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; "
    "style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
    "base-uri 'self'; form-action 'self'"
)


def requiere_rol(*roles: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """401 si no hay sesión; 403 si el rol de la sesión no está autorizado."""

    def decorador(funcion: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(funcion)
        def envoltura(*args: Any, **kwargs: Any) -> Any:
            if "id_usuario" not in session:
                abort(401)
            if session.get("rol") not in roles:
                abort(403)
            return funcion(*args, **kwargs)

        return envoltura

    return decorador


def registrar_cabeceras(app: Flask) -> None:
    @app.after_request
    def cabeceras(respuesta: Response) -> Response:
        respuesta.headers["Content-Security-Policy"] = CSP
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "same-origin"
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return respuesta

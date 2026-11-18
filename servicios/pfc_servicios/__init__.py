"""Capa de Servicios: aplicación Flask con los blueprints de S1 y la seguridad de S2."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from flask import Flask, current_app, jsonify, request
from flask_wtf.csrf import CSRFProtect
from werkzeug.exceptions import HTTPException

from pfc_servicios.seguridad.acceso import registrar_cabeceras


class CSRFCabecera(CSRFProtect):
    """S2. CSRF en todas las solicitudes POST y DELETE, con el token solo en la cabecera.

    El token viaja en X-CSRFToken y no se lee el cuerpo antes de la ruta: la carga manual (RF-02)
    comprueba el rol y su límite de 2 GB antes de recibir el archivo, sin quedar exenta.
    """

    def _get_csrf_token(self) -> str | None:
        for cabecera in current_app.config["WTF_CSRF_HEADERS"]:
            if token := request.headers.get(cabecera):
                return str(token)
        return None


CODIGOS_FUENTE = {
    "ersst_v5": "ERSST_V5",
    "era5_land": "ERA5_LAND",
    "dem_glo30": "DEM_GLO30",
    "inventario": "INVENTARIO",
}


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
    CSRFCabecera(app)  # POST/DELETE exigen la cabecera X-CSRFToken (OWASP A01)
    registrar_cabeceras(app)

    from pfc_servicios.api import autenticacion, indicadores, inferencias, ingestas, mapas, salud

    for modulo in (autenticacion, indicadores, inferencias, ingestas, mapas, salud):
        app.register_blueprint(modulo.bp, url_prefix="/api")

    @app.errorhandler(HTTPException)
    def error_http(error: HTTPException) -> tuple[Any, int]:
        return jsonify(error=error.name, detalle=error.description), error.code or 500

    return app


def _dependencias_bd() -> dict[str, Any]:
    from pfc_datos.almacen import AlmacenArchivos, MatrizParquet
    from pfc_datos.bd import consultar, crear_motor
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.config import ruta_d2
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD
    from pfc_datos.resultados import ResultadosBD, VersionesBD, registrar_dataset

    from pfc_servicios.teselas.mvt import TeselasBD

    motor = crear_motor()
    d2 = ruta_d2()
    bitacora = BitacoraBD(motor)
    almacen = AlmacenArchivos(d2)

    def hay_datos_verificados(desde: Any, hasta: Any) -> bool:
        disponibles = set(MatrizParquet(d2).anios_disponibles())
        return set(range(desde.year, hasta.year + 1)) <= disponibles

    def carga_manual(fuente: str, nombre: str, flujo: Any, id_usuario: int) -> Any:
        huella = hashlib.sha256()
        destino = almacen.ruta_temporal(fuente, nombre)
        with destino.open("wb") as salida:
            for bloque in iter(lambda: flujo.read(1 << 20), b""):
                huella.update(bloque)
                salida.write(bloque)
        registro = almacen.registrar(fuente, destino, huella.hexdigest())
        registrar_dataset(
            motor,
            {
                "fuente": CODIGOS_FUENTE[fuente],
                "ruta": str(registro.ruta),
                "sha256": registro.sha256,
                "id_usuario": id_usuario,
            },
        )
        bitacora.registrar(
            "INFORMATIVO",
            "E2",
            "CARGA_MANUAL",
            id_usuario=id_usuario,
            fuente=fuente,
            sha256=registro.sha256,
        )
        return registro

    return {
        "usuarios": UsuariosBD(motor),
        "procesamientos": ProcesamientosBD(motor),
        "versiones": VersionesBD(motor),
        "resultados": ResultadosBD(motor),
        "teselas": TeselasBD(motor),
        "bitacora": bitacora,
        "hay_datos_verificados": hay_datos_verificados,
        "carga_manual": carga_manual,
        "comprobar_bd": lambda: consultar(motor, "SELECT 1 AS ok")[0]["ok"] == 1,
    }

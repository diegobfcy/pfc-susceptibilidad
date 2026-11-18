"""S1/S3. Teselas, ámbitos, periodos, límites y consulta del valor por clic (RF-08 a RF-11)."""

from __future__ import annotations

import re

from flask import Blueprint, Response, abort, current_app, jsonify, request
from flask.typing import ResponseReturnValue

from pfc_servicios.api.ingestas import json_seguro
from pfc_servicios.api.validacion import coordenada, periodo_mensual
from pfc_servicios.seguridad.acceso import requiere_rol
from pfc_servicios.teselas.mvt import CAPAS, tesela_valida

bp = Blueprint("mapas", __name__)
ROLES_MAPA = ("INVESTIGADOR", "ESPECIALISTA")
TIPO_MVT = "application/vnd.mapbox-vector-tile"
UBIGEO_DEP, UBIGEO_PROV = re.compile(r"^\d{2}$"), re.compile(r"^\d{4}$")


def _filtro(nombre: str, patron: re.Pattern[str]) -> str | None:
    valor = request.args.get(nombre)
    if valor and not patron.match(valor):
        abort(400, f"{nombre} inválido")
    return valor or None


@bp.get("/mapas/<capa>/<periodo>/<int:z>/<int:x>/<int:y>.pbf")
@requiere_rol(*ROLES_MAPA)
def tesela(capa: str, periodo: str, z: int, x: int, y: int) -> ResponseReturnValue:
    """GET /mapas/{capa}/{periodo}/{z}/{x}/{y}.pbf: tesela vectorial MVT de una capa (RF-08).

    Aplica los filtros de departamento y provincia (RF-09). Responde 204 si la tesela está vacía y
    404 si la capa, la tesela o el periodo no existen.
    """
    if capa not in CAPAS or not tesela_valida(z, x, y):
        abort(404)
    fecha = periodo_mensual(periodo)
    pfc = current_app.extensions["pfc"]
    if not pfc["resultados"].periodo_disponible(fecha):
        abort(404, "no hay resultados para el periodo")
    datos = pfc["teselas"].tesela(
        capa,
        fecha,
        z,
        x,
        y,
        departamento=_filtro("departamento", UBIGEO_DEP),
        provincia=_filtro("provincia", UBIGEO_PROV),
    )
    respuesta = Response(datos, mimetype=TIPO_MVT, status=200 if datos else 204)
    respuesta.headers["Cache-Control"] = "private, max-age=300"
    return respuesta


@bp.get("/consulta-punto")
@requiere_rol(*ROLES_MAPA)
def consulta_punto() -> ResponseReturnValue:
    """GET /consulta-punto: nivel, puntaje y variables de la celda en un punto y mes (RF-11)."""
    periodo = periodo_mensual(request.args.get("periodo"))
    lat = coordenada(request.args.get("lat"), -90, 90, "lat")
    lon = coordenada(request.args.get("lon"), -180, 180, "lon")
    fila = current_app.extensions["pfc"]["resultados"].consulta_punto(periodo, lat, lon)
    if fila is None:
        abort(404, "sin datos para ese punto y periodo")
    return jsonify(json_seguro(fila))


@bp.get("/periodos")
@requiere_rol(*ROLES_MAPA)
def periodos() -> ResponseReturnValue:
    """GET /periodos: periodos con resultados, para el selector de fecha del visor."""
    return jsonify(periodos=current_app.extensions["pfc"]["resultados"].periodos())


@bp.get("/ambitos")
@requiere_rol(*ROLES_MAPA)
def ambitos() -> ResponseReturnValue:
    """GET /ambitos: departamentos y provincias para los filtros del visor (RF-09)."""
    return jsonify(current_app.extensions["pfc"]["resultados"].ambitos())


@bp.get("/capas/limites")
@requiere_rol(*ROLES_MAPA)
def limites() -> ResponseReturnValue:
    """GET /capas/limites: límites provinciales en GeoJSON (RF-10)."""
    return jsonify(current_app.extensions["pfc"]["resultados"].limites())

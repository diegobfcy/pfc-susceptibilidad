"""S1. Procesamientos de CU-01: crear, consultar, cancelar y carga manual de archivos."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, request, session
from flask.typing import ResponseReturnValue
from pfc_datos.repositorios import ESTADOS_CANCELABLES, ProcesamientoActivoError
from werkzeug.utils import secure_filename

from pfc_servicios.api.validacion import cuerpo_json, fecha, opcion, rechazar_campos_extra
from pfc_servicios.seguridad.acceso import requiere_rol
from pfc_servicios.seguridad.archivos import ArchivoRechazadoError, comprobar_archivo

bp = Blueprint("ingestas", __name__)
TIPOS = frozenset({"INGESTA", "ENTRENAMIENTO"})
FUENTES = frozenset({"ersst_v5", "era5_land", "dem_glo30", "inventario"})
MAX_CARGA_BYTES = 2 * 1024**3


def json_seguro(fila: dict[str, Any]) -> dict[str, Any]:
    """Convierte las fechas de una fila a texto ISO 8601 para serializarla en JSON."""
    return {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in fila.items()}


def encolar(
    tipo: str,
    desde: dt.date,
    hasta: dt.date,
    modelo: int | None = None,
    departamento: str | None = None,
) -> Any:
    """Encola un procesamiento del usuario de la sesión y responde 202 con su identificador.

    Responde 409 si ya hay un procesamiento activo (RF-04).
    """
    pfc = current_app.extensions["pfc"]
    try:
        nuevo = pfc["procesamientos"].crear(
            session["id_usuario"], tipo, desde, hasta, modelo, departamento
        )
    except ProcesamientoActivoError:
        abort(409, "ya hay un procesamiento activo")
    if bitacora := pfc.get("bitacora"):
        bitacora.registrar(
            "INFORMATIVO",
            "S1",
            f"{tipo} encolado",
            id_usuario=session["id_usuario"],
            id_procesamiento=nuevo,
        )
    return jsonify(id_procesamiento=nuevo, estado="PENDIENTE"), 202


def ventana(datos: dict[str, Any]) -> tuple[dt.date, dt.date]:
    """Fechas fecha_desde y fecha_hasta del cuerpo; 400 si la ventana está invertida."""
    desde, hasta = fecha(datos, "fecha_desde"), fecha(datos, "fecha_hasta")
    if hasta < desde:
        abort(400, "fecha_hasta anterior a fecha_desde")
    return desde, hasta


@bp.post("/ingestas")
@requiere_rol("INVESTIGADOR")
def crear_ingesta() -> ResponseReturnValue:
    """POST /ingestas: encola una ingesta (o un entrenamiento, si se indica el tipo)."""
    datos = cuerpo_json()
    rechazar_campos_extra(datos, frozenset({"tipo", "fecha_desde", "fecha_hasta"}))
    tipo = opcion(datos, "tipo", TIPOS) if "tipo" in datos else "INGESTA"
    return encolar(tipo, *ventana(datos))


@bp.get("/ingestas/<int:id_procesamiento>")
@requiere_rol("INVESTIGADOR", "ASESOR")
def estado_ingesta(id_procesamiento: int) -> ResponseReturnValue:
    """GET /ingestas/{id}: estado de un procesamiento; 404 si no existe."""
    fila = current_app.extensions["pfc"]["procesamientos"].obtener(id_procesamiento)
    if fila is None:
        abort(404)
    return jsonify(json_seguro(fila))


@bp.get("/procesamientos/activo")
@requiere_rol("INVESTIGADOR", "ASESOR")
def procesamiento_activo() -> ResponseReturnValue:
    """GET /procesamientos/activo: el procesamiento en curso o en espera (IU-06); 204 si no hay."""
    fila = current_app.extensions["pfc"]["procesamientos"].activo()
    return (jsonify(json_seguro(fila)), 200) if fila else ("", 204)


@bp.post("/entrenamientos")
@requiere_rol("INVESTIGADOR")
def crear_entrenamiento() -> ResponseReturnValue:
    """POST /entrenamientos: encola un entrenamiento; 422 si la ventana no tiene datos."""
    datos = cuerpo_json()
    rechazar_campos_extra(datos, frozenset({"fecha_desde", "fecha_hasta"}))
    desde, hasta = ventana(datos)
    if not current_app.extensions["pfc"]["hay_datos_verificados"](desde, hasta):
        abort(422, "no hay datos verificados para la ventana")
    return encolar("ENTRENAMIENTO", desde, hasta)


@bp.post("/procesamientos/<int:id_procesamiento>/cancelar")
@requiere_rol("INVESTIGADOR")
def cancelar(id_procesamiento: int) -> ResponseReturnValue:
    """POST /procesamientos/{id}/cancelar: cancela un procesamiento activo y lo registra.

    Responde 404 si no existe y 409 si ya terminó.
    """
    pfc = current_app.extensions["pfc"]
    fila = pfc["procesamientos"].obtener(id_procesamiento)
    if fila is None:
        abort(404)
    if fila["estado"] not in ESTADOS_CANCELABLES or not pfc["procesamientos"].cancelar(
        id_procesamiento
    ):
        abort(409, "el procesamiento ya terminó")
    if bitacora := pfc.get("bitacora"):
        bitacora.registrar(
            "ADVERTENCIA",
            "S1",
            "procesamiento cancelado",
            id_usuario=session["id_usuario"],
            id_procesamiento=id_procesamiento,
        )
    return "", 204


@bp.post("/ingestas/<int:id_procesamiento>/archivos")
@requiere_rol("INVESTIGADOR")
def cargar_archivo(id_procesamiento: int) -> ResponseReturnValue:
    """RF-02: carga manual. Se comprueban tamaño, extensión y contenido antes de llegar a D2."""
    if (request.content_length or 0) > MAX_CARGA_BYTES:
        abort(422, "el archivo supera el límite de 2 GB")
    request.max_content_length = MAX_CARGA_BYTES + 1024**2
    pfc = current_app.extensions["pfc"]
    fila = pfc["procesamientos"].obtener(id_procesamiento)
    if fila is None:
        abort(404)
    if fila["estado"] != "EN_ESPERA":
        abort(409, "el procesamiento no está esperando archivos")
    archivo = request.files.get("archivo")
    fuente = request.form.get("fuente")
    if archivo is None or fuente not in FUENTES:
        abort(400, "se requieren archivo y fuente válidos")
    nombre = secure_filename(archivo.filename or "")
    try:
        comprobar_archivo(nombre, archivo.stream)
    except ArchivoRechazadoError as error:
        abort(415, str(error))
    registro = pfc["carga_manual"](fuente, nombre, archivo.stream, session["id_usuario"])
    pfc["procesamientos"].reanudar(id_procesamiento)
    return jsonify(sha256=registro.sha256, bytes=registro.bytes, ruta=Path(nombre).name), 201

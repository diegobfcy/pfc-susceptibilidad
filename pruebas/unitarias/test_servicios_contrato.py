"""S1 con dobles: contrato de los endpoints nuevos (particiones de equivalencia)."""

from __future__ import annotations

import datetime as dt
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pfc_datos.repositorios import Usuario
from pfc_servicios import crear_app
from pfc_servicios.seguridad.claves import generar_hash

from pruebas.conftest import ProcesamientosMemoria, UsuariosMemoria

CLAVE = "Clave-Segura-2026"
VENTANA = {"fecha_desde": "2017-03-01", "fecha_hasta": "2017-03-31"}


class Resultados:
    def periodo_disponible(self, periodo: dt.date) -> bool:
        return periodo == dt.date(2017, 3, 1)

    def consulta_punto(self, periodo: dt.date, lat: float, lon: float) -> dict[str, Any] | None:
        return {"id_celda": 1, "nivel": 2, "periodo": periodo} if lat == -7 else None

    def periodos(self) -> list[str]:
        return ["2017-03"]

    def ambitos(self) -> dict[str, Any]:
        return {
            "departamentos": [{"id": "24", "nombre": "Tumbes", "celdas": 4624}],
            "provincias": [],
        }

    def limites(self) -> dict[str, Any]:
        return {"type": "FeatureCollection", "features": []}

    def indicadores(self) -> dict[str, Any]:
        return {"metricas": [], "deriva": [], "procesamientos": [], "distribucion_niveles": []}

    def bitacora(self, desde: Any, hasta: Any, tipo: Any) -> list[dict[str, Any]]:
        return [{"id_evento": 1, "ocurrido_en": dt.datetime(2026, 11, 6), "tipo": tipo or "ERROR"}]


class Teselas:
    def tesela(self, capa: str, periodo: dt.date, z: int, x: int, y: int, **f: Any) -> bytes:
        return b"" if z == 12 else b"mvt"


@pytest.fixture
def entorno(tmp_path: Path) -> Any:
    artefacto = tmp_path / "m.ubj"
    artefacto.write_bytes(b"modelo")
    sano = hashlib.sha256(b"modelo").hexdigest()
    versiones = {
        1: {"estado": "CANDIDATA", "ruta_artefacto": str(artefacto), "sha256": sano},
        2: {"estado": "RECHAZADA", "ruta_artefacto": str(artefacto), "sha256": sano},
        3: {"estado": "APROBADA", "ruta_artefacto": str(artefacto), "sha256": "0" * 64},
        4: {"estado": "APROBADA", "ruta_artefacto": str(tmp_path / "no"), "sha256": sano},
    }
    usuarios = UsuariosMemoria(
        [
            Usuario(i, f"{r}@p.pe", r, generar_hash(CLAVE), True, 0, None)
            for i, r in enumerate(("INVESTIGADOR", "ESPECIALISTA", "ASESOR"), 1)
        ]
    )
    procesamientos = ProcesamientosMemoria()
    app = crear_app(
        {
            "usuarios": usuarios,
            "procesamientos": procesamientos,
            "versiones": SimpleNamespace(obtener=versiones.get),
            "resultados": Resultados(),
            "teselas": Teselas(),
            "hay_datos_verificados": lambda d, h: d.year < 2026,
            "carga_manual": lambda f, n, s, u: SimpleNamespace(sha256="a" * 64, bytes=3),
            "comprobar_bd": lambda: True,
        }
    )
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    return SimpleNamespace(c=app.test_client(), procesamientos=procesamientos)


def _csrf(c: Any) -> dict[str, str]:
    return {"X-CSRFToken": c.get("/api/sesion/csrf").get_json()["csrf"]}


def _entrar(c: Any, rol: str) -> None:
    datos = {"correo": f"{rol}@p.pe", "clave": CLAVE}
    assert c.post("/api/auth/login", json=datos, headers=_csrf(c)).status_code == 204


def test_cp11_version_y_huella(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "INVESTIGADOR")

    def pedir(version: Any) -> int:
        cuerpo = {**VENTANA, "id_modelo_version": version}
        return c.post("/api/inferencias", json=cuerpo, headers=_csrf(c)).status_code

    assert [pedir(v) for v in (2, 3, 4, 99)] == [422, 422, 422, 422]
    assert [pedir(v) for v in ("1", 0, -1, True)] == [400, 400, 400, 400]
    assert pedir(1) == 202


def test_cp15_segunda_solicitud_recibe_409(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "INVESTIGADOR")
    cuerpo = {**VENTANA, "id_modelo_version": 1}
    primero = c.post("/api/inferencias", json=cuerpo, headers=_csrf(c))
    assert primero.status_code == 202
    assert c.post("/api/inferencias", json=cuerpo, headers=_csrf(c)).status_code == 409
    identificador = primero.get_json()["id_procesamiento"]
    assert c.get(f"/api/inferencias/{identificador}").get_json()["estado"] == "PENDIENTE"
    assert (
        c.post(f"/api/procesamientos/{identificador}/cancelar", headers=_csrf(c)).status_code
        == 204
    )
    assert (
        c.post(f"/api/procesamientos/{identificador}/cancelar", headers=_csrf(c)).status_code
        == 409
    )
    assert c.post("/api/procesamientos/999/cancelar", headers=_csrf(c)).status_code == 404


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"fecha_desde": "2017-03-31", "fecha_hasta": "2017-03-01", "id_modelo_version": 1},
        {"fecha_desde": "1999-12-31", "fecha_hasta": "2017-03-01", "id_modelo_version": 1},
        {"fecha_desde": "marzo", "fecha_hasta": "2017-03-01", "id_modelo_version": 1},
        {**VENTANA, "id_modelo_version": 1, "extra": 1},
    ],
)
def test_inferencia_rechaza_ventanas_invalidas(entorno: Any, cuerpo: dict[str, Any]) -> None:
    _entrar(entorno.c, "INVESTIGADOR")
    assert (
        entorno.c.post("/api/inferencias", json=cuerpo, headers=_csrf(entorno.c)).status_code
        == 400
    )


def test_entrenamiento_sin_datos_422(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "INVESTIGADOR")
    sin = {"fecha_desde": "2026-01-01", "fecha_hasta": "2026-02-01"}
    assert c.post("/api/entrenamientos", json=sin, headers=_csrf(c)).status_code == 422
    assert c.post("/api/entrenamientos", json=VENTANA, headers=_csrf(c)).status_code == 202


def test_cp04_carga_manual_por_estado_y_contenido(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "INVESTIGADOR")
    identificador = entorno.procesamientos.crear(
        1, "INGESTA", dt.date(2017, 1, 1), dt.date(2017, 2, 1)
    )
    ruta = f"/api/ingestas/{identificador}/archivos"

    def subir(nombre: str, datos: bytes, fuente: str = "era5_land", **k: Any) -> int:
        form = {"fuente": fuente, "archivo": (io.BytesIO(datos), nombre)}
        return c.post(
            ruta, data=form, content_type="multipart/form-data", headers=_csrf(c), **k
        ).status_code

    assert subir("a.nc", b"CDF\x01") == 409  # aún no está en espera
    entorno.procesamientos.filas[identificador]["estado"] = "EN_ESPERA"
    assert subir("a.exe", b"MZ") == 415
    assert subir("falso.nc", b"MZ") == 415
    assert subir("a.nc", b"CDF\x01", fuente="otra") == 400
    assert c.post("/api/ingestas/999/archivos", headers=_csrf(c)).status_code == 404
    grande = c.post(ruta, headers=_csrf(c), environ_overrides={"CONTENT_LENGTH": str(3 * 1024**3)})
    assert grande.status_code == 422
    assert subir("a.nc", b"CDF\x01") == 201
    assert entorno.procesamientos.filas[identificador]["estado"] == "PENDIENTE"  # reanudación


def test_mapas_tesela_y_periodo(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "ESPECIALISTA")
    base = "/api/mapas/susceptibilidad"
    r = c.get(f"{base}/2017-03/7/36/66.pbf")
    assert r.status_code == 200 and r.mimetype == "application/vnd.mapbox-vector-tile"
    assert c.get(f"{base}/2017-03/12/0/0.pbf").status_code == 204  # dentro del periodo, sin celdas
    assert c.get(f"{base}/2018-01/7/36/66.pbf").status_code == 404  # periodo sin procesar
    assert c.get(f"{base}/2017-13/7/36/66.pbf").status_code == 400
    assert c.get(f"{base}/2017-03/7/999/66.pbf").status_code == 404
    assert c.get("/api/mapas/otra/2017-03/7/36/66.pbf").status_code == 404
    assert c.get(f"{base}/2017-03/7/36/66.pbf?provincia=abc").status_code == 400
    assert c.get(f"{base}/2017-03/7/36/66.pbf?departamento=1").status_code == 400


def test_consulta_punto_y_catalogos(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "ESPECIALISTA")
    punto = {"periodo": "2017-03", "lat": -7, "lon": -79}
    assert c.get("/api/consulta-punto", query_string=punto).get_json()["id_celda"] == 1
    assert c.get("/api/consulta-punto", query_string={**punto, "lat": -8}).status_code == 404
    assert c.get("/api/consulta-punto", query_string={**punto, "lat": 99}).status_code == 400
    assert c.get("/api/consulta-punto", query_string={**punto, "lon": "nan"}).status_code == 400
    assert c.get("/api/consulta-punto", query_string={**punto, "periodo": "x"}).status_code == 400
    assert c.get("/api/periodos").get_json()["periodos"] == ["2017-03"]
    assert c.get("/api/ambitos").status_code == 200
    assert c.get("/api/capas/limites").status_code == 200


def test_cp19_bitacora_y_cp18_indicadores(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "ASESOR")
    assert c.get("/api/indicadores").status_code == 200
    assert c.get("/api/bitacora?tipo=ERROR").get_json()["eventos"][0]["tipo"] == "ERROR"
    assert c.get("/api/bitacora?tipo=OTRO").status_code == 400
    assert c.get("/api/bitacora?desde=ayer").status_code == 400
    assert c.get("/api/mapas/susceptibilidad/2017-03/7/36/66.pbf").status_code == 403
    assert "no-store" in c.get("/api/indicadores").headers["Cache-Control"]


def test_sesion_y_cierre(entorno: Any) -> None:
    c = entorno.c
    assert c.get("/api/sesion").status_code == 401
    _entrar(c, "ASESOR")
    assert c.get("/api/sesion").get_json()["rol"] == "ASESOR"
    assert c.delete("/api/sesion", headers=_csrf(c)).status_code == 204
    assert c.get("/api/sesion").status_code == 401


def test_rf01_zona_de_la_inferencia(entorno: Any) -> None:
    """RF-01 / CU-01 paso 2: zona = un departamento de la macrorregión o la macrorregión."""
    c = entorno.c
    _entrar(c, "INVESTIGADOR")

    def pedir(departamento: Any) -> Any:
        cuerpo = {**VENTANA, "id_modelo_version": 1, "departamento": departamento}
        return c.post("/api/inferencias", json=cuerpo, headers=_csrf(c))

    assert [pedir(d).status_code for d in ("99", "16")] == [422, 422]  # fuera de la macrorregión
    assert [pedir(d).status_code for d in ("", "024", 24)] == [400, 400, 400]
    r = pedir("24")
    assert r.status_code == 202
    assert entorno.procesamientos.obtener(r.get_json()["id_procesamiento"])["ubigeo_dep"] == "24"
    cuerpo = {**VENTANA, "tipo": "INGESTA", "departamento": "24"}  # ingesta: macrorregión
    assert c.post("/api/ingestas", json=cuerpo, headers=_csrf(c)).status_code == 400


def test_iu06_procesamiento_activo(entorno: Any) -> None:
    c = entorno.c
    _entrar(c, "INVESTIGADOR")
    assert c.get("/api/procesamientos/activo").status_code == 204
    cuerpo = {**VENTANA, "id_modelo_version": 1}
    creado = c.post("/api/inferencias", json=cuerpo, headers=_csrf(c)).get_json()
    activo = c.get("/api/procesamientos/activo")
    assert activo.status_code == 200
    assert activo.get_json()["id_procesamiento"] == creado["id_procesamiento"]
    _entrar(c, "ESPECIALISTA")
    assert c.get("/api/procesamientos/activo").status_code == 403

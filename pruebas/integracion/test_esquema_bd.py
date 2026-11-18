"""Integración con PostgreSQL/PostGIS: esquema, restricciones y repositorios de D1."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion
URL = os.environ.get("PFC_BD_URL")


@pytest.fixture(scope="module")
def motor() -> Any:
    if not URL:
        pytest.skip("PFC_BD_URL no definida")
    from pfc_datos.bd import crear_motor

    m = crear_motor(URL)
    with m.begin() as c:
        c.execute(text("""INSERT INTO sistema.usuario (id_rol, nombre, correo, hash_clave)
            VALUES (1, 'Prueba', 'prueba@ucsm.edu.pe', 'x') ON CONFLICT (correo) DO NOTHING"""))
    return m


def test_esquemas_instalados(motor: Any) -> None:
    with motor.connect() as c:
        esquemas = set(
            c.execute(text("SELECT schema_name FROM information_schema.schemata")).scalars()
        )
    assert {"sistema", "ref", "datos", "modelo", "resultado"} <= esquemas


def test_procesamiento_y_cola(motor: Any) -> None:
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD

    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    repo = ProcesamientosBD(motor)
    nuevo = repo.crear(usuario.id_usuario, "INGESTA", dt.date(2017, 1, 1), dt.date(2017, 12, 31))
    assert repo.obtener(nuevo)["estado"] == "PENDIENTE"
    assert repo.cancelar(nuevo)


def test_bitacora_es_de_solo_insercion(motor: Any) -> None:
    from pfc_datos.bitacora import BitacoraBD

    BitacoraBD(motor).registrar("INFORMATIVO", "E1", "prueba", n=1)
    for sql in ("UPDATE sistema.bitacora SET tipo = 'ERROR'", "DELETE FROM sistema.bitacora"):
        with pytest.raises(Exception, match="solo inserción"), motor.begin() as c:
            c.execute(text(sql))


def test_restriccion_de_rango_tsm(motor: Any) -> None:
    with pytest.raises(Exception, match="check"), motor.begin() as c:
        c.execute(text("INSERT INTO datos.tsm_mensual VALUES ('2017-03-01', 55, 3.1, NULL)"))


def test_particion_anual_de_resultados(motor: Any) -> None:
    with motor.connect() as c:
        n = c.execute(text("""SELECT count(*) FROM pg_inherits
            WHERE inhparent = 'resultado.susceptibilidad'::regclass""")).scalar_one()
    assert n == 27


class _EtapasVacias:
    def obtener(self, t: Any) -> dict[str, int]:
        return {"ersst_v5": 1}

    def verificar(self, t: Any) -> dict[str, Any]:
        return {}


def test_worker_toma_y_cierra_trabajo(motor: Any) -> None:
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD
    from pfc_etl.orquestador.cola import atender

    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    repo = ProcesamientosBD(motor)
    nuevo = repo.crear(usuario.id_usuario, "INGESTA", dt.date(2018, 1, 1), dt.date(2018, 12, 31))
    atender(motor, _EtapasVacias(), BitacoraBD(motor), una_vez=True)
    assert repo.obtener(nuevo)["estado"] == "COMPLETADO"


def test_worker_marca_fallido_un_error_no_previsto(motor: Any) -> None:
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD
    from pfc_etl.orquestador.cola import atender

    class _Rota(_EtapasVacias):
        def obtener(self, t: Any) -> dict[str, int]:
            raise KeyError("columna")

    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    repo = ProcesamientosBD(motor)
    nuevo = repo.crear(usuario.id_usuario, "INGESTA", dt.date(2019, 1, 1), dt.date(2019, 12, 31))
    with pytest.raises(KeyError):
        atender(motor, _Rota(), BitacoraBD(motor), una_vez=True)
    assert repo.obtener(nuevo)["estado"] == "FALLIDO"

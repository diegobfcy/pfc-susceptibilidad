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
        esquemas = set(c.execute(text("SELECT schema_name FROM information_schema.schemata")).scalars())
    assert {"sistema", "ref", "datos", "modelo", "resultado"} <= esquemas


def test_procesamiento_y_cola(motor: Any) -> None:
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD

    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    repo = ProcesamientosBD(motor)
    nuevo = repo.crear(usuario.id_usuario, "INGESTA", dt.date(2017, 1, 1), dt.date(2017, 12, 31))
    assert repo.obtener(nuevo)["estado"] == "PENDIENTE"


def test_bitacora_es_de_solo_insercion(motor: Any) -> None:
    from pfc_datos.bitacora import BitacoraBD

    BitacoraBD(motor).registrar("INFORMATIVO", "E1", "prueba", n=1)
    with pytest.raises(Exception, match="solo inserción"), motor.begin() as c:
        c.execute(text("DELETE FROM sistema.bitacora"))


def test_restriccion_de_rango_tsm(motor: Any) -> None:
    with pytest.raises(Exception, match="check"), motor.begin() as c:
        c.execute(text("INSERT INTO datos.tsm_mensual VALUES ('2017-03-01', 55, 3.1, NULL)"))


def test_particion_anual_de_resultados(motor: Any) -> None:
    with motor.connect() as c:
        n = c.execute(text("""SELECT count(*) FROM pg_inherits
            WHERE inhparent = 'resultado.susceptibilidad'::regclass""")).scalar_one()
    assert n == 27

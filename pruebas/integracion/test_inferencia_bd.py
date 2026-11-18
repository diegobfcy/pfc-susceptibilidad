"""Integración de M2 con PostGIS: CP-08, CP-11, CP-13, cancelación y reversión del lote."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integracion
URL = os.environ.get("PFC_BD_URL")
VARIABLES = ["a", "b"]
PERIODOS = pd.date_range("2019-01-01", periods=3, freq="MS")


class Lector:
    def __init__(self, filas_por_mes: int = 20) -> None:
        n = filas_por_mes
        self.tabla = pd.concat(
            [
                pd.DataFrame(
                    {
                        "id_celda": np.arange(n),
                        "periodo": p,
                        "a": np.linspace(0, 1, n),
                        "b": np.linspace(1, 0, n),
                        "precip_mes_mm": 10.04,
                        "precip_max3d_mm": 3.0,
                        "precip_ant90_mm": 30.0,
                    }
                )
                for p in PERIODOS
            ]
        )

    def leer(self, anios: range, columnas: list[str] | None = None) -> pd.DataFrame:
        return self.tabla[self.tabla["periodo"].dt.year.isin(anios)]


@pytest.fixture(scope="module")
def motor() -> Any:
    if not URL:
        pytest.skip("PFC_BD_URL no definida")
    from pfc_datos.bd import crear_motor

    m = crear_motor(URL)
    with m.begin() as c:
        c.execute(text("""INSERT INTO sistema.usuario (id_rol, nombre, correo, hash_clave)
            VALUES (1, 'Prueba', 'prueba@ucsm.edu.pe', 'x') ON CONFLICT (correo) DO NOTHING"""))
        c.execute(text("""UPDATE sistema.procesamiento SET estado = 'CANCELADO'
            WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')"""))
        c.execute(text("""INSERT INTO sistema.umbral_version (limites, vigente)
            SELECT '{0.25,0.5,0.75}', true
            WHERE NOT EXISTS (SELECT 1 FROM sistema.umbral_version WHERE vigente)"""))
        c.execute(text("TRUNCATE resultado.susceptibilidad"))
    return m


@pytest.fixture(scope="module")
def modelos(tmp_path_factory: Any) -> Any:
    import xgboost as xgb
    from pfc_datos.modelos import EstadoVersion, RepositorioModelos

    x = pd.DataFrame({"a": np.linspace(0, 1, 200), "b": np.linspace(1, 0, 200)})
    y = (x["a"] > 0.5).astype(int)
    clasificador = xgb.XGBClassifier(n_estimators=4, max_depth=2, device="cpu").fit(x, y)
    repo = RepositorioModelos(tmp_path_factory.mktemp("d2"))
    repo.guardar(clasificador, "XGBOOST", "it", EstadoVersion.CANDIDATA)
    return repo


@pytest.fixture
def trabajo(motor: Any, modelos: Any) -> Any:
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD

    with motor.begin() as c:
        version = c.execute(text("""INSERT INTO modelo.modelo_version
              (algoritmo, version, estado, ruta_artefacto, sha256, hiperparametros)
              VALUES ('XGBOOST', 'it', 'CANDIDATA', 'x', repeat('0', 64), '{}')
              ON CONFLICT (algoritmo, version) DO UPDATE SET estado = 'CANDIDATA'
              RETURNING id_modelo_version""")).scalar_one()
    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    repo = ProcesamientosBD(motor)
    nuevo = repo.crear(
        usuario.id_usuario, "INFERENCIA", dt.date(2019, 1, 1), dt.date(2019, 3, 31), version
    )
    yield nuevo
    repo.cancelar(nuevo)


def _atender(motor: Any, modelos: Any, lector: Any = None) -> bool:
    from pfc_datos.bitacora import BitacoraBD
    from pfc_predictiva.inferencia.trabajador import atender_una

    return atender_una(motor, lector or Lector(), modelos, BitacoraBD(motor), VARIABLES)


def _estado(motor: Any, identificador: int) -> str:
    from pfc_datos.repositorios import ProcesamientosBD

    return ProcesamientosBD(motor).obtener(identificador)["estado"]


def _filas(motor: Any, identificador: int | None = None) -> int:
    sql = "SELECT count(*) FROM resultado.susceptibilidad"
    with motor.connect() as c:
        if identificador is None:
            return c.execute(text(sql)).scalar_one()
        return c.execute(
            text(sql + " WHERE id_procesamiento = :i"), {"i": identificador}
        ).scalar_one()


def test_cp13_persiste_y_clasifica_igual_que_sql(motor: Any, modelos: Any, trabajo: int) -> None:
    assert _atender(motor, modelos)
    assert _estado(motor, trabajo) == "COMPLETADO"
    assert _filas(motor, trabajo) == 60
    with motor.connect() as c:
        diferentes = c.execute(
            text("""SELECT count(*) FROM resultado.susceptibilidad WHERE id_procesamiento = :i
                AND nivel <> CASE WHEN probabilidad < 0.25 THEN 1 WHEN probabilidad < 0.5 THEN 2
                                  WHEN probabilidad < 0.75 THEN 3 ELSE 4 END"""),
            {"i": trabajo},
        ).scalar_one()
        precipitacion = c.execute(
            text("SELECT DISTINCT precip_mes_mm::float8 FROM resultado.susceptibilidad")
        ).scalar_one()
    assert diferentes == 0 and precipitacion == pytest.approx(10.0)


def test_cp13_repetir_la_ventana_reemplaza_sin_duplicar(
    motor: Any, modelos: Any, trabajo: int
) -> None:
    assert _atender(motor, modelos)
    assert _estado(motor, trabajo) == "COMPLETADO"
    assert _filas(motor) == 60 and _filas(motor, trabajo) == 60


def test_cp11_artefacto_alterado_no_escribe(motor: Any, modelos: Any, trabajo: int) -> None:
    ruta = modelos._raiz / "xgboost_vit.ubj"
    original = ruta.read_bytes()
    ruta.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    try:
        assert _atender(motor, modelos)
    finally:
        ruta.write_bytes(original)
    assert _estado(motor, trabajo) == "FALLIDO"
    assert _filas(motor, trabajo) == 0
    with motor.connect() as c:
        evento = c.execute(
            text("""SELECT count(*) FROM sistema.bitacora
                    WHERE tipo = 'ERROR' AND id_procesamiento = :i"""),
            {"i": trabajo},
        ).scalar_one()
    assert evento == 1


def test_cancelacion_antes_del_lote_no_escribe(motor: Any, modelos: Any, trabajo: int) -> None:
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.repositorios import ProcesamientosBD
    from pfc_predictiva.inferencia import trabajador

    original = trabajador._comprobar_cancelacion

    def cancelar_y_comprobar(m: Any, i: int) -> None:
        ProcesamientosBD(m).cancelar(i)
        original(m, i)

    trabajador._comprobar_cancelacion = cancelar_y_comprobar
    try:
        trabajador.atender_una(motor, Lector(), modelos, BitacoraBD(motor), VARIABLES)
    finally:
        trabajador._comprobar_cancelacion = original
    assert _estado(motor, trabajo) == "CANCELADO"
    assert _filas(motor, trabajo) == 0


def test_error_de_copy_revierte_el_lote(motor: Any, modelos: Any, trabajo: int) -> None:
    lector = Lector()
    lector.tabla.loc[lector.tabla.index[5], "precip_mes_mm"] = -5.0  # viola el CHECK de D1
    antes = _filas(motor)
    with pytest.raises(Exception, match="check"):
        _atender(motor, modelos, lector)
    assert _estado(motor, trabajo) == "FALLIDO"
    assert _filas(motor, trabajo) == 0 and _filas(motor) == antes  # lo anterior sigue intacto


def test_cp08_error_de_fuente_queda_en_el_historial(motor: Any) -> None:
    """CU-01, flujo 4a y escenario 2: la falla de una fuente se registra en el historial y el
    procesamiento queda en espera de la carga manual. La inmutabilidad (RF-13) se prueba aparte."""
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.repositorios import ProcesamientosBD, UsuariosBD
    from pfc_etl.orquestador.cola import atender
    from pfc_etl.orquestador.orquestador import FuenteNoDisponibleError

    class SinFuente:
        def obtener(self, t: Any) -> dict[str, int]:
            raise FuenteNoDisponibleError("era5_land")

    repo = ProcesamientosBD(motor)
    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")
    nuevo = repo.crear(usuario.id_usuario, "INGESTA", dt.date(2023, 1, 1), dt.date(2023, 12, 31))
    atender(motor, SinFuente(), BitacoraBD(motor), una_vez=True)
    assert repo.obtener(nuevo)["estado"] == "EN_ESPERA"
    with motor.connect() as c:
        tipo, descripcion = c.execute(
            text("""SELECT tipo, descripcion FROM sistema.bitacora
                    WHERE id_procesamiento = :i ORDER BY id_evento DESC LIMIT 1"""),
            {"i": nuevo},
        ).one()
    assert tipo == "ERROR" and descripcion.startswith("era5_land: no respondió")
    motivo = repo.obtener(nuevo)["resumen"]["motivo"]  # persistido en D1 para IU-08
    assert (motivo["tipo"], motivo["fuente"]) == ("FUENTE_NO_DISPONIBLE", "era5_land")
    repo.reanudar(nuevo)
    assert repo.obtener(nuevo)["estado"] == "PENDIENTE"
    assert repo.cancelar(nuevo)


def test_cp15_concurrencia_real_un_solo_activo(motor: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from pfc_datos.repositorios import ProcesamientoActivoError, ProcesamientosBD, UsuariosBD

    repo = ProcesamientosBD(motor)
    usuario = UsuariosBD(motor).por_correo("prueba@ucsm.edu.pe")

    def enviar(_: int) -> int | None:
        try:
            return repo.crear(
                usuario.id_usuario, "INGESTA", dt.date(2020, 1, 1), dt.date(2020, 2, 1)
            )
        except ProcesamientoActivoError:
            return None

    with ThreadPoolExecutor(20) as hilos:
        resultados = list(hilos.map(enviar, range(20)))
    creados = [r for r in resultados if r is not None]
    assert len(creados) == 1
    assert repo.cancelar(creados[0])
    assert not repo.cancelar(creados[0])

"""S3. Teselas vectoriales (MVT) generadas por PostGIS con ST_AsMVT (RF-08 a RF-10)."""

from __future__ import annotations

import datetime as dt
from typing import Final

from sqlalchemy import text
from sqlalchemy.engine import Engine

CAPAS: Final = frozenset({"susceptibilidad", "precipitacion", "pendiente", "tsm", "inventario"})
# Capas de CU-04 (IU-13). Susceptibilidad y precipitación salen del resultado del mes; la
# pendiente, de datos.terreno_celda; la anomalía de TSM del mes (índice Niño 1+2) se pinta por
# departamento, y el inventario muestra los eventos hasta el fin del mes, con los del mes marcados.
SQL_PENDIENTE: Final = """
    WITH env AS (SELECT ST_TileEnvelope(:z, :x, :y) AS e),
    capa AS (
        SELECT t.id_celda, t.pend_media_g::float8 AS pend_media_g,
               ST_AsMVTGeom(c.geom_3857, env.e, 4096, 16, true) AS geom
        FROM env
        JOIN ref.celda_analisis c ON c.geom_3857 && env.e
        JOIN datos.terreno_celda t ON t.id_celda = c.id_celda
        WHERE (CAST(:provincia AS text) IS NULL OR c.ubigeo_prov = CAST(:provincia AS text))
          AND (CAST(:departamento AS text) IS NULL
               OR left(c.ubigeo_prov, 2) = CAST(:departamento AS text)))
    SELECT ST_AsMVT(capa, :capa, 4096, 'geom') FROM capa WHERE geom IS NOT NULL"""
SQL_TSM: Final = """
    WITH env AS (SELECT ST_TileEnvelope(:z, :x, :y) AS e),
    capa AS (
        SELECT d.ubigeo_dep, d.nombre, m.tsm_c::float8 AS tsm_c, m.anom_tsm::float8 AS anom_tsm,
               ST_AsMVTGeom(ST_Transform(d.geom, 3857), env.e, 4096, 64, true) AS geom
        FROM env
        JOIN ref.departamento d ON ST_Transform(d.geom, 3857) && env.e
        JOIN datos.tsm_mensual m ON m.periodo = :periodo
        WHERE (CAST(:departamento AS text) IS NULL OR d.ubigeo_dep = CAST(:departamento AS text))
          AND (CAST(:provincia AS text) IS NULL
               OR d.ubigeo_dep = left(CAST(:provincia AS text), 2)))
    SELECT ST_AsMVT(capa, :capa, 4096, 'geom') FROM capa WHERE geom IS NOT NULL"""
SQL_INVENTARIO: Final = """
    WITH env AS (SELECT ST_TileEnvelope(:z, :x, :y) AS e),
    capa AS (
        SELECT s.codigo_origen, s.id_celda, to_char(s.fecha_evento, 'YYYY-MM-DD') AS fecha,
               s.precision_fecha,
               (date_trunc('month', s.fecha_evento) = :periodo) AS del_periodo,
               ST_AsMVTGeom(ST_Transform(s.geom, 3857), env.e, 4096, 16, true) AS geom
        FROM env
        JOIN datos.deslizamiento s ON ST_Transform(s.geom, 3857) && env.e
        JOIN ref.celda_analisis c ON c.id_celda = s.id_celda
        WHERE s.fecha_evento < (CAST(:periodo AS date) + interval '1 month')
          AND (CAST(:provincia AS text) IS NULL OR c.ubigeo_prov = CAST(:provincia AS text))
          AND (CAST(:departamento AS text) IS NULL
               OR left(c.ubigeo_prov, 2) = CAST(:departamento AS text)))
    SELECT ST_AsMVT(capa, :capa, 4096, 'geom') FROM capa WHERE geom IS NOT NULL"""
SQL_TESELA: Final = """
    WITH env AS (SELECT ST_TileEnvelope(:z, :x, :y) AS e),
    capa AS (
        SELECT s.id_celda, s.nivel, s.probabilidad::float8 AS probabilidad,
               s.precip_mes_mm::float8 AS precip_mes_mm,
               ST_AsMVTGeom(c.geom_3857, env.e, 4096, 16, true) AS geom
        FROM env
        JOIN ref.celda_analisis c ON c.geom_3857 && env.e
        JOIN resultado.susceptibilidad s ON s.id_celda = c.id_celda AND s.periodo = :periodo
        WHERE (CAST(:provincia AS text) IS NULL OR c.ubigeo_prov = CAST(:provincia AS text))
          AND (CAST(:departamento AS text) IS NULL
               OR left(c.ubigeo_prov, 2) = CAST(:departamento AS text)))
    SELECT ST_AsMVT(capa, :capa, 4096, 'geom') FROM capa WHERE geom IS NOT NULL"""


SQL_POR_CAPA: Final = {"pendiente": SQL_PENDIENTE, "tsm": SQL_TSM, "inventario": SQL_INVENTARIO}


def tesela_valida(z: int, x: int, y: int) -> bool:
    """True si (z, x, y) es una tesela existente con zoom de 0 a 16."""
    return 0 <= z <= 16 and 0 <= x < 2**z and 0 <= y < 2**z


class TeselasBD:
    """Generador de teselas vectoriales con ST_AsMVT de PostGIS."""

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def tesela(
        self,
        capa: str,
        periodo: dt.date,
        z: int,
        x: int,
        y: int,
        departamento: str | None = None,
        provincia: str | None = None,
    ) -> bytes:
        """Tesela MVT de una capa en un mes, con los filtros de ámbito; vacía si no hay celdas."""
        with self._motor.connect() as c:
            datos = c.execute(
                text(SQL_POR_CAPA.get(capa, SQL_TESELA)),
                {
                    "capa": capa,
                    "periodo": periodo,
                    "z": z,
                    "x": x,
                    "y": y,
                    "departamento": departamento,
                    "provincia": provincia,
                },
            ).scalar_one()
        return bytes(datos) if datos else b""

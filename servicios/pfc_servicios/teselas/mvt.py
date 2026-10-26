"""S3. Teselas vectoriales (MVT) generadas por PostGIS con ST_AsMVT (actividad 3.2)."""

from __future__ import annotations

from typing import Final

SQL_TESELA: Final = """
    WITH env AS (SELECT ST_TileEnvelope(:z, :x, :y) AS e),
    capa AS (
        SELECT s.id_celda, s.nivel, s.probabilidad,
               ST_AsMVTGeom(ST_Transform(c.geom, 3857), env.e) AS geom
        FROM env, resultado.susceptibilidad s
        JOIN ref.celda_analisis c USING (id_celda)
        WHERE s.id_procesamiento = :proc AND s.periodo = :periodo
          AND ST_Transform(c.geom, 3857) && env.e)
    SELECT ST_AsMVT(capa, 'susceptibilidad', 4096, 'geom') FROM capa"""


def tesela_valida(z: int, x: int, y: int) -> bool:
    return 0 <= z <= 16 and 0 <= x < 2**z and 0 <= y < 2**z

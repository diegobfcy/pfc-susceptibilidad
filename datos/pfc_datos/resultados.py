"""D1: consultas de mapas, indicadores e historial con parámetros enlazados (OWASP A03)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from pfc_datos.bd import consultar

SQL_CONSULTA_PUNTO = """
    SELECT c.id_celda, s.nivel, s.probabilidad::float8 AS probabilidad, s.periodo,
           s.precip_mes_mm::float8 AS precip_mes_mm,
           s.precip_max3d_mm::float8 AS precip_max3d_mm,
           s.precip_ant90_mm::float8 AS precip_ant90_mm,
           t.pend_media_g, t.pend_p90_g, m.anom_tsm::float8 AS anom_tsm,
           p.nombre AS provincia, d.nombre AS departamento
    FROM ref.celda_analisis c
    JOIN resultado.susceptibilidad s ON s.id_celda = c.id_celda AND s.periodo = :periodo
    LEFT JOIN datos.terreno_celda t ON t.id_celda = c.id_celda
    LEFT JOIN datos.tsm_mensual m ON m.periodo = s.periodo
    LEFT JOIN ref.provincia p ON p.ubigeo_prov = c.ubigeo_prov
    LEFT JOIN ref.departamento d ON d.ubigeo_dep = left(c.ubigeo_prov, 2)
    WHERE ST_Contains(c.geom, ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), 32717))"""


class ResultadosBD:
    """Consultas de lectura de resultados, ámbitos, bitácora e indicadores sobre D1."""

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def consulta_punto(self, periodo: dt.date, lat: float, lon: float) -> dict[str, Any] | None:
        """Nivel, puntaje y variables de la celda que contiene el punto en un periodo (RF-11), o
        None.
        """
        filas = consultar(self._motor, SQL_CONSULTA_PUNTO, periodo=periodo, lat=lat, lon=lon)
        return filas[0] if filas else None

    def periodos(self) -> list[str]:
        """Periodos con resultados, en formato AAAA-MM y en orden."""
        filas = consultar(
            self._motor,
            """SELECT DISTINCT periodo FROM resultado.susceptibilidad ORDER BY periodo""",
        )
        return [f["periodo"].isoformat()[:7] for f in filas]

    def periodo_disponible(self, periodo: dt.date) -> bool:
        """True si el periodo tiene resultados de susceptibilidad."""
        return bool(
            consultar(
                self._motor,
                "SELECT 1 AS ok FROM resultado.susceptibilidad WHERE periodo = :p LIMIT 1",
                p=periodo,
            )
        )

    def ambitos(self) -> dict[str, Any]:
        """Departamentos y provincias con su caja envolvente, para los filtros (RF-09)."""
        departamentos = consultar(
            self._motor,
            """SELECT d.ubigeo_dep AS id, d.nombre,
                      ST_AsGeoJSON(ST_Envelope(d.geom), 5)::json AS caja,
                      (SELECT count(*) FROM ref.celda_analisis c
                       WHERE left(c.ubigeo_prov, 2) = d.ubigeo_dep) AS celdas
               FROM ref.departamento d ORDER BY d.nombre""",
        )
        provincias = consultar(
            self._motor,
            """SELECT ubigeo_prov AS id, ubigeo_dep AS id_departamento, nombre,
                      ST_AsGeoJSON(ST_Envelope(geom), 5)::json AS caja
               FROM ref.provincia ORDER BY nombre""",
        )
        return {"departamentos": departamentos, "provincias": provincias}

    def limites(self) -> dict[str, Any]:
        """Límites provinciales simplificados como FeatureCollection GeoJSON."""
        filas = consultar(
            self._motor,
            """SELECT ubigeo_prov AS id, nombre,
                      ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.005), 4)::json AS geometria
               FROM ref.provincia""",
        )
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": f["geometria"],
                    "properties": {"id": f["id"], "nombre": f["nombre"]},
                }
                for f in filas
            ],
        }

    def bitacora(
        self,
        desde: dt.date | None,
        hasta: dt.date | None,
        tipo: str | None,
        limite: int = 200,
    ) -> list[dict[str, Any]]:
        """Eventos de la bitácora filtrados por fecha y tipo, del más reciente al más antiguo."""
        return consultar(
            self._motor,
            """SELECT b.id_evento, b.ocurrido_en, b.tipo, b.componente, b.descripcion,
                      b.id_procesamiento, u.correo AS usuario, b.detalle
               FROM sistema.bitacora b LEFT JOIN sistema.usuario u USING (id_usuario)
               WHERE (CAST(:desde AS date) IS NULL OR b.ocurrido_en >= CAST(:desde AS date))
                 AND (CAST(:hasta AS date) IS NULL
                      OR b.ocurrido_en < CAST(:hasta AS date) + 1)
                 AND (CAST(:tipo AS text) IS NULL OR b.tipo = CAST(:tipo AS text))
               ORDER BY b.ocurrido_en DESC, b.id_evento DESC LIMIT :limite""",
            desde=desde,
            hasta=hasta,
            tipo=tipo,
            limite=limite,
        )

    def indicadores(self) -> dict[str, Any]:
        """Métricas por versión, PSI por variable, últimos procesamientos y celdas-mes por nivel
        (RF-12).
        """
        metricas = consultar(
            self._motor,
            """SELECT v.algoritmo, v.version, v.estado, m.conjunto, m.nombre,
                      m.valor::float8 AS valor
               FROM modelo.metrica m JOIN modelo.modelo_version v USING (id_modelo_version)
               ORDER BY v.id_modelo_version, m.conjunto, m.nombre""",
        )
        deriva = consultar(
            self._motor,
            """SELECT variable, psi::float8 AS psi FROM modelo.deriva ORDER BY variable""",
        )
        ultimos = consultar(
            self._motor,
            """SELECT DISTINCT ON (tipo) id_procesamiento, tipo, estado, iniciado_en,
                      finalizado_en, memoria_max_gb::float8 AS memoria_max_gb, tiempos_s, resumen
               FROM sistema.procesamiento WHERE estado = 'COMPLETADO'
               ORDER BY tipo, id_procesamiento DESC""",
        )
        distribucion = consultar(
            self._motor,
            """SELECT nivel, count(*) AS celdas_mes FROM resultado.susceptibilidad
               GROUP BY nivel ORDER BY nivel""",
        )
        return {
            "metricas": metricas,
            "deriva": deriva,
            "procesamientos": ultimos,
            "distribucion_niveles": distribucion,
        }


class VersionesBD:
    """Consultas de las versiones del modelo registradas en modelo.modelo_version."""

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def obtener(self, id_modelo_version: int) -> dict[str, Any] | None:
        """Algoritmo, versión, estado, ruta y huella de una versión, o None si no existe."""
        filas = consultar(
            self._motor,
            """SELECT id_modelo_version, algoritmo, version, estado, ruta_artefacto, sha256
               FROM modelo.modelo_version WHERE id_modelo_version = :id""",
            id=id_modelo_version,
        )
        return filas[0] if filas else None


def registrar_dataset(motor: Engine, datos: dict[str, Any]) -> int:
    """Registra en sistema.dataset un archivo de carga manual y devuelve su identificador."""
    with motor.begin() as c:
        return c.execute(
            text("""INSERT INTO sistema.dataset
                (id_fuente, version_producto, origen, ruta_archivo, sha256, id_usuario)
                SELECT id_fuente, 'carga manual', 'MANUAL', :ruta, :sha256, :id_usuario
                FROM sistema.fuente_dato WHERE codigo = :fuente
                RETURNING id_dataset"""),
            datos,
        ).scalar_one()

"""M2. Worker de inferencia: toma trabajos INFERENCIA de D1, verifica el artefacto, estima y
clasifica por lote anual y escribe los resultados con COPY (RF-03, RF-07)."""

from __future__ import annotations

import datetime as dt
import io
import json
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from pfc_datos.almacen import MatrizParquet
from pfc_datos.memoria import pico_gb, reiniciar_pico
from pfc_datos.modelos import IntegridadArtefactoError, RepositorioModelos
from pfc_datos.protocolos import LectorMatriz, RegistroBitacora
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pfc_predictiva.inferencia.inferencia import clasificar

ESPERA_S = 5
FILAS_POR_ENVIO = 250_000
COLUMNAS_COPY = (
    "id_procesamiento, id_celda, periodo, probabilidad, nivel, "
    "precip_mes_mm, precip_max3d_mm, precip_ant90_mm"
)
SQL_TOMAR = """
    UPDATE sistema.procesamiento SET estado = 'EN_CURSO', iniciado_en = now()
    WHERE id_procesamiento = (
        SELECT id_procesamiento FROM sistema.procesamiento
        WHERE estado = 'PENDIENTE' AND tipo = 'INFERENCIA'
        ORDER BY id_procesamiento FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING id_procesamiento, fecha_desde, fecha_hasta, id_modelo_version, id_umbral_version,
              ubigeo_dep"""
SQL_CELDAS_ZONA = """SELECT id_celda FROM ref.celda_analisis
                     WHERE left(ubigeo_prov, 2) = :dep ORDER BY id_celda"""


class CanceladoError(Exception):
    """El Equipo Investigador canceló el procesamiento entre dos lotes."""


@dataclass
class ResultadoInferencia:
    """Filas y lotes escritos, segundos por fase y pico de memoria por fase de una inferencia."""

    filas: int = 0
    lotes: int = 0
    tiempos_s: dict[str, float] = field(default_factory=dict)
    memoria_gb: dict[str, float] = field(default_factory=dict)


class Medidor:
    """Acumula el tiempo por fase y el pico de memoria del trabajo al cerrar cada fase."""

    def __init__(self, resultado: ResultadoInferencia) -> None:
        self._r = resultado
        self._fase = ""

    def __call__(self, fase: str) -> Medidor:
        self._fase = fase
        return self

    def __enter__(self) -> None:
        self._t0 = time.perf_counter()

    def __exit__(self, *_: Any) -> None:
        tiempos = self._r.tiempos_s
        tiempos[self._fase] = round(
            tiempos.get(self._fase, 0.0) + time.perf_counter() - self._t0, 1
        )
        self._r.memoria_gb[self._fase] = round(pico_gb(), 2)


def meses(desde: dt.date, hasta: dt.date) -> pd.DatetimeIndex:
    """Primer día de cada mes entre dos fechas, ambas incluidas."""
    return pd.date_range(desde.replace(day=1), hasta.replace(day=1), freq="MS")


def csv_para_copy(id_procesamiento: int, lote: pd.DataFrame) -> str:
    """Convierte un lote a CSV con las columnas de COPY, con 4 decimales en la probabilidad."""
    salida = pd.DataFrame(
        {
            "id_procesamiento": id_procesamiento,
            "id_celda": lote["id_celda"].to_numpy(),
            "periodo": lote["periodo"].dt.strftime("%Y-%m-%d").to_numpy(),
            "probabilidad": lote["probabilidad"].map("{:.4f}".format).to_numpy(),
            "nivel": lote["nivel"].to_numpy(),
            "precip_mes_mm": lote["precip_mes_mm"].round(1).to_numpy(),
            "precip_max3d_mm": lote["precip_max3d_mm"].round(1).to_numpy(),
            "precip_ant90_mm": lote["precip_ant90_mm"].round(1).to_numpy(),
        }
    )
    tampon = io.StringIO()
    salida.to_csv(tampon, index=False, header=False)
    return tampon.getvalue()


def escribir_lote(
    motor: Engine, id_procesamiento: int, lote: pd.DataFrame, ubigeo_dep: str | None = None
) -> None:
    """Una transacción por lote: reemplaza los periodos del lote sin dejar resultados a medias.

    Con una zona (ubigeo_dep) solo se reemplazan las celdas de ese departamento.
    """
    periodos = sorted({p.date() for p in lote["periodo"].drop_duplicates()})
    with motor.begin() as c:
        c.execute(
            text("""DELETE FROM resultado.susceptibilidad s
                    WHERE s.periodo = ANY(CAST(:periodos AS date[]))
                      AND s.id_procesamiento <> :id
                      AND (CAST(:dep AS text) IS NULL OR s.id_celda IN (
                           SELECT id_celda FROM ref.celda_analisis
                           WHERE left(ubigeo_prov, 2) = CAST(:dep AS text)))"""),
            {"periodos": [str(p) for p in periodos], "id": id_procesamiento, "dep": ubigeo_dep},
        )
        cursor = c.connection.cursor()
        with cursor.copy(
            f"COPY resultado.susceptibilidad ({COLUMNAS_COPY}) FROM STDIN (FORMAT csv)"
        ) as copia:
            for inicio in range(0, len(lote), FILAS_POR_ENVIO):
                parte = lote.iloc[inicio : inicio + FILAS_POR_ENVIO]
                copia.write(csv_para_copy(id_procesamiento, parte))


def _comprobar_cancelacion(motor: Engine, id_procesamiento: int) -> None:
    with motor.connect() as c:
        estado = c.execute(
            text("SELECT estado FROM sistema.procesamiento WHERE id_procesamiento = :id"),
            {"id": id_procesamiento},
        ).scalar_one()
    if estado == "CANCELADO":
        raise CanceladoError


def _version_y_limites(motor: Engine, trabajo: dict[str, Any]) -> tuple[str, str, list[float]]:
    with motor.connect() as c:
        modelo = (
            c.execute(
                text("""SELECT algoritmo, version FROM modelo.modelo_version
                        WHERE id_modelo_version = :id"""),
                {"id": trabajo["id_modelo_version"]},
            )
            .mappings()
            .one()
        )
        limites = c.execute(
            text("SELECT limites FROM sistema.umbral_version WHERE id_umbral_version = :id"),
            {"id": trabajo["id_umbral_version"]},
        ).scalar_one()
    return modelo["algoritmo"], modelo["version"], [float(x) for x in limites]


def ejecutar_inferencia(
    motor: Engine,
    lector: LectorMatriz,
    modelos: RepositorioModelos,
    trabajo: dict[str, Any],
    variables: list[str],
) -> ResultadoInferencia:
    """M2: verifica el artefacto y estima, clasifica y escribe cada año de la ventana.

    Comprueba la cancelación antes de cada lote y mide el tiempo y la memoria por fase. Lanza
    IntegridadArtefactoError o CanceladoError.
    """
    reiniciar_pico()  # el pico registrado es el de este trabajo (DEF-13)
    resultado = ResultadoInferencia()
    medir = Medidor(resultado)
    id_proc = trabajo["id_procesamiento"]
    algoritmo, version, limites = _version_y_limites(motor, trabajo)
    with medir("verificar_artefacto"):
        modelo, _ = modelos.cargar(algoritmo, version)  # IntegridadArtefactoError si no coincide
    ventana = meses(trabajo["fecha_desde"], trabajo["fecha_hasta"])
    dep = trabajo.get("ubigeo_dep")  # zona de RF-01; None = macrorregión completa
    celdas_zona = None
    if dep:
        with motor.connect() as c:
            celdas_zona = pd.Index(c.execute(text(SQL_CELDAS_ZONA), {"dep": dep}).scalars().all())
    for anio in sorted(set(ventana.year)):
        _comprobar_cancelacion(motor, id_proc)
        with medir("leer_matriz"):
            lote = lector.leer(range(anio, anio + 1), ["id_celda", "periodo", *variables])
            lote = lote[lote["periodo"].isin(ventana)]
            if celdas_zona is not None:
                lote = lote[lote["id_celda"].isin(celdas_zona)]
            lote = lote.reset_index(drop=True)
        with medir("predecir"):
            lote["probabilidad"] = modelo.predict_proba(lote[variables])[:, 1]
        with medir("clasificar"):
            # Se clasifica el valor que se almacena: la base y el nivel nunca se contradicen.
            lote["probabilidad"] = np.round(lote["probabilidad"].astype("float64"), 4)
            lote["nivel"] = clasificar(lote["probabilidad"].to_numpy(), limites)
        with medir("copy"):
            escribir_lote(motor, id_proc, lote, dep)
        resultado.filas += len(lote)
        resultado.lotes += 1
        with motor.begin() as c:
            c.execute(
                text("""UPDATE sistema.procesamiento SET fase = :f
                        WHERE id_procesamiento = :id AND estado = 'EN_CURSO'"""),
                {"f": f"lote {anio}", "id": id_proc},
            )
    with medir("analyze"), motor.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text("ANALYZE resultado.susceptibilidad"))
    return resultado


def cerrar(
    motor: Engine, id_procesamiento: int, estado: str, resultado: ResultadoInferencia
) -> None:
    """Guarda el estado final, los tiempos, el pico de memoria y el resumen del procesamiento.

    No sobrescribe un procesamiento CANCELADO.
    """
    with motor.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento
                    SET estado = :e, fase = NULL, finalizado_en = now(), memoria_max_gb = :m,
                        tiempos_s = CAST(:t AS jsonb), resumen = CAST(:r AS jsonb)
                    WHERE id_procesamiento = :id AND estado <> 'CANCELADO'"""),
            {
                "e": estado,
                "m": max(resultado.memoria_gb.values(), default=0.0),
                "t": json.dumps(resultado.tiempos_s),
                "r": json.dumps(
                    {
                        "filas": resultado.filas,
                        "lotes": resultado.lotes,
                        "memoria_gb": resultado.memoria_gb,
                    }
                ),
                "id": id_procesamiento,
            },
        )


def atender_una(
    motor: Engine,
    lector: LectorMatriz,
    modelos: RepositorioModelos,
    bitacora: RegistroBitacora,
    variables: list[str],
) -> bool:
    """Atiende un trabajo si lo hay; False si la cola está vacía."""
    with motor.begin() as c:
        fila = c.execute(text(SQL_TOMAR)).mappings().first()
    if fila is None:
        return False
    trabajo = dict(fila)
    id_proc = trabajo["id_procesamiento"]
    resultado = ResultadoInferencia()
    try:
        resultado = ejecutar_inferencia(motor, lector, modelos, trabajo, variables)
    except IntegridadArtefactoError as error:
        bitacora.registrar(
            "ERROR", "M2", "artefacto alterado", id_procesamiento=id_proc, ruta=str(error)
        )
        cerrar(motor, id_proc, "FALLIDO", resultado)
    except CanceladoError:
        bitacora.registrar("ADVERTENCIA", "M2", "inferencia cancelada", id_procesamiento=id_proc)
    except Exception as error:
        bitacora.registrar("ERROR", "M2", str(error)[:500], id_procesamiento=id_proc)
        cerrar(motor, id_proc, "FALLIDO", resultado)
        raise
    else:
        bitacora.registrar(
            "INFORMATIVO",
            "M2",
            "inferencia completada",
            id_procesamiento=id_proc,
            filas=resultado.filas,
            segundos=sum(resultado.tiempos_s.values()),
        )
        cerrar(motor, id_proc, "COMPLETADO", resultado)
    return True


def main() -> None:  # pragma: no cover - bucle del proceso; lo prueba el entorno de staging
    """Bucle del worker de inferencia: atiende la cola y espera ESPERA_S segundos si está vacía."""
    from pfc_datos.bd import crear_motor
    from pfc_datos.bitacora import BitacoraBD
    from pfc_datos.config import ruta_d2

    from pfc_predictiva.__main__ import VARIABLES

    motor = crear_motor()
    d2 = ruta_d2()
    lector, modelos, bitacora = MatrizParquet(d2), RepositorioModelos(d2), BitacoraBD(motor)
    while True:
        if not atender_una(motor, lector, modelos, bitacora, VARIABLES):
            time.sleep(ESPERA_S)


if __name__ == "__main__":
    main()

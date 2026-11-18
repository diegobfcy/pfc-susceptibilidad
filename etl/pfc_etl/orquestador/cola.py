"""E1. Bucle del worker: toma trabajos PENDIENTE de sistema.procesamiento (FOR UPDATE SKIP
LOCKED), los ejecuta y persiste su estado final."""

from __future__ import annotations

import json
import time
from typing import Any

from pfc_datos.protocolos import RegistroBitacora
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pfc_etl.orquestador.orquestador import SQL_TOMAR, TIPOS_ETL, Trabajo, ejecutar_trabajo

ESPERA_S = 10


class EtapasConFase:
    """Publica en D1 la fase en curso para el seguimiento de IU-06 (proxy de las etapas)."""

    def __init__(self, motor: Engine, etapas: Any, id_procesamiento: int) -> None:
        self._motor, self._etapas, self._id = motor, etapas, id_procesamiento

    def __getattr__(self, fase: str) -> Any:
        with self._motor.begin() as c:
            c.execute(
                text("UPDATE sistema.procesamiento SET fase = :f WHERE id_procesamiento = :id"),
                {"f": fase, "id": self._id},
            )
        return getattr(self._etapas, fase)


def tomar_trabajo(motor: Engine, tipos: tuple[str, ...] = TIPOS_ETL) -> Trabajo | None:
    """Toma el trabajo PENDIENTE más antiguo de los tipos dados y lo pasa a EN_CURSO.

    Usa FOR UPDATE SKIP LOCKED: dos workers nunca toman el mismo trabajo. Devuelve None si la cola
    está vacía.
    """
    with motor.begin() as c:
        fila = c.execute(text(SQL_TOMAR), {"tipos": list(tipos)}).mappings().first()
    return Trabajo(**fila) if fila else None


def cerrar_trabajo(motor: Engine, trabajo: Trabajo) -> None:
    """Guarda en D1 el estado final, los tiempos, la memoria y el resumen del trabajo.

    No sobrescribe un trabajo CANCELADO; un trabajo EN_ESPERA queda sin fecha de fin para poder
    reanudarse.
    """
    with motor.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento
                    SET estado = CAST(:estado AS varchar), fase = NULL, memoria_max_gb = :mem,
                        tiempos_s = CAST(:tiempos AS jsonb), resumen = CAST(:resumen AS jsonb),
                        finalizado_en = CASE WHEN CAST(:estado AS varchar) = 'EN_ESPERA'
                                        THEN NULL ELSE now() END
                    WHERE id_procesamiento = :id AND estado <> 'CANCELADO'"""),
            {
                "estado": trabajo.estado,
                "mem": trabajo.salida.get("memoria_max_gb"),
                "tiempos": json.dumps(trabajo.tiempos_s),
                "resumen": json.dumps(trabajo.salida, default=str),
                "id": trabajo.id_procesamiento,
            },
        )


def atender(motor: Engine, etapas: Any, bitacora: RegistroBitacora, una_vez: bool = False) -> None:
    """Bucle del worker ETL: atiende la cola y espera ESPERA_S segundos cuando está vacía.

    Con una_vez=True termina al vaciar la cola (uso en pruebas).
    """
    while True:
        trabajo = tomar_trabajo(motor)
        if trabajo is not None:
            _atender_trabajo(motor, trabajo, etapas, bitacora)
        elif una_vez:
            return
        else:
            time.sleep(ESPERA_S)


def _atender_trabajo(
    motor: Engine, trabajo: Trabajo, etapas: Any, bitacora: RegistroBitacora
) -> None:
    try:
        proxy = EtapasConFase(motor, etapas, trabajo.id_procesamiento)
        cerrar_trabajo(motor, ejecutar_trabajo(trabajo, proxy, bitacora))
    except Exception:
        # Un error no previsto no deja el trabajo EN_CURSO: se marca FALLIDO y se propaga.
        trabajo.estado = "FALLIDO"
        cerrar_trabajo(motor, trabajo)
        raise

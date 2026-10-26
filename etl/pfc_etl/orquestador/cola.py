"""E1. Bucle del worker: toma trabajos PENDIENTE de sistema.procesamiento (FOR UPDATE SKIP
LOCKED), los ejecuta y persiste su estado final."""

from __future__ import annotations

import time
from typing import Any

from pfc_datos.protocolos import RegistroBitacora
from sqlalchemy import text
from sqlalchemy.engine import Engine

from pfc_etl.orquestador.orquestador import SQL_TOMAR, Trabajo, ejecutar_trabajo

ESPERA_S = 10


def tomar_trabajo(motor: Engine) -> Trabajo | None:
    with motor.begin() as c:
        fila = c.execute(text(SQL_TOMAR)).mappings().first()
    return Trabajo(**fila) if fila else None


def cerrar_trabajo(motor: Engine, trabajo: Trabajo) -> None:
    with motor.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento
                    SET estado = :estado, finalizado_en = now(), memoria_max_gb = :mem
                    WHERE id_procesamiento = :id"""),
            {
                "estado": trabajo.estado,
                "mem": trabajo.salida.get("memoria_max_gb"),
                "id": trabajo.id_procesamiento,
            },
        )


def atender(motor: Engine, etapas: Any, bitacora: RegistroBitacora, una_vez: bool = False) -> None:
    while True:
        trabajo = tomar_trabajo(motor)
        if trabajo is not None:
            cerrar_trabajo(motor, ejecutar_trabajo(trabajo, etapas, bitacora))
        elif una_vez:
            return
        else:
            time.sleep(ESPERA_S)

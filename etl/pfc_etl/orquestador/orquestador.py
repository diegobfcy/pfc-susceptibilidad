"""E1. Orquestador del procesamiento: toma trabajos de la cola (sistema.procesamiento) y
ejecuta sus fases obtener -> verificar -> transformar, registrando estado y tiempos."""

from __future__ import annotations

import resource
import time
from dataclasses import dataclass, field
from typing import Any

from pfc_datos.protocolos import RegistroBitacora


@dataclass
class Trabajo:
    id_procesamiento: int
    tipo: str
    anio_desde: int
    anio_hasta: int
    estado: str = "PENDIENTE"
    tiempos_s: dict[str, float] = field(default_factory=dict)
    salida: dict[str, Any] = field(default_factory=dict)


class FuenteNoDisponibleError(Exception):
    """La fuente no respondió o el archivo no está; el trabajo pasa a EN_ESPERA (CU-01, 4a)."""


class DatosIncompletosError(Exception):
    """La verificación detectó faltantes en la serie; el trabajo pasa a EN_ESPERA."""


def ejecutar_trabajo(trabajo: Trabajo, etapas: Any, bitacora: RegistroBitacora) -> Trabajo:
    trabajo.estado = "EN_CURSO"
    try:
        if trabajo.tipo == "INGESTA":
            fases = ["obtener", "verificar"]
        elif trabajo.tipo == "ENTRENAMIENTO":
            fases = ["obtener", "verificar", "transformar"]
        elif trabajo.tipo == "INFERENCIA":
            fases = ["transformar"]
        else:
            raise ValueError(f"tipo de trabajo desconocido: {trabajo.tipo}")
        for fase in fases:
            t0 = time.perf_counter()
            if fase == "obtener":
                trabajo.salida["archivos"] = etapas.obtener(trabajo)
            elif fase == "verificar":
                trabajo.salida["verificacion"] = etapas.verificar(trabajo)
            else:
                trabajo.salida["matriz"] = etapas.transformar(trabajo)
            trabajo.tiempos_s[fase] = round(time.perf_counter() - t0, 1)
            bitacora.registrar("INFORMATIVO", "E1", f"fase {fase} completada",
                               id_procesamiento=trabajo.id_procesamiento,
                               segundos=trabajo.tiempos_s[fase])
        trabajo.estado = "COMPLETADO"
    except Exception as error:
        trabajo.estado = "EN_ESPERA"
        bitacora.registrar("ERROR", "E1", str(error), id_procesamiento=trabajo.id_procesamiento)
    trabajo.salida["memoria_max_gb"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2, 2
    )
    return trabajo


SQL_TOMAR = """
    UPDATE sistema.procesamiento SET estado = 'EN_CURSO', iniciado_en = now()
    WHERE id_procesamiento = (
        SELECT id_procesamiento FROM sistema.procesamiento
        WHERE estado = 'PENDIENTE' ORDER BY id_procesamiento
        FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING id_procesamiento, tipo, extract(year FROM fecha_desde)::int AS anio_desde,
              extract(year FROM fecha_hasta)::int AS anio_hasta"""

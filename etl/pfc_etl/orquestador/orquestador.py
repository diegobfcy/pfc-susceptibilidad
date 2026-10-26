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


class TipoTrabajoDesconocidoError(ValueError):
    """El tipo de trabajo no está en el registro de fases."""


# Registro de fases por tipo de trabajo: un tipo nuevo se agrega aquí, sin tocar el bucle (OCP).
FASES_POR_TIPO: dict[str, tuple[str, ...]] = {
    "INGESTA": ("obtener", "verificar"),
    "ENTRENAMIENTO": ("obtener", "verificar", "transformar"),
    "INFERENCIA": ("transformar",),
}
SALIDA_POR_FASE: dict[str, str] = {
    "obtener": "archivos",
    "verificar": "verificacion",
    "transformar": "matriz",
}
# Errores recuperables: el trabajo queda EN_ESPERA y puede reintentarse (CU-01, flujo 4a).
ERRORES_RECUPERABLES = (FuenteNoDisponibleError, DatosIncompletosError, OSError)


def ejecutar_trabajo(trabajo: Trabajo, etapas: Any, bitacora: RegistroBitacora) -> Trabajo:
    """E1: ejecuta en orden las fases registradas para el tipo de trabajo."""
    trabajo.estado = "EN_CURSO"
    try:
        for fase in _fases(trabajo.tipo):
            _ejecutar_fase(trabajo, fase, etapas, bitacora)
        trabajo.estado = "COMPLETADO"
    except ERRORES_RECUPERABLES as error:
        trabajo.estado = "EN_ESPERA"
        bitacora.registrar("ERROR", "E1", str(error), id_procesamiento=trabajo.id_procesamiento)
    except TipoTrabajoDesconocidoError as error:
        trabajo.estado = "FALLIDO"
        bitacora.registrar("ERROR", "E1", str(error), id_procesamiento=trabajo.id_procesamiento)
    trabajo.salida["memoria_max_gb"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024**2, 2
    )
    return trabajo


def _fases(tipo: str) -> tuple[str, ...]:
    if tipo not in FASES_POR_TIPO:
        raise TipoTrabajoDesconocidoError(f"tipo de trabajo desconocido: {tipo}")
    return FASES_POR_TIPO[tipo]


def _ejecutar_fase(trabajo: Trabajo, fase: str, etapas: Any, bitacora: RegistroBitacora) -> None:
    t0 = time.perf_counter()
    trabajo.salida[SALIDA_POR_FASE[fase]] = getattr(etapas, fase)(trabajo)
    trabajo.tiempos_s[fase] = round(time.perf_counter() - t0, 1)
    bitacora.registrar(
        "INFORMATIVO",
        "E1",
        f"fase {fase} completada",
        id_procesamiento=trabajo.id_procesamiento,
        segundos=trabajo.tiempos_s[fase],
    )


SQL_TOMAR = """
    UPDATE sistema.procesamiento SET estado = 'EN_CURSO', iniciado_en = now()
    WHERE id_procesamiento = (
        SELECT id_procesamiento FROM sistema.procesamiento
        WHERE estado = 'PENDIENTE' ORDER BY id_procesamiento
        FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING id_procesamiento, tipo, extract(year FROM fecha_desde)::int AS anio_desde,
              extract(year FROM fecha_hasta)::int AS anio_hasta"""

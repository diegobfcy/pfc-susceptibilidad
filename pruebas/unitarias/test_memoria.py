"""DEF-13: el pico de memoria registrado es el de cada trabajo, no el de la vida del worker."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from pfc_datos.memoria import pico_gb, reiniciar_pico
from pfc_etl.orquestador.orquestador import Trabajo, ejecutar_trabajo


def _ocupar(gb: float) -> None:
    datos = np.ones(int(gb * 1024**3 / 8))  # se escribe toda la memoria: cuenta como residente
    del datos


def test_reiniciar_pico_descarta_el_pico_anterior() -> None:
    if not reiniciar_pico():
        pytest.skip("el sistema no permite reiniciar el pico de memoria")
    _ocupar(0.4)
    assert pico_gb() >= 0.4
    reiniciar_pico()
    assert pico_gb() < 0.3


class _EtapasLivianas:
    def obtener(self, t: Trabajo) -> dict[str, Any]:
        return {}

    def verificar(self, t: Trabajo) -> dict[str, Any]:
        return {}


def test_trabajo_liviano_no_hereda_el_pico_del_anterior(bitacora: Any) -> None:
    if not reiniciar_pico():
        pytest.skip("el sistema no permite reiniciar el pico de memoria")
    _ocupar(0.4)  # trabajo pesado anterior en el mismo proceso
    t = ejecutar_trabajo(Trabajo(1, "INGESTA", 2017, 2017), _EtapasLivianas(), bitacora)
    assert t.estado == "COMPLETADO"
    assert 0 < t.salida["memoria_max_gb"] < 0.3

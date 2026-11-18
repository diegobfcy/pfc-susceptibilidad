"""E1: fases por tipo de trabajo, estado final y registro en la bitácora."""

from __future__ import annotations

from typing import Any

import pytest
from pfc_etl.orquestador.orquestador import (
    DatosIncompletosError,
    FuenteNoDisponibleError,
    Trabajo,
    ejecutar_trabajo,
)


class _Etapas:
    def __init__(self, falla: str | None = None) -> None:
        self.llamadas: list[str] = []
        self._falla = falla

    def _fase(self, nombre: str) -> dict[str, Any]:
        self.llamadas.append(nombre)
        if nombre == self._falla:
            raise FuenteNoDisponibleError("era5_land")
        return {"ok": True}

    def obtener(self, t: Trabajo) -> dict[str, Any]:
        return self._fase("obtener")

    def verificar(self, t: Trabajo) -> dict[str, Any]:
        return self._fase("verificar")

    def transformar(self, t: Trabajo) -> dict[str, Any]:
        return self._fase("transformar")


def test_entrenamiento_recorre_tres_fases(bitacora: Any) -> None:
    etapas = _Etapas()
    t = ejecutar_trabajo(Trabajo(1, "ENTRENAMIENTO", 2017, 2017), etapas, bitacora)
    assert t.estado == "COMPLETADO" and etapas.llamadas == ["obtener", "verificar", "transformar"]
    assert set(t.tiempos_s) == {"obtener", "verificar", "transformar"}


def test_ingesta_no_transforma(bitacora: Any) -> None:
    etapas = _Etapas()
    ejecutar_trabajo(Trabajo(2, "INGESTA", 2017, 2017), etapas, bitacora)
    assert etapas.llamadas == ["obtener", "verificar"]


def test_fuente_no_disponible_pasa_a_espera(bitacora: Any) -> None:
    t = ejecutar_trabajo(Trabajo(3, "ENTRENAMIENTO", 2017, 2017), _Etapas("verificar"), bitacora)
    assert t.estado == "EN_ESPERA" and bitacora.eventos[-1][0] == "ERROR"


def test_la_inferencia_no_la_atiende_el_worker_etl(bitacora: Any) -> None:
    trabajo = ejecutar_trabajo(Trabajo(4, "INFERENCIA", 2017, 2017), _Etapas(), bitacora)
    assert trabajo.estado == "FALLIDO"


def test_tipo_desconocido_falla_sin_ejecutar_fases(bitacora: Any) -> None:
    etapas = _Etapas()
    t = ejecutar_trabajo(Trabajo(5, "OTRO", 2017, 2017), etapas, bitacora)
    assert t.estado == "FALLIDO" and etapas.llamadas == []


def test_error_inesperado_no_se_oculta(bitacora: Any) -> None:
    class _Rota(_Etapas):
        def obtener(self, t: Trabajo) -> dict[str, Any]:
            raise KeyError("columna")

    with pytest.raises(KeyError):
        ejecutar_trabajo(Trabajo(6, "INGESTA", 2017, 2017), _Rota(), bitacora)


def test_cu01_4a_motivo_fuente_no_disponible(bitacora: Any) -> None:
    """IU-08: el trabajo en espera guarda qué fuente falló, para el aviso del panel."""
    t = ejecutar_trabajo(Trabajo(7, "INGESTA", 2017, 2017), _Etapas("obtener"), bitacora)
    assert t.estado == "EN_ESPERA"
    assert t.salida["motivo"]["tipo"] == "FUENTE_NO_DISPONIBLE"
    assert t.salida["motivo"]["fuente"] == "era5_land"
    assert bitacora.eventos[-1][:2] == ("ERROR", "E1") and "era5_land" in bitacora.eventos[-1][2]


def test_cu01_6a_motivo_datos_rechazados(bitacora: Any) -> None:
    """IU-10: el trabajo en espera guarda la fuente, la regla incumplida y el detalle."""

    class _Rechaza(_Etapas):
        def verificar(self, t: Trabajo) -> dict[str, Any]:
            raise DatosIncompletosError(
                "era5_land", "continuidad temporal", "2 periodos faltantes"
            )

    t = ejecutar_trabajo(Trabajo(8, "INGESTA", 2023, 2023), _Rechaza(), bitacora)
    assert t.estado == "EN_ESPERA"
    assert t.salida["motivo"] == {
        "tipo": "DATOS_RECHAZADOS",
        "fuente": "era5_land",
        "regla": "continuidad temporal",
        "detalle": "2 periodos faltantes",
    }
    assert "regla de continuidad temporal incumplida" in bitacora.eventos[-1][2]

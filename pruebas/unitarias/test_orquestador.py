"""E1: fases por tipo de trabajo, estado final y registro en la bitácora."""

from __future__ import annotations

from typing import Any

from pfc_etl.orquestador.orquestador import FuenteNoDisponibleError, Trabajo, ejecutar_trabajo


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

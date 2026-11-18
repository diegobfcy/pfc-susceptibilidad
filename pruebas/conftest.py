"""Dobles de prueba en memoria para las interfaces de pfc_datos (DIP)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
from pfc_datos.repositorios import Usuario


class BitacoraMemoria:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, str, dict[str, Any]]] = []

    def registrar(self, tipo: str, componente: str, descripcion: str, **detalle: Any) -> None:
        self.eventos.append((tipo, componente, descripcion, detalle))


class UsuariosMemoria:
    def __init__(self, usuarios: list[Usuario]) -> None:
        self._usuarios = {u.correo: u for u in usuarios}

    def por_correo(self, correo: str) -> Usuario | None:
        return self._usuarios.get(correo)

    def registrar_intento(
        self, id_usuario: int, exitoso: bool, bloquear_hasta: dt.datetime | None
    ) -> None:
        for u in self._usuarios.values():
            if u.id_usuario == id_usuario:
                u.intentos_fallidos = 0 if exitoso else u.intentos_fallidos + 1
                u.bloqueado_hasta = bloquear_hasta


class ProcesamientosMemoria:
    def __init__(self) -> None:
        self.filas: dict[int, dict[str, Any]] = {}

    def crear(
        self,
        id_usuario: int,
        tipo: str,
        desde: dt.date,
        hasta: dt.date,
        id_modelo_version: int | None = None,
        ubigeo_dep: str | None = None,
    ) -> int:
        from pfc_datos.repositorios import ProcesamientoActivoError

        if any(f["estado"] in ("PENDIENTE", "EN_CURSO", "EN_ESPERA") for f in self.filas.values()):
            raise ProcesamientoActivoError
        nuevo = len(self.filas) + 1
        self.filas[nuevo] = {
            "id_procesamiento": nuevo,
            "tipo": tipo,
            "estado": "PENDIENTE",
            "fecha_desde": desde,
            "fecha_hasta": hasta,
            "id_usuario": id_usuario,
            "ubigeo_dep": ubigeo_dep,
        }
        return nuevo

    def obtener(self, id_procesamiento: int) -> dict[str, Any] | None:
        return self.filas.get(id_procesamiento)

    def activo(self) -> dict[str, Any] | None:
        activos = ("PENDIENTE", "EN_CURSO", "EN_ESPERA")
        return next((f for f in self.filas.values() if f["estado"] in activos), None)

    def cancelar(self, id_procesamiento: int) -> bool:
        self.filas[id_procesamiento]["estado"] = "CANCELADO"
        return True

    def reanudar(self, id_procesamiento: int) -> None:
        self.filas[id_procesamiento]["estado"] = "PENDIENTE"


@pytest.fixture
def bitacora() -> BitacoraMemoria:
    return BitacoraMemoria()


@pytest.fixture
def almacen(tmp_path: Path) -> Any:
    from pfc_datos.almacen import AlmacenArchivos

    return AlmacenArchivos(tmp_path / "d2")

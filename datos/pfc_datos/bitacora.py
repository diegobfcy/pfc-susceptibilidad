"""D3: bitácora de solo inserción. En producción es la tabla sistema.bitacora de D1; aquí
se ofrece además una implementación en archivo JSONL para la estación de entrenamiento."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

TIPOS = frozenset({"INFORMATIVO", "ADVERTENCIA", "ERROR"})


class BitacoraArchivo:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)

    def registrar(self, tipo: str, componente: str, descripcion: str, **detalle: Any) -> None:
        if tipo not in TIPOS:
            raise ValueError(f"tipo de evento no permitido: {tipo}")
        evento = {
            "ocurrido_en": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "tipo": tipo,
            "componente": componente,
            "descripcion": descripcion,
            "detalle": detalle,
        }
        with self._ruta.open("a", encoding="utf-8") as archivo:
            archivo.write(json.dumps(evento, ensure_ascii=False, default=str) + "\n")


class BitacoraBD:
    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def registrar(self, tipo: str, componente: str, descripcion: str, **detalle: Any) -> None:
        if tipo not in TIPOS:
            raise ValueError(f"tipo de evento no permitido: {tipo}")
        with self._motor.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO sistema.bitacora (tipo, componente, descripcion, detalle) "
                    "VALUES (:t, :c, :d, CAST(:j AS jsonb))"
                ),
                {"t": tipo, "c": componente, "d": descripcion, "j": json.dumps(detalle, default=str)},
            )

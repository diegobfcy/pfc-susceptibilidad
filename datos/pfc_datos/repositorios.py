"""D1: repositorios de usuarios y procesamientos con consultas parametrizadas (OWASP A03)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class Usuario:
    id_usuario: int
    correo: str
    rol: str
    hash_clave: str
    activo: bool
    intentos_fallidos: int
    bloqueado_hasta: dt.datetime | None


class RepositorioUsuarios(Protocol):
    def por_correo(self, correo: str) -> Usuario | None: ...

    def registrar_intento(self, id_usuario: int, exitoso: bool, bloquear_hasta: dt.datetime | None) -> None: ...


class RepositorioProcesamientos(Protocol):
    def crear(self, id_usuario: int, tipo: str, desde: dt.date, hasta: dt.date) -> int: ...

    def obtener(self, id_procesamiento: int) -> dict[str, Any] | None: ...


class UsuariosBD:
    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def por_correo(self, correo: str) -> Usuario | None:
        with self._motor.connect() as c:
            fila = c.execute(text("""
                SELECT u.id_usuario, u.correo, r.codigo AS rol, u.hash_clave, u.activo,
                       u.intentos_fallidos, u.bloqueado_hasta
                FROM sistema.usuario u JOIN sistema.rol r USING (id_rol)
                WHERE u.correo = :correo"""), {"correo": correo}).mappings().first()
        return Usuario(**fila) if fila else None

    def registrar_intento(self, id_usuario: int, exitoso: bool, bloquear_hasta: dt.datetime | None) -> None:
        with self._motor.begin() as c:
            c.execute(text("""
                UPDATE sistema.usuario
                SET intentos_fallidos = CASE WHEN :ok THEN 0 ELSE intentos_fallidos + 1 END,
                    bloqueado_hasta = :hasta
                WHERE id_usuario = :id"""), {"ok": exitoso, "hasta": bloquear_hasta, "id": id_usuario})


class ProcesamientosBD:
    ZONA_MACRORREGION = (
        "ST_Multi(ST_MakeEnvelope(-81.5249, -10.9169, -76.6030, -3.3500, 4326))"
    )

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def crear(self, id_usuario: int, tipo: str, desde: dt.date, hasta: dt.date) -> int:
        with self._motor.begin() as c:
            return c.execute(text(f"""
                INSERT INTO sistema.procesamiento (id_usuario, tipo, fecha_desde, fecha_hasta, zona)
                VALUES (:u, :t, :d, :h, {self.ZONA_MACRORREGION})
                RETURNING id_procesamiento"""),  # nosec B608: constante, sin datos del usuario
                {"u": id_usuario, "t": tipo, "d": desde, "h": hasta}).scalar_one()

    def obtener(self, id_procesamiento: int) -> dict[str, Any] | None:
        with self._motor.connect() as c:
            fila = c.execute(text("""
                SELECT id_procesamiento, tipo, estado, fase, fecha_desde, fecha_hasta,
                       iniciado_en, finalizado_en
                FROM sistema.procesamiento WHERE id_procesamiento = :id"""),
                {"id": id_procesamiento}).mappings().first()
        return dict(fila) if fila else None

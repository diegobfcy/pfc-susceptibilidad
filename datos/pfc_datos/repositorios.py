"""D1: repositorios de usuarios y procesamientos con consultas parametrizadas (OWASP A03)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

ESTADOS_CANCELABLES = frozenset({"PENDIENTE", "EN_CURSO", "EN_ESPERA"})


class ProcesamientoActivoError(Exception):
    """Ya hay un procesamiento activo: el índice único de D1 rechazó el segundo (RF-04)."""


@dataclass
class Usuario:
    """Usuario del sistema con su rol y el estado del bloqueo por intentos fallidos."""

    id_usuario: int
    correo: str
    rol: str
    hash_clave: str
    activo: bool
    intentos_fallidos: int
    bloqueado_hasta: dt.datetime | None


class RepositorioUsuarios(Protocol):
    """Interfaz de acceso a los usuarios que usa la autenticación."""

    def por_correo(self, correo: str) -> Usuario | None:
        """Usuario con ese correo, o None si no existe."""

    def registrar_intento(
        self, id_usuario: int, exitoso: bool, bloquear_hasta: dt.datetime | None
    ) -> None:
        """Registra un intento de acceso: reinicia o incrementa el contador y fija el bloqueo."""


class RepositorioProcesamientos(Protocol):
    """Interfaz de la cola de procesamientos (sistema.procesamiento)."""

    def crear(
        self,
        id_usuario: int,
        tipo: str,
        desde: dt.date,
        hasta: dt.date,
        id_modelo_version: int | None = None,
    ) -> int:
        """Encola un procesamiento y devuelve su identificador."""

    def obtener(self, id_procesamiento: int) -> dict[str, Any] | None:
        """Estado de un procesamiento, o None si no existe."""

    def cancelar(self, id_procesamiento: int) -> bool:
        """Cancela un procesamiento activo. True si quedó CANCELADO."""

    def reanudar(self, id_procesamiento: int) -> None:
        """Devuelve a PENDIENTE un procesamiento EN_ESPERA."""


class UsuariosBD:
    """Repositorio de usuarios sobre sistema.usuario de D1."""

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def por_correo(self, correo: str) -> Usuario | None:
        """Usuario con ese correo y el código de su rol, o None si no existe."""
        with self._motor.connect() as c:
            fila = (
                c.execute(
                    text("""
                SELECT u.id_usuario, u.correo, r.codigo AS rol, u.hash_clave, u.activo,
                       u.intentos_fallidos, u.bloqueado_hasta
                FROM sistema.usuario u JOIN sistema.rol r USING (id_rol)
                WHERE u.correo = :correo"""),
                    {"correo": correo},
                )
                .mappings()
                .first()
            )
        return Usuario(**fila) if fila else None

    def registrar_intento(
        self, id_usuario: int, exitoso: bool, bloquear_hasta: dt.datetime | None
    ) -> None:
        """Reinicia el contador si el intento fue exitoso o lo incrementa; fija el bloqueo."""
        with self._motor.begin() as c:
            c.execute(
                text("""
                UPDATE sistema.usuario
                SET intentos_fallidos = CASE WHEN :ok THEN 0 ELSE intentos_fallidos + 1 END,
                    bloqueado_hasta = :hasta
                WHERE id_usuario = :id"""),
                {"ok": exitoso, "hasta": bloquear_hasta, "id": id_usuario},
            )


class ProcesamientosBD:
    """Repositorio de procesamientos sobre sistema.procesamiento de D1."""

    ZONA_MACRORREGION = "ST_Multi(ST_MakeEnvelope(-81.5249, -10.9169, -76.6030, -3.3500, 4326))"

    def __init__(self, motor: Engine) -> None:
        self._motor = motor

    def crear(
        self,
        id_usuario: int,
        tipo: str,
        desde: dt.date,
        hasta: dt.date,
        id_modelo_version: int | None = None,
        ubigeo_dep: str | None = None,
    ) -> int:
        """Encola un procesamiento con la versión de umbrales vigente.

        La zona (RF-01) es el departamento ubigeo_dep o, si es None, la macrorregión completa.

        Lanza ProcesamientoActivoError si ya hay uno activo: lo impide el índice único
        ux_procesamiento_activo (RF-04).
        """
        try:
            with self._motor.begin() as c:
                return c.execute(
                    text(f"""
                    INSERT INTO sistema.procesamiento
                        (id_usuario, tipo, fecha_desde, fecha_hasta, zona, ubigeo_dep,
                         id_modelo_version, id_umbral_version)
                    VALUES (:u, :t, :d, :h,
                        COALESCE((SELECT geom FROM ref.departamento WHERE ubigeo_dep = :dep),
                                 {self.ZONA_MACRORREGION}),
                        :dep, :m,
                        (SELECT id_umbral_version FROM sistema.umbral_version
                         WHERE vigente ORDER BY id_umbral_version DESC LIMIT 1))
                    RETURNING id_procesamiento"""),  # nosec B608: constante, sin datos del usuario
                    {
                        "u": id_usuario,
                        "t": tipo,
                        "d": desde,
                        "h": hasta,
                        "m": id_modelo_version,
                        "dep": ubigeo_dep,
                    },
                ).scalar_one()
        except IntegrityError as error:
            if "ux_procesamiento_activo" in str(error):
                raise ProcesamientoActivoError from error
            raise

    def cancelar(self, id_procesamiento: int) -> bool:
        """True si el procesamiento estaba activo y quedó CANCELADO."""
        with self._motor.begin() as c:
            return (
                c.execute(
                    text("""
                UPDATE sistema.procesamiento SET estado = 'CANCELADO', finalizado_en = now()
                WHERE id_procesamiento = :id
                  AND estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')"""),
                    {"id": id_procesamiento},
                ).rowcount
                == 1
            )

    def reanudar(self, id_procesamiento: int) -> None:
        """RF-02: tras la carga manual, el procesamiento en espera vuelve a la cola."""
        with self._motor.begin() as c:
            c.execute(
                text("""UPDATE sistema.procesamiento SET estado = 'PENDIENTE', fase = NULL
                        WHERE id_procesamiento = :id AND estado = 'EN_ESPERA'"""),
                {"id": id_procesamiento},
            )

    def activo(self) -> dict[str, Any] | None:
        """El procesamiento PENDIENTE, EN_CURSO o EN_ESPERA (hay a lo sumo uno), o None."""
        with self._motor.connect() as c:
            id_activo = c.execute(
                text("""SELECT id_procesamiento FROM sistema.procesamiento
                        WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')"""),
            ).scalar_one_or_none()
        return self.obtener(id_activo) if id_activo is not None else None

    def obtener(self, id_procesamiento: int) -> dict[str, Any] | None:
        """Estado, fase, tiempos, memoria y resumen de un procesamiento, o None si no existe."""
        with self._motor.connect() as c:
            fila = (
                c.execute(
                    text("""
                SELECT id_procesamiento, tipo, estado, fase, fecha_desde, fecha_hasta, ubigeo_dep,
                       iniciado_en, finalizado_en, memoria_max_gb::float8 AS memoria_max_gb,
                       tiempos_s, resumen
                FROM sistema.procesamiento WHERE id_procesamiento = :id"""),
                    {"id": id_procesamiento},
                )
                .mappings()
                .first()
            )
        return dict(fila) if fila else None

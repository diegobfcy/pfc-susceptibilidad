"""Consola de administración: alta de cuentas por rol (solo por consola, según el RBAC)."""

from __future__ import annotations

import argparse
import getpass
import os

from pfc_datos.bd import crear_motor
from sqlalchemy import text

from pfc_servicios.seguridad.claves import generar_hash


def crear_usuario(motor: object, nombre: str, correo: str, rol: str, clave: str) -> None:
    """Crea un usuario con el rol dado o, si el correo existe, cambia su clave y lo desbloquea.

    La clave se guarda solo como hash Argon2id.
    """
    with motor.begin() as c:  # type: ignore[attr-defined]
        c.execute(
            text(
                """
            INSERT INTO sistema.usuario (id_rol, nombre, correo, hash_clave)
            SELECT id_rol, :nombre, :correo, :hash FROM sistema.rol WHERE codigo = :rol
            ON CONFLICT (correo) DO UPDATE
            SET hash_clave = EXCLUDED.hash_clave, intentos_fallidos = 0, bloqueado_hasta = NULL"""
            ),
            {"nombre": nombre, "correo": correo, "hash": generar_hash(clave), "rol": rol},
        )


def main() -> None:
    """Comando de administración: crea o actualiza un usuario.

    La clave se toma de PFC_CLAVE_NUEVA o se pide por consola sin mostrarla.
    """
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("correo")
    argumentos.add_argument("rol", choices=["INVESTIGADOR", "ESPECIALISTA", "ASESOR"])
    argumentos.add_argument("--nombre", default="")
    a = argumentos.parse_args()
    clave = os.environ.get("PFC_CLAVE_NUEVA") or getpass.getpass("Clave: ")
    crear_usuario(crear_motor(), a.nombre or a.correo, a.correo, a.rol, clave)


if __name__ == "__main__":
    main()

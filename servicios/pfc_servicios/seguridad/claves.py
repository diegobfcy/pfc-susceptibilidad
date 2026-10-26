"""S2. Hash de contraseñas con Argon2id y límite de intentos fallidos."""

from __future__ import annotations

import datetime as dt
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from pfc_datos.repositorios import RepositorioUsuarios, Usuario

MAX_INTENTOS: Final = 5
BLOQUEO: Final = dt.timedelta(minutes=15)
_hasher = PasswordHasher()  # Argon2id con los parámetros recomendados por RFC 9106


def generar_hash(clave: str) -> str:
    return _hasher.hash(clave)


def autenticar(repo: RepositorioUsuarios, correo: str, clave: str) -> Usuario | None:
    """Devuelve el usuario si la clave es correcta; aplica el bloqueo tras 5 fallos."""
    usuario = repo.por_correo(correo)
    ahora = dt.datetime.now(dt.UTC)
    if usuario is None or not usuario.activo:
        return None
    if usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        return None
    try:
        _hasher.verify(usuario.hash_clave, clave)
    except (VerificationError, InvalidHashError):
        bloqueo = ahora + BLOQUEO if usuario.intentos_fallidos + 1 >= MAX_INTENTOS else None
        repo.registrar_intento(usuario.id_usuario, False, bloqueo)
        return None
    repo.registrar_intento(usuario.id_usuario, True, None)
    return usuario

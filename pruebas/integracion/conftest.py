"""Cada prueba de integración parte sin procesamientos activos (índice único de D1)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import text

BASES_PROTEGIDAS = {"pfc"}  # base del entorno de sistema y de staging: no se vacía en pruebas


def pytest_sessionstart(session: pytest.Session) -> None:
    """Detiene la sesión si PFC_BD_URL apunta a una base protegida (usar pfc_it)."""
    url = os.environ.get("PFC_BD_URL", "")
    base = url.rsplit("/", 1)[-1].split("?", 1)[0] if url else ""
    if base in BASES_PROTEGIDAS:
        pytest.exit(f"las pruebas de integración vacían tablas: PFC_BD_URL apunta a '{base}'", 2)


@pytest.fixture(autouse=True)
def sin_procesamientos_activos() -> Iterator[None]:
    url = os.environ.get("PFC_BD_URL")
    if url:
        from pfc_datos.bd import crear_motor

        motor = crear_motor(url)
        with motor.begin() as c:
            c.execute(text("""UPDATE sistema.procesamiento SET estado = 'CANCELADO'
                WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')"""))
        motor.dispose()
    yield

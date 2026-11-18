"""Pruebas de sistema contra el entorno en ejecución (HTTPS real a través de nginx)."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from cliente_pruebas import Cliente, clave  # noqa: E402

URL_VISOR = "https://127.0.0.1:8444"
EVIDENCIA = RAIZ / "resultados" / "pruebas" / "c3_sistema"


def pytest_collection_modifyitems(items: list[Any]) -> None:
    if not os.environ.get("PFC_SISTEMA"):
        marca = pytest.mark.skip(reason="requiere el entorno en ejecución (PFC_SISTEMA=1)")
        for item in items:
            if "/sistema/" in str(item.fspath):
                item.add_marker(marca)


@pytest.fixture(scope="session")
def clientes() -> dict[str, Cliente]:
    sesiones = {}
    for rol in ("INVESTIGADOR", "ESPECIALISTA", "ASESOR"):
        sesiones[rol] = Cliente()
        assert sesiones[rol].entrar(rol).status_code == 204
    return sesiones


@pytest.fixture(scope="session")
def motor_bd() -> Any:
    from sqlalchemy import create_engine

    return create_engine(os.environ["PFC_BD_URL_SISTEMA"])


@pytest.fixture(scope="session", params=["chromium", "firefox", "msedge"])
def navegador(request: Any) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        if request.param == "msedge":  # Microsoft Edge instalado, motor Chromium
            instancia = p.chromium.launch(channel="msedge")
        else:
            instancia = getattr(p, request.param).launch()
        yield instancia
        instancia.close()


@pytest.fixture(scope="session")
def estado_sesion(navegador: Any, tmp_path_factory: Any) -> dict[str, str]:
    """Una sesión por navegador y rol: el proxy limita los inicios de sesión."""
    rutas = {}
    carpeta = tmp_path_factory.mktemp("estado")
    for rol in ("INVESTIGADOR", "ESPECIALISTA", "ASESOR"):
        contexto = navegador.new_context(ignore_https_errors=True)
        pagina = contexto.new_page()
        pagina.goto(f"{URL_VISOR}/visor/")
        correo = {"INVESTIGADOR": "inv", "ESPECIALISTA": "esp", "ASESOR": "ase"}[rol]
        pagina.fill("input[name=correo]", f"{correo}@pruebas.pfc")
        pagina.fill("input[name=clave]", clave(rol))
        pagina.click("button.primario")
        pagina.wait_for_selector("#acceso", state="hidden")
        rutas[rol] = str(carpeta / f"{rol}.json")
        contexto.storage_state(path=rutas[rol])
        contexto.close()
    return rutas


class Visor:
    def __init__(self, navegador: Any, estado: str) -> None:
        self.contexto = navegador.new_context(
            ignore_https_errors=True, storage_state=estado, viewport={"width": 1440, "height": 900}
        )
        self.pagina = self.contexto.new_page()
        self.errores: list[str] = []
        self.pagina.on(
            "console",
            lambda m: (
                self.errores.append(m.text)
                if m.type == "error" and "tile.openstreetmap" not in m.text
                else None
            ),
        )
        self.pagina.on("pageerror", lambda e: self.errores.append(str(e)))

    def abrir(self, periodo: str = "2023-03") -> Any:
        self.pagina.goto(f"{URL_VISOR}/visor/?periodo={periodo}")
        self.pagina.wait_for_selector('body[data-listo="1"]', timeout=45000)
        self.esperar_teselas()
        return self.pagina

    def esperar_teselas(self) -> None:
        self.pagina.wait_for_load_state("networkidle", timeout=45000)
        self.pagina.wait_for_timeout(800)

    def cerrar(self) -> None:
        self.contexto.close()


@pytest.fixture
def visor(navegador: Any, estado_sesion: dict[str, str]) -> Iterator[Visor]:
    v = Visor(navegador, estado_sesion["ESPECIALISTA"])
    yield v
    v.cerrar()


@pytest.fixture
def panel(navegador: Any, estado_sesion: dict[str, str]) -> Iterator[Visor]:
    v = Visor(navegador, estado_sesion["ASESOR"])
    yield v
    v.cerrar()

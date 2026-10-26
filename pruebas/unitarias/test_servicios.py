"""S1/S2: sesión con Argon2id, bloqueo por intentos, RBAC, validación y cabeceras."""

from __future__ import annotations

from typing import Any

import pytest
from pfc_datos.repositorios import Usuario
from pfc_servicios import crear_app
from pfc_servicios.seguridad.claves import MAX_INTENTOS, generar_hash

from pruebas.conftest import ProcesamientosMemoria, UsuariosMemoria

CLAVE = "Clave-Segura-2026"


def _usuario(id_: int, correo: str, rol: str) -> Usuario:
    return Usuario(id_, correo, rol, generar_hash(CLAVE), True, 0, None)


@pytest.fixture
def cliente() -> Any:
    usuarios = UsuariosMemoria(
        [
            _usuario(1, "inv@ucsm.edu.pe", "INVESTIGADOR"),
            _usuario(2, "esp@ucsm.edu.pe", "ESPECIALISTA"),
        ]
    )
    app = crear_app(
        {
            "usuarios": usuarios,
            "procesamientos": ProcesamientosMemoria(),
            "comprobar_bd": lambda: True,
        }
    )
    app.config.update(TESTING=True, SESSION_COOKIE_SECURE=False)
    return app.test_client()


def _entrar(cliente: Any, correo: str, clave: str = CLAVE) -> Any:
    return cliente.post("/api/sesion", json={"correo": correo, "clave": clave})


def test_salud_y_cabeceras(cliente: Any) -> None:
    r = cliente.get("/api/salud")
    assert r.status_code == 200 and r.get_json()["base_datos"] is True
    for cabecera in ("Content-Security-Policy", "X-Frame-Options", "Strict-Transport-Security"):
        assert cabecera in r.headers


def test_inicio_de_sesion(cliente: Any) -> None:
    assert _entrar(cliente, "inv@ucsm.edu.pe").get_json() == {"rol": "INVESTIGADOR"}
    assert _entrar(cliente, "inv@ucsm.edu.pe", "incorrecta").status_code == 401
    assert _entrar(cliente, "nadie@ucsm.edu.pe").status_code == 401


def test_bloqueo_tras_intentos_fallidos(cliente: Any) -> None:
    for _ in range(MAX_INTENTOS):
        _entrar(cliente, "esp@ucsm.edu.pe", "mala")
    assert _entrar(cliente, "esp@ucsm.edu.pe").status_code == 401  # bloqueado aunque sea correcta


def test_crear_y_consultar_ingesta(cliente: Any) -> None:
    _entrar(cliente, "inv@ucsm.edu.pe")
    r = cliente.post(
        "/api/ingestas",
        json={"tipo": "INGESTA", "fecha_desde": "2017-01-01", "fecha_hasta": "2017-12-31"},
    )
    assert r.status_code == 202
    estado = cliente.get(f"/api/ingestas/{r.get_json()['id_procesamiento']}").get_json()
    assert estado["estado"] == "PENDIENTE" and estado["fecha_desde"] == "2017-01-01"
    assert cliente.get("/api/ingestas/999").status_code == 404


def test_rbac(cliente: Any) -> None:
    cuerpo = {"tipo": "INGESTA", "fecha_desde": "2017-01-01", "fecha_hasta": "2017-12-31"}
    assert cliente.post("/api/ingestas", json=cuerpo).status_code == 401
    _entrar(cliente, "esp@ucsm.edu.pe")
    assert cliente.post("/api/ingestas", json=cuerpo).status_code == 403


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"tipo": "BORRAR", "fecha_desde": "2017-01-01", "fecha_hasta": "2017-12-31"},
        {
            "tipo": "INGESTA",
            "fecha_desde": "2017-01-01'; DROP TABLE x;--",
            "fecha_hasta": "2017-12-31",
        },
        {"tipo": "INGESTA", "fecha_desde": "1970-01-01", "fecha_hasta": "2017-12-31"},
        {"tipo": "INGESTA", "fecha_desde": "2018-01-01", "fecha_hasta": "2017-12-31"},
    ],
)
def test_rechazo_de_entradas_invalidas(cliente: Any, cuerpo: dict[str, str]) -> None:
    _entrar(cliente, "inv@ucsm.edu.pe")
    assert cliente.post("/api/ingestas", json=cuerpo).status_code == 400


def test_salud_degradada_sin_bd() -> None:
    app = crear_app(
        {
            "usuarios": UsuariosMemoria([]),
            "procesamientos": ProcesamientosMemoria(),
            "comprobar_bd": lambda: False,
        }
    )
    assert app.test_client().get("/api/salud").status_code == 503

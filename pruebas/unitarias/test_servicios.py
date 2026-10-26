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


def _csrf(cliente: Any) -> dict[str, str]:
    return {"X-CSRFToken": cliente.get("/api/sesion/csrf").get_json()["csrf"]}


def _entrar(cliente: Any, correo: str, clave: str = CLAVE) -> Any:
    return cliente.post(
        "/api/sesion", json={"correo": correo, "clave": clave}, headers=_csrf(cliente)
    )


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
        headers=_csrf(cliente),
    )
    assert r.status_code == 202
    estado = cliente.get(f"/api/ingestas/{r.get_json()['id_procesamiento']}").get_json()
    assert estado["estado"] == "PENDIENTE" and estado["fecha_desde"] == "2017-01-01"
    assert cliente.get("/api/ingestas/999").status_code == 404


def test_rbac(cliente: Any) -> None:
    cuerpo = {"tipo": "INGESTA", "fecha_desde": "2017-01-01", "fecha_hasta": "2017-12-31"}
    assert cliente.post("/api/ingestas", json=cuerpo, headers=_csrf(cliente)).status_code == 401
    _entrar(cliente, "esp@ucsm.edu.pe")
    assert cliente.post("/api/ingestas", json=cuerpo, headers=_csrf(cliente)).status_code == 403


def test_post_sin_token_csrf_se_rechaza(cliente: Any) -> None:
    _entrar(cliente, "inv@ucsm.edu.pe")
    cuerpo = {"tipo": "INGESTA", "fecha_desde": "2017-01-01", "fecha_hasta": "2017-12-31"}
    r = cliente.post("/api/ingestas", json=cuerpo)
    assert r.status_code == 400 and "CSRF" in r.get_json()["detalle"]


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
    r = cliente.post("/api/ingestas", json=cuerpo, headers=_csrf(cliente))
    assert r.status_code == 400 and "CSRF" not in r.get_json()["detalle"]


def test_salud_degradada_sin_bd() -> None:
    app = crear_app(
        {
            "usuarios": UsuariosMemoria([]),
            "procesamientos": ProcesamientosMemoria(),
            "comprobar_bd": lambda: False,
        }
    )
    assert app.test_client().get("/api/salud").status_code == 503

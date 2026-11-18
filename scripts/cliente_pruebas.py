"""Cliente HTTPS del entorno de pruebas: sesión con CSRF real a través de nginx."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests
import urllib3

urllib3.disable_warnings()
BASE = "https://127.0.0.1:8444/api"
RAIZ = Path(__file__).resolve().parents[1]
CUENTAS = {"INVESTIGADOR": "inv", "ESPECIALISTA": "esp", "ASESOR": "ase"}


def clave(rol: str) -> str:
    return (RAIZ / "data" / "pruebas" / f".clave_{CUENTAS[rol]}").read_text().strip()


class Cliente:
    def __init__(self, base: str = BASE) -> None:
        self.base = base
        self.s = requests.Session()
        self.s.verify = False  # certificado autofirmado del entorno de pruebas
        self.s.headers["Referer"] = base.removesuffix("/api") + "/"  # como un navegador real

    def csrf(self) -> dict[str, str]:
        return {"X-CSRFToken": self.s.get(f"{self.base}/sesion/csrf").json()["csrf"]}

    def entrar(self, rol: str | None = None, correo: str | None = None, contra: str = "") -> Any:
        correo = correo or f"{CUENTAS[rol]}@pruebas.pfc"
        contra = contra or clave(rol)
        return self.s.post(
            f"{self.base}/auth/login",
            json={"correo": correo, "clave": contra},
            headers=self.csrf(),
        )

    def get(self, ruta: str, **k: Any) -> Any:
        return self.s.get(f"{self.base}{ruta}", **k)

    def post(self, ruta: str, **k: Any) -> Any:
        return self.s.post(f"{self.base}{ruta}", headers=self.csrf(), **k)

"""Escenario D: visor bajo carga (teselas MVT y consulta por punto) durante la inferencia."""

from __future__ import annotations

import math
import os
import random

import urllib3
from locust import HttpUser, between, task

urllib3.disable_warnings()
PERIODO = os.environ.get("PFC_PERIODO_CARGA", "2017-03")
DOMINIO = (-81.52, -10.91, -76.61, -3.36)  # lon_min, lat_min, lon_max, lat_max


def indice_tesela(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    x = int((lon + 180) / 360 * n)
    rad = math.radians(lat)
    return x, int((1 - math.asinh(math.tan(rad)) / math.pi) / 2 * n)


class UsuarioVisor(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        self.client.verify = False
        self.client.headers["Referer"] = f"{self.host}/"
        csrf = self.client.get("/api/sesion/csrf", name="csrf").json()["csrf"]
        self.client.post(
            "/api/auth/login",
            json={"correo": "esp@pruebas.pfc", "clave": os.environ["PFC_CLAVE_ESP"]},
            headers={"X-CSRFToken": csrf},
            name="login",
        )

    @task(5)
    def tesela(self) -> None:
        z = random.randint(6, 12)
        lon = random.uniform(DOMINIO[0], DOMINIO[2])
        lat = random.uniform(DOMINIO[1], DOMINIO[3])
        x, y = indice_tesela(lon, lat, z)
        with self.client.get(
            f"/api/mapas/susceptibilidad/{PERIODO}/{z}/{x}/{y}.pbf",
            name="tesela MVT",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 204):
                r.success()

    @task(1)
    def consulta(self) -> None:
        with self.client.get(
            "/api/consulta-punto",
            params={
                "periodo": PERIODO,
                "lat": round(random.uniform(DOMINIO[1], DOMINIO[3]), 5),
                "lon": round(random.uniform(DOMINIO[0], DOMINIO[2]), 5),
            },
            name="consulta-punto",
            catch_response=True,
        ) as r:
            if r.status_code in (200, 404):  # 404: punto fuera del dominio de análisis
                r.success()

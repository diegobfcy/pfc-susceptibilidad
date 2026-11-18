"""Escenario D escalonado: carga creciente sobre el visor hasta superar el umbral o romperse.

Cada escalón dura PFC_ESCALON_S segundos con tantos usuarios como solicitudes por segundo
objetivo; cada usuario envía una solicitud por segundo (constant_throughput), así que si el
servidor se satura la tasa lograda queda por debajo de la objetivo. Al cerrar cada escalón se
calculan el percentil 95, la tasa de errores y la tasa lograda. Un escalón cumple si respeta el
umbral del escenario D (p95 <= 2 s y errores < 1 %); se marca saturado si la tasa lograda cae
por debajo del 90 % de la objetivo. La prueba se detiene tras dos escalones seguidos que
incumplen el umbral, para observar también el comportamiento después de superarlo.
Los resultados se escriben en PFC_SALIDA_ESCALONADA (JSON).

Todos los usuarios comparten una sesión: el inicio de sesión tiene un límite de 30 por minuto
en nginx y no es lo que se mide.
"""

from __future__ import annotations

import json
import math
import os
import random
import time
from pathlib import Path

import requests
import urllib3
from locust import HttpUser, LoadTestShape, constant_throughput, events, task

urllib3.disable_warnings()
PERIODO = os.environ.get("PFC_PERIODO_CARGA", "2017-03")
DOMINIO = (-81.52, -10.91, -76.61, -3.36)  # lon_min, lat_min, lon_max, lat_max
ESCALONES = [int(v) for v in os.environ.get(
    "PFC_ESCALONES", "5,10,15,20,25,30,35,40,50,60,80,100,130,160").split(",")]  # fmt: skip
DURACION = int(os.environ.get("PFC_ESCALON_S", "60"))
SALIDA = Path(os.environ.get("PFC_SALIDA_ESCALONADA", "escalonada.json"))
UMBRAL_P95_MS = 2000.0
UMBRAL_ERRORES = 0.01
TIMEOUT_S = 10

SESION: dict[str, str] = {}
MUESTRAS: list[tuple[float, float, bool, str]] = []  # (instante, ms, fallo, nombre)
RESULTADOS: list[dict] = []


@events.test_start.add_listener
def iniciar_sesion(environment, **_) -> None:  # noqa: ANN001
    """Inicia una única sesión y la guarda para todos los usuarios virtuales."""
    s = requests.Session()
    s.verify = False
    s.headers["Referer"] = f"{environment.host}/"
    csrf = s.get(f"{environment.host}/api/sesion/csrf").json()["csrf"]
    r = s.post(
        f"{environment.host}/api/auth/login",
        json={"correo": "esp@pruebas.pfc", "clave": os.environ["PFC_CLAVE_ESP"]},
        headers={"X-CSRFToken": csrf},
    )
    r.raise_for_status()
    SESION.update(s.cookies.get_dict())


@events.request.add_listener
def registrar(request_type, name, response_time, exception, **_) -> None:  # noqa: ANN001
    """Guarda cada solicitud con su instante, latencia y resultado."""
    MUESTRAS.append((time.time(), float(response_time), exception is not None, name))


def percentil(valores: list[float], p: float) -> float:
    """Percentil por rango más cercano."""
    if not valores:
        return math.nan
    orden = sorted(valores)
    return orden[max(0, math.ceil(p / 100 * len(orden)) - 1)]


def cerrar_escalon(objetivo: int, inicio: float, fin: float) -> dict:
    """Métricas del escalón, descartando los primeros 5 s de rampa de usuarios."""
    ventana = [m for m in MUESTRAS if inicio + 5 <= m[0] < fin]
    lat = [m[1] for m in ventana]
    fallos = sum(m[2] for m in ventana)
    segundos = fin - inicio - 5
    teselas = [m[1] for m in ventana if m[3] == "tesela MVT"]
    fila = {
        "objetivo_rps": objetivo,
        "solicitudes": len(ventana),
        "lograda_rps": round(len(ventana) / segundos, 2),
        "p50_ms": round(percentil(lat, 50), 1),
        "p95_ms": round(percentil(lat, 95), 1),
        "p99_ms": round(percentil(lat, 99), 1),
        "p95_teselas_ms": round(percentil(teselas, 95), 1),
        "errores": fallos,
        "tasa_errores": round(fallos / len(ventana), 4) if ventana else 1.0,
    }
    fila["cumple_umbral"] = (
        fila["p95_ms"] <= UMBRAL_P95_MS and fila["tasa_errores"] < UMBRAL_ERRORES
    )
    fila["saturado"] = fila["lograda_rps"] < 0.9 * objetivo
    RESULTADOS.append(fila)
    SALIDA.write_text(json.dumps({"periodo": PERIODO, "escalon_s": DURACION,
                                  "escalones": RESULTADOS}, indent=2))  # fmt: skip
    print(f"ESCALON {json.dumps(fila)}", flush=True)
    return fila


class Escalones(LoadTestShape):
    """Escalones de solicitudes por segundo; se detiene tras dos incumplimientos seguidos."""

    def __init__(self) -> None:
        super().__init__()
        self.indice = 0
        self.inicio_escalon: float | None = None
        self.incumplidos = 0

    def tick(self) -> tuple[int, float] | None:
        """Usuarios y tasa de creación del escalón vigente, o None para terminar."""
        ahora = time.time()
        if self.inicio_escalon is None:
            self.inicio_escalon = ahora
        if ahora - self.inicio_escalon >= DURACION:
            fila = cerrar_escalon(ESCALONES[self.indice], self.inicio_escalon, ahora)
            self.indice += 1
            self.inicio_escalon = ahora
            self.incumplidos = 0 if fila["cumple_umbral"] else self.incumplidos + 1
            if self.incumplidos >= 2 or self.indice >= len(ESCALONES):
                return None
        objetivo = ESCALONES[self.indice]
        return objetivo, max(objetivo, 5)


class UsuarioVisor(HttpUser):
    """Usuario del visor: 5 teselas MVT por cada consulta por punto, una solicitud por segundo."""

    wait_time = constant_throughput(1)

    def on_start(self) -> None:
        """Reutiliza la sesión compartida."""
        self.client.verify = False
        self.client.headers["Referer"] = f"{self.host}/"
        for nombre, valor in SESION.items():
            self.client.cookies.set(nombre, valor)

    @task(5)
    def tesela(self) -> None:
        """Tesela MVT aleatoria de zoom 6 a 12 dentro del dominio."""
        z = random.randint(6, 12)
        n = 2**z
        lon = random.uniform(DOMINIO[0], DOMINIO[2])
        lat = math.radians(random.uniform(DOMINIO[1], DOMINIO[3]))
        x = int((lon + 180) / 360 * n)
        y = int((1 - math.asinh(math.tan(lat)) / math.pi) / 2 * n)
        with self.client.get(
            f"/api/mapas/susceptibilidad/{PERIODO}/{z}/{x}/{y}.pbf",
            name="tesela MVT",
            catch_response=True,
            timeout=TIMEOUT_S,
        ) as r:
            if r.status_code in (200, 204):
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

    @task(1)
    def consulta(self) -> None:
        """Consulta por punto aleatorio; 404 es válido fuera del dominio de análisis."""
        with self.client.get(
            "/api/consulta-punto",
            params={
                "periodo": PERIODO,
                "lat": round(random.uniform(DOMINIO[1], DOMINIO[3]), 5),
                "lon": round(random.uniform(DOMINIO[0], DOMINIO[2]), 5),
            },
            name="consulta-punto",
            catch_response=True,
            timeout=TIMEOUT_S,
        ) as r:
            if r.status_code in (200, 404):
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}")

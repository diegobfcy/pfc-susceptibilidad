"""CP-26: CU-01 completo por la API (E1 a E4 y luego M2 sobre 2000-2026) con límites del VPS.

Compara la matriz regenerada con la original, celda a celda. Corre con el muestreador activo."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pandas as pd
from cliente_pruebas import RAIZ, Cliente

DESDE, HASTA = "2000-01-01", "2026-06-30"
SALIDA = Path(RAIZ, "resultados", "pruebas", "c4_carga", "cp26_extremo_a_extremo.json")
FINALES = ("COMPLETADO", "FALLIDO", "CANCELADO", "EN_ESPERA")


def esperar(cliente: Cliente, ruta: str) -> dict:
    ultimo, t0 = None, time.time()
    while True:
        try:
            estado = cliente.get(ruta).json()
        except Exception as error:  # noqa: BLE001 - el seguimiento registra cortes y continúa
            print("reintento", error, flush=True)
            time.sleep(10)
            continue
        if estado.get("fase") != ultimo:
            ultimo = estado.get("fase")
            print(round(time.time() - t0), estado.get("estado"), ultimo, flush=True)
        if estado.get("estado") in FINALES:
            estado["segundos_reloj"] = round(time.time() - t0, 1)
            return estado
        time.sleep(5)


def comparar_matrices(a: Path, b: Path) -> dict:
    resultado: dict = {"anios": 0, "filas_a": 0, "filas_b": 0, "anios_distintos": []}
    for carpeta in sorted(a.glob("anio=*")):
        x = pd.read_parquet(carpeta)
        y = pd.read_parquet(b / carpeta.name)
        claves = ["id_celda", "periodo"] if "periodo" in x else list(x.columns[:2])
        x = x.sort_values(claves).reset_index(drop=True)
        y = y.sort_values(claves)[x.columns].reset_index(drop=True)
        resultado["anios"] += 1
        resultado["filas_a"] += len(x)
        resultado["filas_b"] += len(y)
        if not x.equals(y):
            resultado["anios_distintos"].append(carpeta.name)
    resultado["identicas"] = not resultado["anios_distintos"]
    return resultado


def main() -> None:
    d2 = Path(sys.argv[1])
    cliente = Cliente()
    assert cliente.entrar("INVESTIGADOR").status_code == 204
    t0 = time.time()
    r = cliente.post("/entrenamientos", json={"fecha_desde": DESDE, "fecha_hasta": HASTA})
    if r.status_code != 202:
        raise SystemExit(f"{r.status_code} {r.text}")
    salida: dict = {"inicio": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    salida["etl"] = esperar(cliente, f"/ingestas/{r.json()['id_procesamiento']}")
    SALIDA.write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    if salida["etl"]["estado"] == "COMPLETADO":
        r = cliente.post(
            "/inferencias",
            json={"fecha_desde": "2000-02-01", "fecha_hasta": HASTA, "id_modelo_version": 1},
        )
        if r.status_code != 202:
            raise SystemExit(f"{r.status_code} {r.text}")
        salida["inferencia"] = esperar(cliente, f"/inferencias/{r.json()['id_procesamiento']}")
        salida["matriz"] = comparar_matrices(Path(RAIZ, "data", "d2", "matriz"), d2 / "matriz")
    salida["segundos_total"] = round(time.time() - t0, 1)
    salida["fin"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    SALIDA.write_text(json.dumps(salida, indent=2, ensure_ascii=False))
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Escenarios A y B de la carga: lanza POST /inferencias real y mide hasta su fin.

La carpeta de salida se cambia con PFC_SALIDA_ESCENARIO (por defecto, c4_carga)."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from cliente_pruebas import RAIZ, Cliente


def main() -> None:
    nombre, desde, hasta = sys.argv[1:4]
    cliente = Cliente()
    assert cliente.entrar("INVESTIGADOR").status_code == 204
    t0 = time.time()
    r = cliente.post(
        "/inferencias",
        json={"fecha_desde": desde, "fecha_hasta": hasta, "id_modelo_version": 1},
    )
    if r.status_code != 202:
        raise SystemExit(f"{r.status_code} {r.text}")
    identificador = r.json()["id_procesamiento"]
    print("procesamiento", identificador, flush=True)
    ultimo = None
    while True:
        try:
            estado = cliente.get(f"/inferencias/{identificador}").json()
        except Exception as error:  # noqa: BLE001 - el seguimiento registra cortes y continúa
            print("reintento", error, flush=True)
            time.sleep(10)
            continue
        if estado["fase"] != ultimo:
            ultimo = estado["fase"]
            print(round(time.time() - t0), estado["estado"], ultimo, flush=True)
        if estado["estado"] in ("COMPLETADO", "FALLIDO", "CANCELADO"):
            break
        time.sleep(5)
    estado["segundos_reloj"] = round(time.time() - t0, 1)
    carpeta = os.environ.get(
        "PFC_SALIDA_ESCENARIO", Path(RAIZ, "resultados", "pruebas", "c4_carga")
    )
    destino = Path(carpeta, f"escenario_{nombre}.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(estado, indent=2, ensure_ascii=False))
    print(json.dumps(estado, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Escenario C de la carga: 20 POST /inferencias simultáneos y otros 20 con el trabajo en curso."""

from __future__ import annotations

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cliente_pruebas import RAIZ, Cliente

CUERPO = {"fecha_desde": "2000-02-01", "fecha_hasta": "2026-06-30", "id_modelo_version": 1}


def rafaga(cliente: Cliente, token: dict) -> list[tuple[int, float]]:
    def enviar(_: int) -> tuple[int, float]:
        t0 = time.perf_counter()
        r = cliente.s.post(f"{cliente.base}/inferencias", json=CUERPO, headers=token)
        return r.status_code, (time.perf_counter() - t0) * 1000

    with ThreadPoolExecutor(20) as hilos:
        return list(hilos.map(enviar, range(20)))


def resumen(respuestas: list[tuple[int, float]]) -> dict:
    tiempos = sorted(t for _, t in respuestas)
    codigos = [c for c, _ in respuestas]
    return {
        "codigos": {str(c): codigos.count(c) for c in sorted(set(codigos))},
        "p95_ms": round(statistics.quantiles(tiempos, n=20)[-1], 1),
        "max_ms": round(tiempos[-1], 1),
    }


def main() -> None:
    cliente = Cliente()
    assert cliente.entrar("INVESTIGADOR").status_code == 204
    token = cliente.csrf()
    salida = {"sin_trabajo_activo": resumen(rafaga(cliente, token))}
    time.sleep(20)  # el trabajo ya está escribiendo
    salida["con_trabajo_en_curso"] = resumen(rafaga(cliente, token))
    destino = Path(RAIZ, "resultados", "pruebas", "c4_carga", "escenario_C.json")
    destino.write_text(json.dumps(salida, indent=2))
    print(json.dumps(salida, indent=2))


if __name__ == "__main__":
    main()

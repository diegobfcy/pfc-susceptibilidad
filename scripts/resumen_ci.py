"""Resumen de las ejecuciones locales del pipeline ci-cd con act (resultados/logs/act_run*.log).

Por ejecución y trabajo: estado, paso que falló y duración (suma de los pasos). La hora y la
duración total de cada ejecución se tomaron del reloj de la estación al lanzar act.
Salida: resultados/ejecuciones_ci.json"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
TRABAJOS = ["calidad-estatica", "pruebas", "analisis-sonarqube", "desplegar-staging"]
# (ejecución, commit, hora de fin local, duración total en s) del 26/10/2026
EJECUCIONES = [
    (1, "0601279", "15:52", 69),
    (2, "d58bb88", "15:53", 5),
    (3, "b068ee2", "15:54", 10),
    (4, "972ffaa", "15:55", 45),
    (5, "6deb4ae", "15:57", 113),
    (6, "9190fdc", "16:06", 207),
    (7, "1a24fa3", "16:09", 126),
    (8, "c094893", "16:14", 313),
    (9, "f08c408", "16:23", 97),
    (10, "1f75fbb", "16:27", 204),
    (11, "69738e5", "16:30", 145),
]
PASO = re.compile(
    r"\[ci-cd/(?P<trabajo>[a-z-]+) *\] +(?P<estado>✅  Success|❌  Failure) - Main (?P<paso>.*?) "
    r"\[(?:(?P<min>\d+)m)?(?P<valor>[\d.]+)(?P<unidad>s|ms|µs)\]$"
)
FACTOR = {"s": 1.0, "ms": 1e-3, "µs": 1e-6}


def resumir(log: Path) -> dict[str, dict]:
    trabajos: dict[str, dict] = {}
    for linea in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = PASO.search(linea)
        if m:
            t = trabajos.setdefault(
                m["trabajo"], {"estado": "exito", "segundos": 0.0, "falla": None}
            )
            t["segundos"] += int(m["min"] or 0) * 60 + float(m["valor"]) * FACTOR[m["unidad"]]
            if "Failure" in m["estado"] and t["falla"] is None:
                t["estado"], t["falla"] = "falla", m["paso"]
    return {
        j: trabajos.get(j, {"estado": "no ejecutado", "segundos": 0.0, "falla": None})
        for j in TRABAJOS
    }


def main() -> None:
    salida = []
    for n, commit, hora, total in EJECUCIONES:
        trabajos = resumir(RAIZ / "resultados" / "logs" / f"act_run{n}.log")
        for t in trabajos.values():
            t["segundos"] = round(t["segundos"], 1)
        salida.append(
            {
                "ejecucion": n,
                "commit": commit,
                "fecha": f"26/10/2026 {hora}",
                "segundos_total": total,
                "trabajos": trabajos,
            }
        )
    destino = RAIZ / "resultados" / "ejecuciones_ci.json"
    destino.write_text(json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    for e in salida:
        estados = " | ".join(f"{t['estado']:>12}" for t in e["trabajos"].values())
        fallas = [t["falla"] for t in e["trabajos"].values() if t["falla"]]
        print(f"{e['ejecucion']:>2} {e['commit']} {e['segundos_total']:>4}s {estados} {fallas}")


if __name__ == "__main__":
    main()

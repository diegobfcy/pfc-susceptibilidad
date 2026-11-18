"""Muestra cada segundo la memoria y la CPU del grupo de control del entorno y de cada proceso.

Uso: muestrear_recursos.py salida.csv  (termina con SIGTERM)."""

from __future__ import annotations

import csv
import signal
import subprocess
import sys
import time
from pathlib import Path

GRUPOS = {"postgres": "postgres", "gunicorn": "gunicorn", "pfc_predictiva": "worker_m2",
          "pfc_etl": "worker_etl", "nginx": "nginx"}  # fmt: skip
PAGINA = 4096


def ruta_grupo() -> Path:
    salida = subprocess.run(
        ["systemctl", "--user", "show", "-p", "ControlGroup", "pfc-pruebas.service"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().split("=", 1)[1]  # fmt: skip
    return Path("/sys/fs/cgroup" + salida)


def rss_por_grupo(grupo: Path) -> dict[str, float]:
    totales = dict.fromkeys(GRUPOS.values(), 0.0)
    for pid in (grupo / "cgroup.procs").read_text().split():
        try:
            comando = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
            campos = Path(f"/proc/{pid}/smaps_rollup").read_text()
        except OSError:
            continue
        for linea in campos.splitlines():
            if linea.startswith("Pss:"):
                for clave, nombre in GRUPOS.items():
                    if clave in comando:
                        totales[nombre] += int(linea.split()[1]) / 1024**2
                break
    return totales


def main() -> None:
    grupo = ruta_grupo()
    continuar = [True]
    signal.signal(signal.SIGTERM, lambda *_: continuar.clear())
    uso_previo = None
    t_previo = time.time()
    with open(sys.argv[1], "w", newline="") as archivo:
        salida = csv.writer(archivo)
        salida.writerow(["t", "memoria_gb", "pico_gb", "swap_gb", "cpu_nucleos", *GRUPOS.values()])
        while continuar:
            uso = int((grupo / "cpu.stat").read_text().split()[1])
            ahora = time.time()
            nucleos = 0.0 if uso_previo is None else (uso - uso_previo) / 1e6 / (ahora - t_previo)
            uso_previo, t_previo = uso, ahora
            rss = rss_por_grupo(grupo)
            salida.writerow(
                [
                    round(ahora, 1),
                    round(int((grupo / "memory.current").read_text()) / 1024**3, 3),
                    round(int((grupo / "memory.peak").read_text()) / 1024**3, 3),
                    round(int((grupo / "memory.swap.current").read_text()) / 1024**3, 3),
                    round(nucleos, 2),
                    *(round(rss[n], 3) for n in GRUPOS.values()),
                ]
            )
            archivo.flush()
            time.sleep(1)


if __name__ == "__main__":
    main()

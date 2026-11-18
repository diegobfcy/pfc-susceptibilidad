"""Ejecuta en esta estación los pasos del pipeline de CI/CD (ci-cd.yml) y registra su resultado.

SonarQube y el despliegue a staging no forman parte de este script: se registran como no
ejecutados, no como aprobados. La carpeta de salida se cambia con PFC_SALIDA_PIPELINE."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BIN = Path(sys.executable).parent
SALIDA = Path(
    os.environ.get("PFC_SALIDA_PIPELINE", RAIZ / "resultados" / "pruebas" / "c5_regresion")
)
PASOS = [
    ("calidad-estatica", "black --check", [BIN / "black", "--check", "."]),
    ("calidad-estatica", "ruff check", [BIN / "ruff", "check", "."]),
    ("calidad-estatica", "lint-imports", [BIN / "lint-imports"]),
    ("calidad-estatica", "openapi-spec-validator",
     [BIN / "openapi-spec-validator", "api/openapi.yaml"]),
    ("calidad-estatica", "docstrings", [BIN / "python", "scripts/medir_docstrings.py"]),
    ("calidad-estatica", "pip-audit (producción)",
     [BIN / "pip-audit", "-r", str(SALIDA / "requisitos_produccion.txt")]),
    ("pruebas", "pytest --cov",
     [BIN / "python", "-m", "pytest", "pruebas/unitarias", "pruebas/integracion",
      "--cov", "--cov-branch", f"--cov-report=xml:{SALIDA / 'coverage.xml'}",
      f"--cov-report=html:{SALIDA / 'htmlcov'}", "--cov-report=term",
      f"--junitxml={SALIDA / 'pruebas.xml'}"]),
]  # fmt: skip


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "requisitos_produccion.txt").write_text(_requisitos())
    entorno = {**os.environ, "PYTHONPATH": "servicios:etl:predictiva:datos"}
    resultados = []
    for trabajo, nombre, comando in PASOS:
        t0 = time.perf_counter()
        r = subprocess.run(
            [str(c) for c in comando], cwd=RAIZ, env=entorno,
            capture_output=True, text=True, check=False,
        )  # fmt: skip
        resultados.append(
            {
                "trabajo": trabajo,
                "paso": nombre,
                "estado": "aprobado" if r.returncode == 0 else "falla",
                "segundos": round(time.perf_counter() - t0, 1),
            }
        )
        (SALIDA / f"{nombre.split()[0]}.log").write_text(r.stdout + r.stderr)
        print(nombre, resultados[-1]["estado"], flush=True)
    for trabajo in ("analisis-sonarqube", "desplegar-staging"):
        resultados.append(
            {"trabajo": trabajo, "paso": trabajo, "estado": "no ejecutado", "segundos": 0.0}
        )
    (SALIDA / "pipeline_local.json").write_text(json.dumps(resultados, indent=2))


def _requisitos() -> str:
    import tomllib

    datos = tomllib.loads((RAIZ / "pyproject.toml").read_text())
    return "\n".join(datos["project"]["dependencies"]) + "\n"


if __name__ == "__main__":
    main()

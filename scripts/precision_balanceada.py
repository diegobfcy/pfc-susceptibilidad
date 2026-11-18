"""CP-14 (RNF-02, complemento): precisión en muestras caso-control 1:1 de la versión 1.

El umbral (0.5) y el diseño del remuestreo se fijaron con la validación 2017-2019 antes de leer la
prueba. El script calcula primero la validación y después, una sola vez, la prueba 2020-2026; se
niega a ejecutarse de nuevo si ya existe su resultado. Informa también la precisión operativa
(todas las celdas-mes, sin remuestreo) para que no se confunda con la balanceada."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from pfc_datos.almacen import MatrizParquet
from pfc_datos.config import cargar_config, ruta_d2
from pfc_datos.modelos import RepositorioModelos
from pfc_predictiva.__main__ import VARIABLES
from pfc_predictiva.evaluacion.metricas import metricas_balanceadas, metricas_umbral

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "resultados" / "pruebas" / "c2_integracion" / "cp14_precision_balanceada.json"
UMBRAL = 0.5
REPETICIONES = 1000
CRITERIO = 0.80


def evaluar(modelo: Any, datos: pd.DataFrame, semilla: int) -> dict[str, Any]:
    """Métricas 1:1 estratificadas por año y métricas operativas por celda-mes y provincia-mes."""
    y = datos["objetivo"].to_numpy().astype("int8")
    p = modelo.predict_proba(datos[VARIABLES])[:, 1]
    anios = datos["periodo"].dt.year.to_numpy()
    prov = (
        pd.DataFrame({"prov": datos["ubigeo_prov"], "mes": datos["periodo"], "y": y, "p": p})
        .groupby(["prov", "mes"], observed=True)
        .agg(y=("y", "max"), p=("p", "max"))
    )
    return {
        "filas": len(y),
        "positivos": int(y.sum()),
        "balanceada_1a1": metricas_balanceadas(y, p, UMBRAL, anios, REPETICIONES, semilla),
        "operativa_celda_mes": metricas_umbral(y, p, UMBRAL),
        "operativa_provincia_mes": {
            "filas": len(prov),
            "positivos": int(prov["y"].sum()),
            **metricas_umbral(prov["y"].to_numpy(), prov["p"].to_numpy(), UMBRAL),
        },
    }


def main() -> None:
    if DESTINO.exists():
        sys.exit(f"La precisión 1:1 de la prueba ya se calculó: {DESTINO}")
    config = cargar_config()
    d2 = ruta_d2()
    modelo, tarjeta = RepositorioModelos(d2).cargar("XGBOOST", "1")  # verifica el SHA-256
    matriz = MatrizParquet(d2)
    columnas = ["periodo", "objetivo", "ubigeo_prov", *VARIABLES]
    resultado: dict[str, Any] = {
        "fecha": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "modelo": {"algoritmo": "XGBOOST", "version": "1", "sha256": tarjeta.sha256},
        "umbral": UMBRAL,
        "repeticiones": REPETICIONES,
        "semilla": config["semilla"],
        "criterio_precision_1a1": CRITERIO,
    }
    v0, v1 = config["particion"]["validacion"]
    resultado["validacion"] = evaluar(modelo, matriz.leer(range(v0, v1 + 1), columnas), 42)
    print(json.dumps(resultado["validacion"]["balanceada_1a1"], indent=2), flush=True)
    t0, t1 = config["particion"]["prueba"]
    resultado["prueba"] = evaluar(modelo, matriz.leer(range(t0, t1 + 1), columnas), 42)
    precision = resultado["prueba"]["balanceada_1a1"]["precision"]["media"]
    resultado["cumple"] = bool(precision >= CRITERIO)
    DESTINO.write_text(json.dumps(resultado, indent=2))
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()

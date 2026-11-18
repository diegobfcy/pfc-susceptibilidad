"""CP-14 (RNF-02): evaluación ÚNICA de la partición de prueba sellada 2020-2026.

Se niega a ejecutarse si ya existe su resultado: el modelo no puede ajustarse después de verla."""

from __future__ import annotations

import datetime as dt
import json
import math
import sys
from pathlib import Path

import numpy as np
from pfc_datos.almacen import MatrizParquet, sha256_archivo
from pfc_datos.bd import crear_motor
from pfc_datos.config import cargar_config, ruta_d2
from pfc_datos.modelos import RepositorioModelos
from pfc_predictiva.__main__ import VARIABLES
from pfc_predictiva.evaluacion.metricas import auc_roc, metricas_umbral
from scipy.stats import rankdata
from sqlalchemy import text

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "resultados" / "pruebas" / "c2_integracion" / "cp14_prueba_sellada.json"
FRACCIONES = (0.01, 0.05, 0.10, 0.20)
LIMITES = (0.25, 0.50, 0.75)


def auc_independiente(y: np.ndarray, p: np.ndarray) -> float:
    """AUC por rangos de Mann-Whitney, sin usar scikit-learn."""
    rangos = rankdata(p)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    return float((rangos[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def ic_hanley_mcneil(a: float, n1: int, n0: int) -> tuple[float, float]:
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    v = (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)
    return a - 1.96 * math.sqrt(v), a + 1.96 * math.sqrt(v)


def main() -> None:
    if DESTINO.exists():
        sys.exit(f"CP-14 ya se ejecutó: {DESTINO}")
    config = cargar_config()
    d2 = ruta_d2()
    modelos = RepositorioModelos(d2)
    modelo, tarjeta = modelos.cargar("XGBOOST", "1")  # verifica el SHA-256
    assert tarjeta.sha256 == sha256_archivo(Path(d2, "modelos", "xgboost_v1.ubj"))
    desde, hasta = config["particion"]["prueba"]
    datos = MatrizParquet(d2).leer(range(desde, hasta + 1), ["periodo", "objetivo", *VARIABLES])
    y = datos["objetivo"].to_numpy().astype("int8")
    p = modelo.predict_proba(datos[VARIABLES])[:, 1]
    auc = auc_roc(y, p)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    inferior, superior = ic_hanley_mcneil(auc, n1, n0)
    anios = datos["periodo"].dt.year.to_numpy()
    orden = np.argsort(-p, kind="stable")
    y_orden = y[orden]
    nivel = np.searchsorted(np.asarray(LIMITES), np.round(p, 4), side="right") + 1
    resultado = {
        "fecha": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "modelo": {"algoritmo": "XGBOOST", "version": "1", "estado": str(tarjeta.estado),
                   "sha256": tarjeta.sha256},
        "filas": len(y),
        "positivos": n1,
        "umbral_rnf02": config["modelo"]["umbral_auc_minimo"],
        "auc_m3": auc,
        "auc_independiente": auc_independiente(y, p),
        "ic95": [inferior, superior],
        "cumple_rnf02": bool(auc >= config["modelo"]["umbral_auc_minimo"]),
        "por_anio": {
            int(a): {
                "positivos": int(y[anios == a].sum()),
                "auc": auc_roc(y[anios == a], p[anios == a]),
            }
            for a in np.unique(anios)
            if y[anios == a].sum() > 0
        },
        "captura": {
            str(f): float(y_orden[: int(len(y) * f)].sum() / n1) for f in FRACCIONES
        },
        "positivos_por_nivel": {
            int(n): int(y[nivel == n].sum()) for n in (1, 2, 3, 4)
        },
        "filas_por_nivel": {int(n): int((nivel == n).sum()) for n in (1, 2, 3, 4)},
        "metricas_umbral_050": metricas_umbral(y, p, 0.50),
    }  # fmt: skip
    DESTINO.write_text(json.dumps(resultado, indent=2))
    motor = crear_motor()
    with motor.begin() as c:
        for nombre, valor in (("AUC_ROC", auc),) + tuple(
            (k.upper(), v) for k, v in resultado["metricas_umbral_050"].items()
        ):
            c.execute(
                text("""INSERT INTO modelo.metrica VALUES (1, 'PRUEBA', :n, :v)
                        ON CONFLICT DO NOTHING"""),
                {"n": nombre, "v": valor},
            )
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()

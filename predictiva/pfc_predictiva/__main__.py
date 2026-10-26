"""Ejecución del Sprint 4 de la capa Predictiva: búsqueda de hiperparámetros, versión
candidata de XGBoost, línea base de Random Forest y métricas de M3 (sin leer la prueba)."""

from __future__ import annotations

import json
import time
from typing import Any

import numpy as np
import pandas as pd

from pfc_datos.almacen import MatrizParquet
from pfc_datos.config import cargar_config, ruta_d2
from pfc_datos.modelos import RepositorioModelos
from pfc_predictiva.entrenamiento import busqueda, entrenador
from pfc_predictiva.entrenamiento.clasificadores import crear_random_forest
from pfc_predictiva.entrenamiento.particion import bloques_espaciales, submuestrear_negativos
from pfc_predictiva.evaluacion.metricas import auc_roc, curva_roc, psi

VARIABLES = [
    "tsm_c", "anom_tsm", "anom_tsm_l1", "anom_tsm_l2", "anom_tsm_l3", "anom_tsm_mm3",
    "precip_mes_mm", "precip_max3d_mm", "precip_ant90_mm",
    "pend_media_g", "pend_p90_g", "pend_max_g", "mes",
]


def resumen_particion(matriz: MatrizParquet, config: dict[str, Any]) -> list[dict[str, Any]]:
    p = config["particion"]
    conjuntos = [
        ("Entrenamiento", range(2000, p["fin_entrenamiento"] + 1)),
        ("Validacion", range(p["validacion"][0], p["validacion"][1] + 1)),
        ("Prueba", range(p["prueba"][0], p["prueba"][1] + 1)),
    ]
    filas = []
    for nombre, anios in conjuntos:
        tabla = matriz.leer(anios, ["periodo", "objetivo"])  # solo conteos; sin variables
        filas.append({"conjunto": nombre, "desde": anios.start, "hasta": anios.stop - 1,
                      "meses": int(tabla["periodo"].nunique()), "filas": len(tabla),
                      "positivos": int(tabla["objetivo"].sum())})
    return filas


def importancia_relativa(ganancia: dict[str, float]) -> dict[str, float]:
    total = sum(ganancia.values())
    return {v: ganancia.get(v, 0.0) / total for v in VARIABLES}


def main() -> None:
    config = cargar_config()
    semilla = config["semilla"]
    d2 = ruta_d2()
    matriz = MatrizParquet(d2)
    resultado: dict[str, Any] = {"particion": resumen_particion(matriz, config)}

    datos = matriz.leer(range(2000, entrenador.ANIOS_VALIDACION[1] + 1))
    anio = datos["periodo"].dt.year
    entreno = datos[anio <= entrenador.ANIO_FIN_ENTRENO].reset_index(drop=True)
    valid = datos[anio.between(*entrenador.ANIOS_VALIDACION)]
    celdas = pd.read_parquet(d2 / "celdas.parquet")
    bloque = bloques_espaciales(celdas, config["modelo"]["bloque_espacial_km"])
    bloque_filas = bloque.loc[entreno["id_celda"]].to_numpy()
    resultado["bloques"] = int(np.unique(bloque_filas).size)

    b = busqueda.buscar(entreno, VARIABLES, bloque_filas, config, semilla)
    resultado["busqueda"] = {k: v for k, v in b.items() if k != "pliegues"}

    t0 = time.perf_counter()
    version = entrenador.entrenar_version(datos, VARIABLES, b["params"], RepositorioModelos(d2))
    t_xgb = time.perf_counter() - t0
    modelo, _ = RepositorioModelos(d2).cargar("XGBOOST", "1")
    p_xgb = modelo.predict_proba(valid[VARIABLES])[:, 1]

    fraccion = config["modelo"]["submuestreo_negativos_busqueda"]
    aucs_rf = busqueda.validacion_cruzada_rf(entreno, VARIABLES, b["pliegues"], fraccion, semilla)
    t0 = time.perf_counter()
    parte = submuestrear_negativos(entreno, fraccion, semilla)
    rf = crear_random_forest(semilla).fit(parte[VARIABLES], parte["objetivo"])
    t_rf = time.perf_counter() - t0
    reg_rf = RepositorioModelos(d2).guardar(rf, "RANDOM_FOREST", "1", version.estado.__class__("REVISION"))
    p_rf = rf.predict_proba(valid[VARIABLES])[:, 1]

    y_val = valid["objetivo"].to_numpy()
    resultado["xgboost"] = {
        "params": b["params"], "auc_cv": b["auc_cv"], "auc_cv_std": b["auc_cv_std"],
        "auc_validacion": auc_roc(y_val, p_xgb), "segundos_final": round(t_xgb, 1),
        "bytes": version.bytes, "sha256": version.sha256, "estado": version.estado,
        "importancia": importancia_relativa(version.importancia), "roc": curva_roc(y_val, p_xgb),
    }
    resultado["random_forest"] = {
        "auc_cv": float(np.mean(aucs_rf)), "auc_cv_std": float(np.std(aucs_rf)),
        "auc_validacion": auc_roc(y_val, p_rf), "segundos_final": round(t_rf, 1),
        "bytes": reg_rf.bytes, "roc": curva_roc(y_val, p_rf),
    }
    resultado["psi_entreno_validacion"] = {
        v: psi(entreno[v], valid[v], version.referencia_psi[v]) for v in entrenador.VARIABLES_DERIVA
    }
    resultado["prevalencia_entreno"] = float(entreno["objetivo"].mean())
    (d2 / "entrenamiento_v1.json").write_text(json.dumps(resultado, indent=2, default=str))
    print(json.dumps({k: v for k, v in resultado.items() if k not in ("busqueda",)},
                     indent=2, default=str)[:4000])


if __name__ == "__main__":
    main()

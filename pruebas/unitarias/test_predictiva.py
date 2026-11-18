"""M1, M2 y M3 sobre una matriz sintética pequeña (XGBoost en CPU, sin GPU)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pfc_datos.modelos import EstadoVersion, IntegridadArtefactoError, RepositorioModelos
from pfc_predictiva.entrenamiento import busqueda, entrenador, particion
from pfc_predictiva.evaluacion import metricas
from pfc_predictiva.inferencia.inferencia import clasificar, inferir

VARIABLES = ["precip_mes_mm", "precip_max3d_mm", "precip_ant90_mm", "anom_tsm", "pend_p90_g"]


@pytest.fixture(autouse=True)
def _cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PFC_DISPOSITIVO_XGB", "cpu")


@pytest.fixture(scope="module")
def matriz() -> pd.DataFrame:
    """40 celdas en 8 bloques de 50 km, 2014-2020; la lluvia explica el objetivo."""
    rng = np.random.default_rng(42)
    celdas = pd.DataFrame(
        {
            "id_celda": np.arange(40, dtype="int32"),
            "x": (np.arange(40) % 8) * 50_000.0 + 500,
            "y": (np.arange(40) // 8) * 1_000.0,
            "ubigeo_prov": np.where(np.arange(40) < 20, "2001", "2002"),
        }
    )
    periodos = pd.date_range("2014-01-01", "2020-12-01", freq="MS")
    m = celdas.merge(pd.DataFrame({"periodo": periodos}), how="cross")
    for v in VARIABLES:
        m[v] = rng.gamma(2.0, 10.0, len(m)).astype("float32")
    riesgo = m["precip_max3d_mm"] + m["precip_ant90_mm"] + rng.normal(0, 5, len(m))
    m["objetivo"] = (riesgo > np.quantile(riesgo, 0.97)).astype("int8")
    return m


@pytest.fixture
def config() -> dict[str, Any]:
    return {
        "modelo": {
            "pliegues": 3,
            "submuestreo_negativos_busqueda": 0.5,
            "grilla": {"max_depth": [2, 3], "learning_rate": [0.1], "min_child_weight": [1]},
        }
    }


def test_bloques_y_pliegues_separan_celdas(matriz: pd.DataFrame) -> None:
    celdas = matriz.drop_duplicates("id_celda")
    bloque = particion.bloques_espaciales(celdas, 50)
    assert bloque.nunique() == 8
    por_fila = bloque.reindex(matriz["id_celda"]).to_numpy()
    for i_tr, i_va in particion.pliegues_espaciales(por_fila, 3):
        assert not set(por_fila[i_tr]) & set(por_fila[i_va])


def test_submuestreo_conserva_todos_los_positivos(matriz: pd.DataFrame) -> None:
    parte = particion.submuestrear_negativos(matriz, 0.1, 42)
    assert parte["objetivo"].sum() == matriz["objetivo"].sum()
    assert len(parte) < 0.2 * len(matriz)


def test_busqueda_elige_por_auc_y_fija_arboles(
    matriz: pd.DataFrame, config: dict[str, Any]
) -> None:
    entreno = matriz[matriz["periodo"].dt.year <= 2016].reset_index(drop=True)
    celdas = matriz.drop_duplicates("id_celda")
    bloque = particion.bloques_espaciales(celdas, 50).reindex(entreno["id_celda"]).to_numpy()
    r = busqueda.buscar(entreno, VARIABLES, bloque, config, 42)
    assert len(r["tabla"]) == 2 and r["auc_cv"] > 0.8
    assert r["params"]["n_estimators"] >= 1
    aucs = busqueda.validacion_cruzada_rf(entreno, VARIABLES, r["pliegues"], 0.5, 42)
    assert len(aucs) == 3 and min(aucs) > 0.7


def test_entrenar_version_candidata_y_registro(matriz: pd.DataFrame, tmp_path: Path) -> None:
    modelos = RepositorioModelos(tmp_path)
    params = {"max_depth": 3, "learning_rate": 0.1, "min_child_weight": 1, "n_estimators": 30}
    v = entrenador.entrenar_version(matriz, VARIABLES, params, modelos)
    assert v.estado == EstadoVersion.CANDIDATA and v.metricas["auc_validacion"] >= 0.8
    assert set(v.referencia_psi) == set(entrenador.VARIABLES_DERIVA)
    modelo, registro = modelos.cargar("XGBOOST", "1")
    assert registro.sha256 == v.sha256 and modelo.predict_proba(matriz[VARIABLES][:5]).shape == (
        5,
        2,
    )


def test_version_bajo_el_umbral_se_rechaza(matriz: pd.DataFrame, tmp_path: Path) -> None:
    ruido = matriz.copy()
    ruido["objetivo"] = np.random.default_rng(1).permutation(ruido["objetivo"].to_numpy())
    params = {"max_depth": 2, "learning_rate": 0.1, "min_child_weight": 1, "n_estimators": 5}
    v = entrenador.entrenar_version(ruido, VARIABLES, params, RepositorioModelos(tmp_path))
    assert v.estado == EstadoVersion.RECHAZADA


def test_artefacto_alterado_se_detecta(tmp_path: Path) -> None:
    from sklearn.dummy import DummyClassifier

    modelos = RepositorioModelos(tmp_path)
    clf = DummyClassifier(strategy="prior").fit([[0], [1]], [0, 1])
    v = modelos.guardar(clf, "RANDOM_FOREST", "1", EstadoVersion.CANDIDATA)
    assert modelos.cargar("RANDOM_FOREST", "1")[1].bytes == v.bytes
    with Path(v.ruta_artefacto).open("ab") as f:
        f.write(b"x")
    with pytest.raises(IntegridadArtefactoError):
        modelos.cargar("RANDOM_FOREST", "1")


class _LectorMemoria:
    def __init__(self, matriz: pd.DataFrame) -> None:
        self._m = matriz

    def leer(self, anios: range, columnas: list[str]) -> pd.DataFrame:
        return self._m[self._m["periodo"].dt.year.isin(anios)][columnas].copy()


def test_inferencia_por_anio_y_niveles(matriz: pd.DataFrame, tmp_path: Path) -> None:
    modelos = RepositorioModelos(tmp_path)
    params = {"max_depth": 2, "learning_rate": 0.1, "min_child_weight": 1, "n_estimators": 10}
    entrenador.entrenar_version(matriz, VARIABLES, params, modelos)
    lotes = list(
        inferir(_LectorMemoria(matriz), modelos, "XGBOOST", "1", range(2019, 2021), VARIABLES)
    )
    assert len(lotes) == 2 and lotes[0]["probabilidad"].between(0, 1).all()
    niveles = clasificar(np.array([0.01, 0.2, 0.5, 0.9]), [0.1, 0.3, 0.7])
    assert niveles.tolist() == [1, 2, 3, 4]


def test_metricas_y_psi() -> None:
    y = np.array([0, 0, 1, 1])
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert metricas.auc_roc(y, p) == pytest.approx(0.75)
    curva = metricas.curva_roc(y, p, puntos=5)
    assert curva["fpr"][0] == 0 and curva["tpr"][-1] == 1
    m = metricas.metricas_umbral(y, p, 0.5)
    assert m["precision"] == 1.0 and m["recall"] == 0.5
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(0, 1, 5000))
    cortes = metricas.deciles_referencia(ref)
    assert len(cortes) == 9
    assert metricas.psi(ref, pd.Series(rng.normal(0, 1, 5000)), cortes) < 0.1
    assert metricas.psi(ref, pd.Series(rng.normal(1.5, 1, 5000)), cortes) > 0.25


def test_metricas_balanceadas_uno_a_uno_por_grupo() -> None:
    rng = np.random.default_rng(1)
    y = np.zeros(4000, dtype=int)
    y[:40] = 1
    grupos = np.repeat([2020, 2021], 2000)
    y[2000:2010] = 1  # 40 positivos en 2020 y 10 en 2021
    p = np.where(y == 1, 0.9, rng.uniform(0, 1, len(y)))
    r = metricas.metricas_balanceadas(y, p, 0.5, grupos, repeticiones=200, semilla=42)
    assert r["recall"]["media"] == 1.0  # todos los positivos se conservan
    # Con la mitad de los negativos sobre el umbral, la precisión 1:1 ronda 1 / 1.5.
    assert r["precision"]["media"] == pytest.approx(1 / 1.5, abs=0.05)
    assert r["precision"]["ic95_inf"] <= r["precision"]["media"] <= r["precision"]["ic95_sup"]
    assert r == metricas.metricas_balanceadas(y, p, 0.5, grupos, repeticiones=200, semilla=42)

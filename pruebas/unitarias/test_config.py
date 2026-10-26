"""Configuración central y rutas de D2."""

from __future__ import annotations

from pathlib import Path

import pytest
from pfc_datos import config


def test_config_del_repositorio_tiene_particion_y_umbral() -> None:
    c = config.cargar_config()
    assert c["modelo"]["umbral_auc_minimo"] == 0.80
    assert c["deriva"]["psi_alerta"] > c["deriva"]["psi_vigilancia"]


def test_rutas_desde_variables_de_entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PFC_DATOS_ORIGEN", str(tmp_path / "origen"))
    monkeypatch.setenv("PFC_D2", str(tmp_path / "d2"))
    assert config.ruta_datos_origen() == tmp_path / "origen"
    assert config.ruta_d2().is_dir()

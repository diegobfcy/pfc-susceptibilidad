"""D2/D3: huellas, catálogo, matriz Parquet y bitácora de solo inserción."""

import json
from pathlib import Path

import pandas as pd
import pytest

from pfc_datos.almacen import AlmacenArchivos, MatrizParquet, sha256_archivo
from pfc_datos.bitacora import BitacoraArchivo
from pfc_etl.conectores.carga_manual import CargaManual, ExtensionNoPermitidaError


def test_registro_y_verificacion_de_huella(tmp_path: Path) -> None:
    almacen = AlmacenArchivos(tmp_path)
    tmp = almacen.ruta_temporal("ersst_v5", "serie.ascii")
    tmp.write_text("1 2 3")
    registro = almacen.registrar("ersst_v5", tmp, sha256_archivo(tmp))
    assert registro.ruta.name == "serie.ascii" and almacen.verificar(registro.ruta)
    registro.ruta.write_text("alterado")
    assert not almacen.verificar(registro.ruta)


def test_matriz_parquet_por_anio(tmp_path: Path) -> None:
    matriz = MatrizParquet(tmp_path)
    for anio in (2019, 2020):
        matriz.escribir_anio(anio, pd.DataFrame({"id_celda": [1, 2], "anio": anio}))
    assert matriz.anios_disponibles() == [2019, 2020]
    assert len(matriz.leer(range(2020, 2021))) == 2


def test_bitacora_rechaza_tipos_no_permitidos(tmp_path: Path) -> None:
    b = BitacoraArchivo(tmp_path / "b.jsonl")
    b.registrar("INFORMATIVO", "E1", "ok", n=1)
    with pytest.raises(ValueError):
        b.registrar("DEBUG", "E1", "x")
    assert json.loads((tmp_path / "b.jsonl").read_text())["detalle"] == {"n": 1}


def test_carga_manual(tmp_path: Path, bitacora: object) -> None:
    origen = tmp_path / "manual.csv"
    origen.write_text("a,b\n1,2\n")
    almacen = AlmacenArchivos(tmp_path / "d2")
    registro = CargaManual("inventario", almacen, bitacora).cargar(origen)
    assert registro.sha256 == sha256_archivo(origen)
    with pytest.raises(ExtensionNoPermitidaError):
        CargaManual("inventario", almacen, bitacora).cargar(tmp_path / "x.exe")

"""Caja blanca de los casos críticos: CP-03, CP-05, CP-06, CP-12 y validación de S1/S2."""

from __future__ import annotations

import io
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pfc_etl.conectores.base import HostNoPermitidoError
from pfc_etl.conectores.ersst import ConectorErsst
from pfc_etl.verificacion.verificador import verificar_dataset
from pfc_predictiva.inferencia.inferencia import ProbabilidadInvalidaError, clasificar
from pfc_servicios.seguridad.archivos import ArchivoRechazadoError, comprobar_archivo

LIMITES = [0.25, 0.50, 0.75]
REGLAS_PENDIENTE = {
    "columnas": ["id_celda", "pend_media_g"],
    "rango": {"pend_media_g": [0.0, 90.0]},
}


@pytest.mark.parametrize(
    ("probabilidad", "nivel"),
    [
        (0.0, 1),
        (0.2499, 1),
        (0.25, 2),
        (0.4999, 2),
        (0.50, 3),
        (0.7499, 3),
        (0.75, 4),
        (1.0, 4),
    ],
)
def test_cp12_fronteras_de_nivel(probabilidad: float, nivel: int) -> None:
    assert clasificar(np.array([probabilidad]), LIMITES)[0] == nivel


@pytest.mark.parametrize("probabilidad", [-0.0001, 1.0001, float("nan")])
def test_cp12_rechaza_fuera_de_rango(probabilidad: float) -> None:
    with pytest.raises(ProbabilidadInvalidaError):
        clasificar(np.array([0.5, probabilidad]), LIMITES)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/x",
        "https://www.cpc.ncep.noaa.gov.evil.example.com/x",
        "http://www.cpc.ncep.noaa.gov/x",
        "https://www.cpc.ncep.noaa.gov@evil.example.com/x",
    ],
)
def test_cp03_lista_blanca_rechaza_sin_conectar(url: str, almacen: Any, bitacora: Any) -> None:
    conector = ConectorErsst(frozenset({"www.cpc.ncep.noaa.gov"}), almacen, bitacora)
    with pytest.raises(HostNoPermitidoError):
        conector._validar_host(url)


def test_cp03_lista_blanca_acepta_dominio_oficial(almacen: Any, bitacora: Any) -> None:
    conector = ConectorErsst(frozenset({"www.cpc.ncep.noaa.gov"}), almacen, bitacora)
    conector._validar_host("https://www.cpc.ncep.noaa.gov/data/indices/x.ascii")


def test_cp05_nulos_y_campos_faltantes() -> None:
    tabla = pd.DataFrame(
        {"id_celda": [1, 2, 3, 4], "pend_media_g": [10.0, None, 30.0, 40.0]},
    )
    resultado = verificar_dataset("dem", tabla, REGLAS_PENDIENTE, 1e-9)
    assert resultado.filas == 4 and len(resultado.validos) == 3
    assert sum(resultado.rechazados.values()) == 1
    sin_campo = verificar_dataset("dem", tabla[["id_celda"]], REGLAS_PENDIENTE, 1e-9)
    assert not sin_campo.es_valido


def test_cp06_valores_limite_de_pendiente() -> None:
    valores = [-0.01, 0.0, 90.0, 90.01]
    tabla = pd.DataFrame({"id_celda": range(4), "pend_media_g": valores})
    validos = verificar_dataset("dem", tabla, REGLAS_PENDIENTE, 1e-9).validos
    assert sorted(validos["pend_media_g"]) == [0.0, 90.0]


def test_cp06_precipitacion_negativa_se_rechaza() -> None:
    reglas = {"columnas": ["fecha", "id_pixel", "p1"], "rango": {"p1": [0.0, 500.0]}}
    fechas = pd.date_range("2023-03-01", periods=2)
    tabla = pd.DataFrame({"fecha": fechas, "id_pixel": 1, "p1": [-1.0, 5.0]})
    assert len(verificar_dataset("era5", tabla, reglas, 1e-9).validos) == 1


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("virus.exe", b"MZ\x90\x00"),
        ("sin_extension", b"CDF\x01"),
        ("falso.nc", b"MZ\x90\x00 no es NetCDF"),
        ("falso.csv", b"a,b\x00c"),
        ("vacio.csv", b""),
        ("falso.tif", b"no es tiff"),
    ],
)
def test_cp04_archivos_rechazados(nombre: str, contenido: bytes) -> None:
    with pytest.raises(ArchivoRechazadoError):
        comprobar_archivo(nombre, io.BytesIO(contenido))


@pytest.mark.parametrize(
    ("nombre", "contenido"),
    [
        ("a.nc", b"CDF\x01resto"),
        ("a.nc", b"\x89HDF\r\n\x1a\nresto"),
        ("a.tif", b"II*\x00resto"),
        ("a.gpkg", b"SQLite format 3\x00resto"),
        ("a.csv", b"a,b\n1,2\n"),
    ],
)
def test_cp04_archivos_aceptados(nombre: str, contenido: bytes) -> None:
    flujo = io.BytesIO(contenido)
    comprobar_archivo(nombre, flujo)
    assert flujo.tell() == 0  # el flujo queda listo para guardarse

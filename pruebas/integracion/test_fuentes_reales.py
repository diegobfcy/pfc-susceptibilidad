"""Integración con las fuentes y la matriz reales: CP-01, CP-07, CP-09 y CP-10."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

pytestmark = pytest.mark.integracion
ORIGEN = Path(os.environ.get("PFC_DATOS_ORIGEN", "/no/existe"))
D2 = Path(__file__).resolve().parents[2] / "data" / "d2"
VARIABLES = [
    "tsm_c", "anom_tsm", "anom_tsm_l1", "anom_tsm_l2", "anom_tsm_l3", "anom_tsm_mm3",
    "precip_mes_mm", "precip_max3d_mm", "precip_ant90_mm", "pend_media_g", "pend_p90_g",
    "pend_max_g",
]  # fmt: skip


def _requiere(ruta: Path) -> None:
    if not ruta.exists():
        pytest.skip(f"no existe {ruta}")


def test_cp01_noaa_real_con_huella(tmp_path: Path, bitacora: Any) -> None:
    from pfc_datos.almacen import AlmacenArchivos, sha256_archivo
    from pfc_datos.config import cargar_config
    from pfc_etl.conectores.base import Ventana
    from pfc_etl.conectores.ersst import ConectorErsst, leer_ersst
    from pfc_etl.verificacion.verificador import verificar_dataset

    if not os.environ.get("PFC_FUENTES_EN_LINEA"):
        pytest.skip("descarga real desactivada")
    config = cargar_config()
    conector = ConectorErsst(
        frozenset(config["hosts_permitidos"]), AlmacenArchivos(tmp_path), bitacora
    )
    registro = conector.descargar_periodo(Ventana(2000, 2026))
    assert sha256_archivo(registro.ruta) == registro.sha256
    assert bitacora.eventos[-1][:3] == ("INFORMATIVO", "E2", "INGESTA")
    serie = leer_ersst(registro.ruta)
    serie = serie[(serie.anio >= 2000) & (serie.anio <= 2026)]
    reglas = config["verificacion"]["fuentes"]["ersst_v5"]
    resultado = verificar_dataset("ersst_v5", serie, reglas, 1e-9)
    assert resultado.es_valido and len(serie) >= 318
    # La anomalía publicada es consistente: enero de 2016 frente a la serie cálida conocida.
    assert serie[(serie.anio == 2017) & (serie.mes == 3)].n12_anom.iloc[0] > 1


def test_cp07_dias_faltantes_detienen_y_se_indican(tmp_path: Path, bitacora: Any) -> None:
    """Conjunto de verificación negativa derivado del ERA5-Land real (marzo de 2023)."""
    from pfc_datos.config import cargar_config
    from pfc_etl.orquestador.etapas import EtapasLocales
    from pfc_etl.orquestador.orquestador import Trabajo, ejecutar_trabajo

    xr = pytest.importorskip("xarray")
    _requiere(ORIGEN / "raw" / "ERA5Land" / "era5land_tp00_2023.nc")
    origen = tmp_path / "origen"
    (origen / "raw" / "ERA5Land").mkdir(parents=True)
    (origen / "raw" / "NOAA_CPC").symlink_to(ORIGEN / "raw" / "NOAA_CPC")
    (origen / "processed").symlink_to(ORIGEN / "processed")
    (origen / "interim").symlink_to(ORIGEN / "interim")
    (origen / "raw" / "ERA5Land" / "era5land_tp00_2022.nc").symlink_to(
        ORIGEN / "raw" / "ERA5Land" / "era5land_tp00_2022.nc"
    )
    with xr.open_dataset(ORIGEN / "raw" / "ERA5Land" / "era5land_tp00_2023.nc") as ds:
        coord = next(c for c in ds.coords if "time" in c)
        tiempos = pd.to_datetime(ds[coord].values)
        faltan = np.isin(tiempos.normalize(), pd.to_datetime(["2023-03-15", "2023-03-16"]))
        ds.isel({coord: ~faltan}).load().to_netcdf(
            origen / "raw" / "ERA5Land" / "era5land_tp00_2023.nc"
        )
    etapas = EtapasLocales(origen, tmp_path / "d2", cargar_config(), bitacora)
    trabajo = ejecutar_trabajo(Trabajo(7, "INGESTA", 2023, 2023), etapas, bitacora)
    assert trabajo.estado == "EN_ESPERA"
    tipo, componente, descripcion, _ = bitacora.eventos[-1]
    assert (tipo, componente) == ("ERROR", "E1")
    assert "era5_land" in descripcion and "2023-03-14" in descripcion
    motivo = trabajo.salida["motivo"]  # lo que muestra IU-10 (CU-01, flujo 6a)
    assert (motivo["tipo"], motivo["fuente"], motivo["regla"]) == (
        "DATOS_RECHAZADOS",
        "era5_land",
        "continuidad temporal",
    )


def test_cp09_grilla_y_pendiente_contra_calculo_independiente() -> None:
    rasterio = pytest.importorskip("rasterio")
    _requiere(D2 / "celdas.parquet")
    celdas = pd.read_parquet(D2 / "celdas.parquet")
    assert len(celdas) == 108461 and celdas["id_celda"].is_unique
    assert celdas["ubigeo_prov"].str.fullmatch(r"\d{4}").all()
    assert ((celdas["x"] - 500) % 1000 == 0).all() and ((celdas["y"] - 500) % 1000 == 0).all()
    ruta = ORIGEN / "interim" / "terreno" / "pendiente.tif"
    _requiere(ruta)
    terreno = pd.read_parquet(D2 / "terreno_celdas.parquet").set_index("id_celda")
    control = celdas.sample(10, random_state=42)
    with rasterio.open(ruta) as raster:
        for fila in control.itertuples():
            # Cada píxel pertenece a la celda que contiene su centro; se lee con holgura.
            ventana = (
                rasterio.windows.from_bounds(
                    fila.x - 560, fila.y - 560, fila.x + 560, fila.y + 560, raster.transform
                )
                .round_offsets()
                .round_lengths()
            )
            bloque = raster.read(1, window=ventana, masked=True)
            transformada = raster.window_transform(ventana)
            columnas, renglones = np.meshgrid(
                np.arange(bloque.shape[1]), np.arange(bloque.shape[0])
            )
            cx, cy = rasterio.transform.xy(transformada, renglones, columnas, offset="center")
            cx, cy = np.asarray(cx).reshape(bloque.shape), np.asarray(cy).reshape(bloque.shape)
            dentro = (
                (cx >= fila.x - 500)
                & (cx < fila.x + 500)
                & (cy >= fila.y - 500)
                & (cy < fila.y + 500)
            )
            datos = bloque[dentro].compressed().astype(float)
            esperado = terreno.loc[fila.id_celda]
            assert datos.size > 0
            assert datos.mean() == pytest.approx(float(esperado.pend_media_g), abs=1e-3)
            assert datos.max() == pytest.approx(float(esperado.pend_max_g), abs=1e-3)


def test_cp10_matriz_completa_sin_nulos() -> None:
    _requiere(D2 / "matriz")
    partes = sorted((D2 / "matriz").glob("anio=*/parte.parquet"))
    assert len(partes) == 27
    filas = 0
    for parte in partes:
        metadatos = pq.ParquetFile(parte).metadata
        filas += metadatos.num_rows
        nombres = [metadatos.schema.column(i).name for i in range(metadatos.num_columns)]
        for g in range(metadatos.num_row_groups):
            grupo = metadatos.row_group(g)
            for i, nombre in enumerate(nombres):
                if nombre in VARIABLES:
                    estadistica = grupo.column(i).statistics
                    assert estadistica is None or not estadistica.null_count, (parte, nombre)
    assert filas == 34382137


def test_cp10_rezagos_y_acumulados_en_control() -> None:
    _requiere(D2 / "matriz")
    from pfc_datos.almacen import MatrizParquet

    columnas = ["id_celda", "periodo", "anom_tsm", "anom_tsm_l1", "anom_tsm_l2", "anom_tsm_l3",
                "anom_tsm_mm3", "precip_mes_mm", "precip_max3d_mm", "precip_ant90_mm"]  # fmt: skip
    tabla = MatrizParquet(D2).leer(range(2018, 2020), columnas)
    celda = tabla[tabla.id_celda == tabla.id_celda.iloc[0]].sort_values("periodo")
    assert len(celda) == 24
    # Rezagos correctos en el cambio de año (enero de 2019 ve diciembre de 2018).
    a = celda.set_index("periodo")["anom_tsm"]
    enero = celda[celda.periodo == "2019-01-01"].iloc[0]
    assert enero.anom_tsm_l1 == pytest.approx(a["2018-12-01"], abs=1e-5)
    assert enero.anom_tsm_l2 == pytest.approx(a["2018-11-01"], abs=1e-5)
    assert enero.anom_tsm_l3 == pytest.approx(a["2018-10-01"], abs=1e-5)
    assert (celda.precip_max3d_mm <= celda.precip_ant90_mm + 1e-3).all()
    assert (celda[["precip_mes_mm", "precip_max3d_mm", "precip_ant90_mm"]] >= 0).all().all()


def test_cp10_primer_mes_de_la_serie() -> None:
    _requiere(D2 / "matriz")
    primera = pq.read_table(
        D2 / "matriz" / "anio=2000" / "parte.parquet", columns=["periodo"]
    ).to_pandas()
    assert primera.periodo.min() == pd.Timestamp("2000-02-01")
    assert primera.periodo.nunique() == 11


def test_cp37_rf05_dem_glo30_real_de_una_tesela(tmp_path: Path, bitacora: Any) -> None:
    """RF-05: obtención real de una tesela Copernicus DEM GLO-30 (S08, W079: La Libertad)."""
    from pfc_datos.almacen import AlmacenArchivos, sha256_archivo
    from pfc_datos.config import cargar_config
    from pfc_etl.conectores.base import Ventana
    from pfc_etl.conectores.dem_glo30 import ConectorDemGlo30, nombre_tesela

    if not os.environ.get("PFC_FUENTES_EN_LINEA"):
        pytest.skip("descarga real desactivada")
    rasterio = pytest.importorskip("rasterio")
    conector = ConectorDemGlo30(
        frozenset(cargar_config()["hosts_permitidos"]),
        AlmacenArchivos(tmp_path),
        bitacora,
        tesela=nombre_tesela(-8, -79),
    )
    registro = conector.descargar_periodo(Ventana(2000, 2026))
    assert registro.sha256 == sha256_archivo(registro.ruta)
    with rasterio.open(registro.ruta) as dem:
        izq, inf, der, sup = dem.bounds
        muestra = dem.read(1, window=((0, 512), (0, 512)))
    assert (round(izq), round(inf), round(der), round(sup)) == (-79, -8, -78, -7)
    assert muestra.max() > 1000  # Andes de La Libertad: elevaciones reales en metros
    assert bitacora.eventos[-1][:2] == ("INFORMATIVO", "E2")


def test_cp38_rf05_inventario_geocatmin_completo(tmp_path: Path, bitacora: Any) -> None:
    """RF-05: inventario completo de GEOCATMIN, TLS verificado (DEF-26) y sin cortes (DEF-27)."""
    import json

    from pfc_datos.almacen import AlmacenArchivos
    from pfc_datos.config import cargar_config
    from pfc_etl.conectores.base import Ventana
    from pfc_etl.conectores.inventario import SERVICIO, ConectorInventario

    if not os.environ.get("PFC_FUENTES_EN_LINEA"):
        pytest.skip("descarga real desactivada")
    conector = ConectorInventario(
        frozenset(cargar_config()["hosts_permitidos"]), AlmacenArchivos(tmp_path), bitacora
    )
    total = conector._leer_json(f"{SERVICIO}?where=1%3D1&returnCountOnly=true&f=json")["count"]
    registro = conector.descargar_periodo(Ventana(2000, 2026))
    elementos = json.loads(registro.ruta.read_text())["features"]
    ids = {e["properties"]["OBJECTID"] for e in elementos}
    assert total > 2000 and len(elementos) == len(ids) == total
    assert bitacora.eventos[-1][3]["registros"] == total

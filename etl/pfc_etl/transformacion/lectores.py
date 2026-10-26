"""E4. Lectura de los archivos registrados en D2 a tablas normalizadas."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PRECISION = {"D1": "DIA", "D2": "MES", "D3": "ANIO"}


def leer_era5_diario(archivos: list[Path], pixeles: pd.DataFrame) -> pd.DataFrame:
    """Precipitación diaria (mm) en los centros de los píxeles de 0.1°.

    El valor de las 00 UTC del día D+1 es el total del día D. Los píxeles costeros sin
    dato (máscara tierra-mar) toman el valor del píxel terrestre válido más cercano."""
    import xarray as xr
    from scipy.spatial import cKDTree

    ds = xr.open_mfdataset([str(a) for a in archivos], combine="by_coords")
    tiempo = "valid_time" if "valid_time" in ds.dims else "time"
    tp = ds["tp"].sel(
        latitude=xr.DataArray(pixeles["lat"].to_numpy(), dims="p"),
        longitude=xr.DataArray(pixeles["lon"].to_numpy(), dims="p"),
        method="nearest",
        tolerance=0.02,
    ).load()
    fechas = pd.to_datetime(tp[tiempo].to_numpy()).normalize() - pd.Timedelta(days=1)
    ancho = pd.DataFrame(tp.to_numpy() * 1000.0, index=fechas, columns=pixeles["id_pixel"])
    ancho = ancho[~ancho.index.duplicated()].sort_index()
    vacios = ancho.columns[ancho.isna().all()]
    validos = ancho.columns[~ancho.isna().all()]
    if len(vacios):
        xy = pixeles.set_index("id_pixel")[["lon", "lat"]]
        _, cercano = cKDTree(xy.loc[validos].to_numpy()).query(xy.loc[vacios].to_numpy())
        for columna, j in zip(vacios, cercano, strict=True):
            ancho[columna] = ancho[validos[j]].to_numpy()
    largo = ancho.rename_axis("fecha").reset_index().melt(
        id_vars="fecha", var_name="id_pixel", value_name="precip_mm"
    )
    largo["precip_mm"] = largo["precip_mm"].astype("float32")
    largo.attrs["pixeles_imputados"] = len(vacios)
    return largo


def leer_celdas(ruta: Path) -> pd.DataFrame:
    import geopandas as gpd

    celdas = gpd.read_file(ruta, ignore_geometry=True)
    celdas["ubigeo_prov"] = celdas["ubigeo"].str[2:6]
    return pd.DataFrame(celdas[["id_celda", "id_pixel", "ubigeo_prov", "x", "y"]])


def leer_pixeles(ruta: Path) -> pd.DataFrame:
    import geopandas as gpd

    return pd.DataFrame(gpd.read_file(ruta, ignore_geometry=True)[["id_pixel", "lon", "lat"]])


def leer_eventos(ruta: Path) -> pd.DataFrame:
    import geopandas as gpd

    eventos = gpd.read_file(ruta, ignore_geometry=True)
    return pd.DataFrame(
        {
            "event_uid": eventos["event_uid"],
            "fecha": pd.to_datetime(eventos["fecha"]),
            "date_precision": eventos["date_precision"],
            "precision_fecha": eventos["date_precision"].map(PRECISION).fillna("NULA"),
            "id_celda": eventos["id_celda"].astype("float64"),
        }
    )


def a_int(serie: pd.Series) -> np.ndarray:
    return serie.astype("int64").to_numpy()

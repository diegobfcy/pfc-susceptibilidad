"""E4. Variables de terreno por celda de análisis a partir de la pendiente a 30 m (DEM GLO-30).

Recorre el ráster por bloques de filas y acumula por celda la suma, el máximo y el
histograma de la pendiente (1°), del que se obtiene el percentil 90."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

TAM_CELDA_M = 1000
FILAS_BLOQUE = 512
CLASES_PENDIENTE = 91


def tabla_celdas(celdas: pd.DataFrame) -> tuple[np.ndarray, float, float]:
    """Matriz de búsqueda (fila, columna) -> índice de celda de la grilla de 1 km."""
    x0 = (celdas["x"] - TAM_CELDA_M / 2).min()
    y0 = (celdas["y"] - TAM_CELDA_M / 2).min()
    ix = ((celdas["x"] - TAM_CELDA_M / 2 - x0) / TAM_CELDA_M).round().astype(int).to_numpy()
    iy = ((celdas["y"] - TAM_CELDA_M / 2 - y0) / TAM_CELDA_M).round().astype(int).to_numpy()
    busqueda = np.full((iy.max() + 1, ix.max() + 1), -1, dtype=np.int64)
    busqueda[iy, ix] = np.arange(len(celdas))
    return busqueda, x0, y0


def percentil_histograma(histograma: np.ndarray, q: float) -> np.ndarray:
    """Percentil q de cada fila de un histograma de pendiente por clases de 1°.

    Devuelve la primera clase en la que el acumulado alcanza la fracción q del total; las filas
    vacías dan 0.
    """
    acumulado = np.cumsum(histograma, axis=1)
    total = np.maximum(acumulado[:, -1:], 1)
    return np.argmax(acumulado >= q * total, axis=1).astype("float32")


def variables_terreno(celdas: pd.DataFrame, ruta_pendiente: Path) -> pd.DataFrame:
    """celdas: id_celda, x, y (EPSG:32717). Devuelve pend_media_g, pend_p90_g y pend_max_g."""
    import rasterio
    from rasterio.windows import Window

    busqueda, x0, y0 = tabla_celdas(celdas)
    n = len(celdas)
    suma, conteo = np.zeros(n), np.zeros(n)
    maximo = np.zeros(n)
    histograma = np.zeros((n, CLASES_PENDIENTE), dtype=np.int64)
    with rasterio.open(ruta_pendiente) as raster:
        t = raster.transform
        xs = t.c + (np.arange(raster.width) + 0.5) * t.a
        cx = np.floor((xs - x0) / TAM_CELDA_M).astype(int)
        for fila0 in range(0, raster.height, FILAS_BLOQUE):
            alto = min(FILAS_BLOQUE, raster.height - fila0)
            pendiente = raster.read(1, window=Window(0, fila0, raster.width, alto))
            ys = t.f + (np.arange(fila0, fila0 + alto) + 0.5) * t.e
            cy = np.floor((ys - y0) / TAM_CELDA_M).astype(int)
            CX, CY = np.meshgrid(cx, cy)
            dentro = (
                (pendiente >= 0)
                & (CX >= 0)
                & (CY >= 0)
                & (busqueda.shape[1] > CX)
                & (busqueda.shape[0] > CY)
            )
            k = busqueda[CY[dentro], CX[dentro]]
            p = np.clip(pendiente[dentro][k >= 0], 0, 90).astype(np.float64)
            k = k[k >= 0]
            suma += np.bincount(k, p, n)
            conteo += np.bincount(k, minlength=n)
            np.maximum.at(maximo, k, p)
            np.add.at(histograma, (k, np.round(p).astype(np.int64)), 1)
    return pd.DataFrame(
        {
            "id_celda": celdas["id_celda"].to_numpy(),
            "pend_media_g": (suma / np.maximum(conteo, 1)).astype("float32"),
            "pend_p90_g": percentil_histograma(histograma, 0.9),
            "pend_max_g": maximo.astype("float32"),
        }
    )

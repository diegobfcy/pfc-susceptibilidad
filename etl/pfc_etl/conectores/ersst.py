"""E2. Conector NOAA ERSST v5: índices mensuales Niño (anomalías respecto de 1991-2020)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pfc_etl.conectores.base import ConectorFuente, Ventana

URL_ERSST = "https://www.cpc.ncep.noaa.gov/data/indices/ersst5.nino.mth.91-20.ascii"


class ConectorErsst(ConectorFuente):
    """Conector de los índices Niño de NOAA ERSST v5 (un archivo con toda la serie)."""

    nombre_fuente = "ersst_v5"

    def _construir_url(self, ventana: Ventana) -> str:
        return URL_ERSST  # el archivo publicado contiene toda la serie desde 1950


def leer_ersst(ruta: Path) -> pd.DataFrame:
    """Serie Niño 1+2: columnas anio, mes, n12 (°C) y n12_anom (°C)."""
    tabla = pd.read_csv(ruta, sep=r"\s+")
    tabla.columns = [
        "anio",
        "mes",
        "n12",
        "n12_anom",
        "n3",
        "n3_anom",
        "n4",
        "n4_anom",
        "n34",
        "n34_anom",
    ]
    return tabla[["anio", "mes", "n12", "n12_anom"]]

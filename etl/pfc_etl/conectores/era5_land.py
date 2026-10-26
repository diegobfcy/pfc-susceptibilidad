"""E2. Conector Copernicus ERA5-Land (precipitación total a las 00 UTC, vía cdsapi).

En ERA5-Land el campo acumula desde las 00 UTC: el valor de las 00 UTC del día D+1 es la
precipitación total del día D. El CDS devuelve la URL del resultado, que también debe
pertenecer a la lista blanca antes de descargarse."""

from __future__ import annotations

from typing import Any

from pfc_etl.conectores.base import ConectorFuente, Ventana

PRODUCTO = "reanalysis-era5-land"


def solicitud_anual(anio: int, area: list[float]) -> dict[str, Any]:
    return {
        "variable": ["total_precipitation"],
        "year": str(anio),
        "month": [f"{m:02d}" for m in range(1, 13)],
        "day": [f"{d:02d}" for d in range(1, 32)],
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": area,
    }


class ConectorEra5Land(ConectorFuente):
    nombre_fuente = "era5_land"

    def __init__(self, *args: Any, area: list[float], cliente: Any = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._area = area
        self._cliente = cliente

    def _construir_url(self, ventana: Ventana) -> str:
        if self._cliente is None:
            import cdsapi

            self._cliente = cdsapi.Client(quiet=True)
        resultado = self._cliente.retrieve(PRODUCTO, solicitud_anual(ventana.anio_desde, self._area))
        return resultado.location


def a_mm_dia(acumulado_m: float) -> float:
    """Convierte el acumulado diario de ERA5-Land (m) a milímetros."""
    return acumulado_m * 1000.0

"""E2. Conector Copernicus DEM GLO-30 (teselas COG de 1° en AWS Open Data)."""

from __future__ import annotations

import math
from typing import Any

from pfc_etl.conectores.base import ConectorFuente, Ventana

BASE_DEM = "https://copernicus-dem-30m.s3.amazonaws.com"


def nombre_tesela(lat_inf: int, lon_izq: int) -> str:
    """Nombre de la tesela de 1° del DEM GLO-30 cuya esquina inferior izquierda es (lat, lon)."""
    ns = f"S{-lat_inf:02d}" if lat_inf < 0 else f"N{lat_inf:02d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_W{-lon_izq:03d}_00_DEM"


def teselas_dominio(dominio: dict[str, float]) -> list[str]:
    """Teselas del DEM GLO-30 que cubren la caja del dominio de config.yaml."""
    return [
        nombre_tesela(lat, lon)
        for lat in range(math.floor(dominio["lat_min"]), math.ceil(dominio["lat_max"]))
        for lon in range(math.floor(dominio["lon_min"]), math.ceil(dominio["lon_max"]))
    ]


class ConectorDemGlo30(ConectorFuente):
    """Descarga una tesela; el orquestador recorre teselas_dominio()."""

    nombre_fuente = "dem_glo30"

    def __init__(self, *args: Any, tesela: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tesela = tesela

    def _construir_url(self, ventana: Ventana) -> str:
        return f"{BASE_DEM}/{self._tesela}/{self._tesela}.tif"

    def _nombre_archivo(self, ventana: Ventana) -> str:
        return f"{self._tesela}.tif"

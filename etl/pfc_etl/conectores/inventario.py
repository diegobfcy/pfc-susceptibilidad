"""E2. Conector del inventario de movimientos en masa (servicio GEOCATMIN de INGEMMET)."""

from __future__ import annotations

from urllib.parse import urlencode

from pfc_etl.conectores.base import ConectorFuente, Ventana

SERVICIO = (
    "https://geocatmin.ingemmet.gob.pe/arcgis/rest/services/"
    "SERV_PELIGROS_GEOLOGICOS/MapServer/0/query"
)
PRECISION_FECHA = {"D1": "DIA", "D2": "MES", "D3": "ANIO"}


class ConectorInventario(ConectorFuente):
    nombre_fuente = "inventario"

    def _construir_url(self, ventana: Ventana) -> str:
        filtro = {"where": "1=1", "outFields": "*", "f": "geojson", "outSR": 4326}
        return f"{SERVICIO}?{urlencode(filtro)}"

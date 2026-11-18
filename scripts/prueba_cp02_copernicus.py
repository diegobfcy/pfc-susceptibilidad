"""CP-02: ingesta real de ERA5-Land con el conector E2 sobre el año indicado (por defecto 2026)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from pfc_datos.almacen import AlmacenArchivos
from pfc_datos.bitacora import BitacoraArchivo
from pfc_datos.config import cargar_config
from pfc_etl.conectores.base import Ventana
from pfc_etl.conectores.era5_land import ConectorEra5Land

RAIZ = Path(__file__).resolve().parents[1]


def main() -> None:
    anio = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    etiqueta = sys.argv[2] if len(sys.argv) > 2 else "primera_pasada"
    config = cargar_config()
    d2 = RAIZ / "data" / "pruebas" / "d2_cp02"
    conector = ConectorEra5Land(
        frozenset(config["hosts_permitidos"]),
        AlmacenArchivos(d2),
        BitacoraArchivo(d2 / "bitacora.jsonl"),
        area=config["dominio"]["area_cds"],
    )
    t0 = time.perf_counter()
    salida: dict[str, object] = {"anio": anio, "inicio": time.strftime("%FT%T%z")}
    try:
        registro = conector.descargar_periodo(Ventana(anio, anio))
        salida |= {"estado": "OK", "sha256": registro.sha256, "bytes": registro.bytes}
    except Exception as error:  # noqa: BLE001 - la prueba registra cualquier falla tal como ocurre
        salida |= {"estado": "FALLA", "tipo": type(error).__name__, "detalle": str(error)[:500]}
    salida |= {"segundos": round(time.perf_counter() - t0, 1), "fin": time.strftime("%FT%T%z")}
    destino = RAIZ / "resultados" / "pruebas" / "c2_integracion" / f"cp02_{etiqueta}.json"
    destino.write_text(json.dumps(salida, indent=2, default=str))
    print(json.dumps(salida, indent=2, default=str))


if __name__ == "__main__":
    main()

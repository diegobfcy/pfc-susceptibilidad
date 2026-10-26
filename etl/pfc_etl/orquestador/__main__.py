"""Ejecución local de un trabajo de ENTRENAMIENTO de extremo a extremo (E1 -> E4)."""

from __future__ import annotations

import argparse
import json

from pfc_datos.bitacora import BitacoraArchivo
from pfc_datos.config import cargar_config, ruta_d2, ruta_datos_origen
from pfc_etl.orquestador.etapas import EtapasLocales
from pfc_etl.orquestador.orquestador import Trabajo, ejecutar_trabajo


def main() -> None:
    argumentos = argparse.ArgumentParser(description=__doc__)
    argumentos.add_argument("--desde", type=int, default=2000)
    argumentos.add_argument("--hasta", type=int, default=2026)
    argumentos.add_argument("--tipo", default="ENTRENAMIENTO")
    argumentos.add_argument("--cola", action="store_true", help="atender la cola de D1 (worker)")
    a = argumentos.parse_args()
    d2 = ruta_d2()
    bitacora = BitacoraArchivo(d2 / "bitacora.jsonl")
    etapas = EtapasLocales(ruta_datos_origen(), d2, cargar_config(), bitacora)
    if a.cola:
        from pfc_datos.bd import crear_motor
        from pfc_etl.orquestador.cola import atender

        atender(crear_motor(), etapas, bitacora)
        return
    trabajo = ejecutar_trabajo(Trabajo(1, a.tipo, a.desde, a.hasta), etapas, bitacora)
    informe = {"estado": trabajo.estado, "tiempos_s": trabajo.tiempos_s, **trabajo.salida}
    (d2 / "informe_procesamiento.json").write_text(json.dumps(informe, indent=2, default=str))
    print(json.dumps(informe, indent=2, default=str))


if __name__ == "__main__":
    main()

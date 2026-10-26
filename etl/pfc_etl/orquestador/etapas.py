"""E1. Etapas concretas del procesamiento sobre los archivos de la estación de entrenamiento:
obtener (registro en D2 con SHA-256), verificar (E3) y transformar (E4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from pfc_datos.almacen import AlmacenArchivos, MatrizParquet, sha256_archivo
from pfc_datos.protocolos import RegistroBitacora
from pfc_etl.conectores.ersst import leer_ersst
from pfc_etl.orquestador.orquestador import DatosIncompletosError, FuenteNoDisponibleError, Trabajo
from pfc_etl.transformacion import lectores
from pfc_etl.transformacion.matriz import construir_matriz
from pfc_etl.transformacion.objetivo import celdas_mes_positivas
from pfc_etl.transformacion.oceanicas import variables_oceanicas
from pfc_etl.transformacion.precipitacion import variables_precipitacion
from pfc_etl.transformacion.terreno import variables_terreno
from pfc_etl.verificacion.verificador import verificar_dataset


class EtapasLocales:
    """Fuentes ya descargadas en la carpeta de origen (caché de los conectores E2)."""

    def __init__(self, origen: Path, d2: Path, config: dict[str, Any], bitacora: RegistroBitacora) -> None:
        self._origen = origen
        self._almacen = AlmacenArchivos(d2)
        self._matriz = MatrizParquet(d2)
        self._d2 = d2
        self._config = config
        self._bitacora = bitacora
        self._tablas: dict[str, pd.DataFrame] = {}

    def _archivos_fuente(self, trabajo: Trabajo) -> dict[str, list[Path]]:
        raw, proc = self._origen / "raw", self._origen / "processed"
        era5 = [
            raw / "ERA5Land" / f"era5land_tp00_{a}.nc"
            for a in range(trabajo.anio_desde - 1, trabajo.anio_hasta + 1)
        ]
        return {
            "ersst_v5": [raw / "NOAA_CPC" / "ersst5.nino.mth.91-20.ascii"],
            "era5_land": [a for a in era5 if a.exists()],
            "dem_glo30": [self._origen / "interim" / "terreno" / "pendiente.tif"],
            "inventario": [proc / "eventos.gpkg"],
            "grilla": [proc / "celdas.gpkg", proc / "pixeles_clima.gpkg"],
        }

    def obtener(self, trabajo: Trabajo) -> dict[str, int]:
        registrados = {}
        for fuente, archivos in self._archivos_fuente(trabajo).items():
            if not archivos or not all(a.exists() for a in archivos):
                raise FuenteNoDisponibleError(fuente)
            for archivo in archivos:
                huella = sha256_archivo(archivo)
                self._almacen.registrar(fuente, archivo, huella)
            registrados[fuente] = len(archivos)
        self._rutas = self._archivos_fuente(trabajo)
        return registrados

    def verificar(self, trabajo: Trabajo) -> dict[str, dict[str, Any]]:
        reglas = self._config["verificacion"]["fuentes"]
        r = self._rutas
        ersst = leer_ersst(r["ersst_v5"][0])
        ersst = ersst[(ersst.anio >= trabajo.anio_desde - 1) & (ersst.anio <= trabajo.anio_hasta)]
        pixeles = lectores.leer_pixeles(r["grilla"][1])
        era5 = lectores.leer_era5_diario(r["era5_land"], pixeles).rename(columns={"precip_mm": "p1"})
        eventos = lectores.leer_eventos(r["inventario"][0])
        informe = {}
        for fuente, tabla in (("ersst_v5", ersst), ("era5_land", era5), ("inventario", eventos)):
            resultado = verificar_dataset(fuente, tabla, reglas[fuente])
            informe[fuente] = {"filas": resultado.filas, "rechazados": resultado.rechazados,
                               "faltantes": len(resultado.faltantes)}
            if not resultado.es_valido:
                raise DatosIncompletosError(f"{fuente}: {resultado.faltantes[:5]}")
            self._tablas[fuente] = resultado.validos
        informe["era5_land"]["pixeles_imputados"] = era5.attrs.get("pixeles_imputados", 0)
        return informe

    def transformar(self, trabajo: Trabajo) -> dict[int, tuple[int, int]]:
        r = self._rutas
        celdas = lectores.leer_celdas(r["grilla"][0])
        cache_terreno = self._d2 / "terreno_celdas.parquet"
        if cache_terreno.exists():
            terreno = pd.read_parquet(cache_terreno)
        else:
            terreno = variables_terreno(celdas, r["dem_glo30"][0])
            terreno.to_parquet(cache_terreno, index=False)
        verif = verificar_dataset("dem_glo30", terreno, self._config["verificacion"]["fuentes"]["dem_glo30"])
        if not verif.es_valido:
            raise DatosIncompletosError(f"dem_glo30: {verif.faltantes}")
        precipitacion = variables_precipitacion(
            self._tablas["era5_land"].rename(columns={"p1": "precip_mm"})
        )
        return construir_matriz(
            range(trabajo.anio_desde, trabajo.anio_hasta + 1),
            self._matriz,
            celdas=celdas,
            oceanicas=variables_oceanicas(self._tablas["ersst_v5"]),
            precipitacion=precipitacion,
            terreno=verif.validos,
            positivos=celdas_mes_positivas(self._tablas["inventario"]),
        )

"""E2. Carga manual (RF-02): registra en D2 un archivo provisto por el Equipo Investigador
cuando la API de la fuente no está disponible. Comparte el contrato de los conectores."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from pfc_datos.protocolos import AlmacenArtefactos, ArchivoRegistrado, RegistroBitacora

EXTENSIONES = frozenset({".nc", ".tif", ".csv", ".ascii", ".gpkg", ".parquet"})


class ExtensionNoPermitidaError(Exception):
    pass


class CargaManual:
    def __init__(
        self, fuente: str, almacen: AlmacenArtefactos, bitacora: RegistroBitacora
    ) -> None:
        self.nombre_fuente = fuente
        self._almacen = almacen
        self._bitacora = bitacora

    def cargar(self, origen: Path) -> ArchivoRegistrado:
        if origen.suffix.lower() not in EXTENSIONES:
            raise ExtensionNoPermitidaError(origen.suffix)
        destino = self._almacen.ruta_temporal(self.nombre_fuente, origen.name)
        huella = hashlib.sha256()
        with origen.open("rb") as lectura, destino.open("wb") as escritura:
            for bloque in iter(lambda: lectura.read(1 << 20), b""):
                huella.update(bloque)
                escritura.write(bloque)
        registro = self._almacen.registrar(self.nombre_fuente, destino, huella.hexdigest())
        self._bitacora.registrar(
            "INFORMATIVO", "E2", "CARGA_MANUAL", fuente=self.nombre_fuente, sha256=registro.sha256
        )
        return registro


def copiar_existente(origen: Path, destino: Path) -> Path:
    """Reutiliza un archivo ya descargado (caché local de la estación de entrenamiento)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    return destino

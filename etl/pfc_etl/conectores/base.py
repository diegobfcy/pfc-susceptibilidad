"""E2. Clase base de los conectores: descarga segura y verificable de fuentes oficiales."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

import requests

from pfc_datos.protocolos import AlmacenArtefactos, ArchivoRegistrado, RegistroBitacora


class HostNoPermitidoError(Exception):
    """La URL no usa HTTPS o su dominio no está en la lista blanca de config.yaml."""


@dataclass(frozen=True)
class Ventana:
    """Periodo solicitado a una fuente (años inclusivos)."""

    anio_desde: int
    anio_hasta: int


class ConectorFuente(ABC):
    """E2. Descarga segura de una fuente oficial (RF-05) con integridad SHA-256.

    Template Method: el flujo de seguridad es fijo; cada subclase solo define
    qué solicitar a su fuente (ERSST v5, ERA5-Land, DEM GLO-30, inventario).
    """

    TIEMPO_ESPERA_S: Final = (10, 300)  # conexión y lectura, en segundos
    TAMANO_BLOQUE: Final = 1024 * 1024  # 1 MiB por bloque

    def __init__(
        self,
        hosts_permitidos: frozenset[str],
        almacen: AlmacenArtefactos,
        bitacora: RegistroBitacora,
    ) -> None:
        self._hosts_permitidos = hosts_permitidos  # lista blanca de config.yaml
        self._almacen = almacen  # D2, inyectado (DIP)
        self._bitacora = bitacora  # D3, inyectado (DIP)

    def descargar_periodo(self, ventana: Ventana) -> ArchivoRegistrado:
        """Validar dominio -> descargar por HTTPS -> SHA-256 -> registrar."""
        url = self._construir_url(ventana)  # único paso variable
        self._validar_host(url)  # OWASP A10 (SSRF)
        sha256 = hashlib.sha256()
        destino = self._almacen.ruta_temporal(self.nombre_fuente, self._nombre_archivo(ventana))
        with requests.get(
            url, stream=True, verify=True, allow_redirects=False, timeout=self.TIEMPO_ESPERA_S
        ) as respuesta:
            if respuesta.is_redirect:  # no se siguen saltos sin validar
                raise HostNoPermitidoError(respuesta.headers.get("Location"))
            respuesta.raise_for_status()
            with destino.open("wb") as archivo:
                for bloque in respuesta.iter_content(self.TAMANO_BLOQUE):
                    sha256.update(bloque)  # huella calculada al escribir
                    archivo.write(bloque)
        registro = self._almacen.registrar(self.nombre_fuente, destino, sha256.hexdigest())
        self._bitacora.registrar("INFORMATIVO", "E2", "INGESTA", fuente=self.nombre_fuente,
                                 sha256=registro.sha256)
        return registro

    def _validar_host(self, url: str) -> None:
        partes = urlsplit(url)
        if partes.scheme != "https" or partes.hostname not in self._hosts_permitidos:
            raise HostNoPermitidoError(partes.hostname)

    def _nombre_archivo(self, ventana: Ventana) -> str:
        return f"{self.nombre_fuente}_{ventana.anio_desde}_{ventana.anio_hasta}"

    @property
    @abstractmethod
    def nombre_fuente(self) -> str: ...

    @abstractmethod
    def _construir_url(self, ventana: Ventana) -> str: ...

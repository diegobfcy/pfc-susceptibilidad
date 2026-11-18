"""S2. Comprobación de archivos cargados: la extensión debe coincidir con el contenido (A04)."""

from __future__ import annotations

from pathlib import PurePath
from typing import BinaryIO

FIRMAS: dict[str, tuple[bytes, ...]] = {
    ".nc": (b"CDF", b"\x89HDF\r\n\x1a\n"),
    ".tif": (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"),
    ".gpkg": (b"SQLite format 3\x00",),
    ".parquet": (b"PAR1",),
}
TEXTO = frozenset({".csv", ".ascii"})
BYTES_MUESTRA = 4096


class ArchivoRechazadoError(Exception):
    """Extensión no permitida o contenido que no corresponde a la extensión."""


def comprobar_archivo(nombre: str, flujo: BinaryIO) -> None:
    """Comprueba la extensión y que el contenido corresponda a ella (firma o texto sin bytes
    nulos).

    Lanza ArchivoRechazadoError; deja el flujo al inicio para la copia.
    """
    extension = PurePath(nombre).suffix.lower()
    if extension not in FIRMAS and extension not in TEXTO:
        raise ArchivoRechazadoError(f"extensión no permitida: {extension or 'ninguna'}")
    muestra = flujo.read(BYTES_MUESTRA)
    flujo.seek(0)
    valido = (
        bool(muestra) and b"\x00" not in muestra
        if extension in TEXTO
        else muestra.startswith(FIRMAS[extension])
    )
    if not valido:
        raise ArchivoRechazadoError(f"el contenido no corresponde a {extension}")

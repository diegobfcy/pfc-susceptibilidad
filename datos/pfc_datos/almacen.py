"""D2: repositorio de archivos (fuentes, matriz Parquet particionada por año y artefactos)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from pfc_datos.protocolos import ArchivoRegistrado

TAMANO_BLOQUE = 1 << 20


def sha256_archivo(ruta: Path) -> str:
    """Huella SHA-256 de un archivo, leída por bloques de 1 MiB."""
    huella = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(TAMANO_BLOQUE), b""):
            huella.update(bloque)
    return huella.hexdigest()


class AlmacenArchivos:
    """Almacén D2 en disco; mantiene un catálogo JSON con la huella de cada archivo."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz
        self._catalogo = raiz / "catalogo.json"
        raiz.mkdir(parents=True, exist_ok=True)

    def ruta_temporal(self, fuente: str, nombre: str) -> Path:
        destino = self._raiz / "fuentes" / fuente / f"{nombre}.part"
        destino.parent.mkdir(parents=True, exist_ok=True)
        return destino

    def registrar(self, fuente: str, ruta: Path, sha256: str) -> ArchivoRegistrado:
        final = ruta.with_suffix("") if ruta.suffix == ".part" else ruta
        if final != ruta:
            shutil.move(ruta, final)
        catalogo = self._leer_catalogo()
        catalogo[self._clave(final)] = {"fuente": fuente, "sha256": sha256}
        self._catalogo.write_text(json.dumps(catalogo, indent=2), encoding="utf-8")
        return ArchivoRegistrado(fuente, final, sha256, final.stat().st_size)

    def verificar(self, ruta: Path) -> bool:
        """True si el archivo conserva la huella registrada (OWASP A08)."""
        esperado = self._leer_catalogo().get(self._clave(ruta), {}).get("sha256")
        return esperado is not None and esperado == sha256_archivo(ruta)

    def _clave(self, ruta: Path) -> str:
        """Ruta relativa a D2; los archivos de la caché externa se registran con ruta absoluta."""
        return str(ruta.relative_to(self._raiz)) if ruta.is_relative_to(self._raiz) else str(ruta)

    def _leer_catalogo(self) -> dict[str, dict[str, str]]:
        if not self._catalogo.exists():
            return {}
        return json.loads(self._catalogo.read_text(encoding="utf-8"))


class MatrizParquet:
    """Matriz de variables celda x mes en Parquet, una partición por año."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz / "matriz"
        self._raiz.mkdir(parents=True, exist_ok=True)

    def escribir_anio(self, anio: int, matriz: pd.DataFrame) -> Path:
        destino = self._raiz / f"anio={anio}" / "parte.parquet"
        destino.parent.mkdir(parents=True, exist_ok=True)
        matriz.to_parquet(destino, index=False, compression="zstd")
        return destino

    def leer(self, anios: range, columnas: list[str] | None = None) -> pd.DataFrame:
        partes = [
            pd.read_parquet(self._raiz / f"anio={a}" / "parte.parquet", columns=columnas)
            for a in anios
            if (self._raiz / f"anio={a}").exists()
        ]
        return pd.concat(partes, ignore_index=True)

    def anios_disponibles(self) -> list[int]:
        return sorted(int(p.name.split("=")[1]) for p in self._raiz.glob("anio=*"))

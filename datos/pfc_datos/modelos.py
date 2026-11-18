"""D2 + D1: repositorio de versiones del modelo (artefacto SHA-256, métricas e importancias)."""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pfc_datos.almacen import sha256_archivo


class EstadoVersion(StrEnum):
    """Estados del ciclo de vida de una versión del modelo en el repositorio."""

    CANDIDATA = "CANDIDATA"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"
    REVISION = "REVISION"


@dataclass
class VersionModelo:
    """Tarjeta de una versión del modelo: artefacto, huella SHA-256, métricas, importancias,
    referencia del PSI e hiperparámetros.
    """

    algoritmo: str
    version: str
    estado: EstadoVersion
    ruta_artefacto: str
    sha256: str
    bytes: int
    metricas: dict[str, Any] = field(default_factory=dict)
    importancia: dict[str, float] = field(default_factory=dict)
    referencia_psi: dict[str, list[float]] = field(default_factory=dict)
    hiperparametros: dict[str, Any] = field(default_factory=dict)
    entrenado_en: str = ""


class IntegridadArtefactoError(Exception):
    """El artefacto no coincide con la huella registrada (OWASP A08)."""


class RepositorioModelos:
    """Repositorio de versiones del modelo en D2 (carpeta modelos/): artefacto y tarjeta JSON."""

    def __init__(self, raiz: Path) -> None:
        self._raiz = raiz / "modelos"
        self._raiz.mkdir(parents=True, exist_ok=True)

    def guardar(
        self, clasificador: Any, algoritmo: str, version: str, estado: EstadoVersion, **datos: Any
    ) -> VersionModelo:
        """Serializa el clasificador, calcula su huella y escribe la tarjeta JSON junto al
        artefacto.
        """
        ruta = self._raiz / f"{algoritmo.lower()}_v{version}{self._extension(algoritmo)}"
        self._serializar(clasificador, algoritmo, ruta)
        registro = VersionModelo(
            algoritmo=algoritmo,
            version=version,
            estado=estado,
            ruta_artefacto=str(ruta),
            sha256=sha256_archivo(ruta),
            bytes=ruta.stat().st_size,
            entrenado_en=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            **datos,
        )
        tarjeta = ruta.with_suffix(".json")
        tarjeta.write_text(json.dumps(asdict(registro), indent=2, default=float), encoding="utf-8")
        return registro

    def cargar(self, algoritmo: str, version: str) -> tuple[Any, VersionModelo]:
        """Carga una versión después de verificar su huella SHA-256.

        Lanza IntegridadArtefactoError sin deserializar el artefacto si la huella no coincide con
        la de la tarjeta (OWASP A08).
        """
        ruta = self._raiz / f"{algoritmo.lower()}_v{version}{self._extension(algoritmo)}"
        tarjeta = json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))
        registro = VersionModelo(**tarjeta)
        if sha256_archivo(ruta) != registro.sha256:
            raise IntegridadArtefactoError(str(ruta))
        return self._deserializar(algoritmo, ruta), registro

    @staticmethod
    def _extension(algoritmo: str) -> str:
        return ".ubj" if algoritmo == "XGBOOST" else ".joblib"

    @staticmethod
    def _serializar(clasificador: Any, algoritmo: str, ruta: Path) -> None:
        if algoritmo == "XGBOOST":
            clasificador.save_model(ruta)
        else:
            import joblib

            joblib.dump(clasificador, ruta, compress=3)

    @staticmethod
    def _deserializar(algoritmo: str, ruta: Path) -> Any:
        if algoritmo == "XGBOOST":
            import xgboost as xgb

            modelo = xgb.XGBClassifier()
            modelo.load_model(ruta)
            return modelo
        import joblib

        return joblib.load(ruta)  # nosec B301: artefacto propio verificado con SHA-256

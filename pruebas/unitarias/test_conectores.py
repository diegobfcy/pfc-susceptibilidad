"""E2: contrato común de los conectores (prueba parametrizada, LSP) y seguridad de la descarga."""

from __future__ import annotations

import hashlib
from typing import Any
from unittest import mock

import pytest
from pfc_etl.conectores.base import ConectorFuente, HostNoPermitidoError, Ventana
from pfc_etl.conectores.dem_glo30 import ConectorDemGlo30, nombre_tesela, teselas_dominio
from pfc_etl.conectores.era5_land import ConectorEra5Land, a_mm_dia, solicitud_anual
from pfc_etl.conectores.ersst import ConectorErsst
from pfc_etl.conectores.inventario import ConectorInventario

HOSTS = frozenset(
    {
        "www.cpc.ncep.noaa.gov",
        "cds.climate.copernicus.eu",
        "copernicus-dem-30m.s3.amazonaws.com",
        "geocatmin.ingemmet.gob.pe",
    }
)
CONTENIDO = b"datos de prueba" * 1000


class _Respuesta:
    def __init__(self, redireccion: bool = False) -> None:
        self.is_redirect = redireccion
        self.headers = {"Location": "https://malicioso.example/x"}

    def __enter__(self) -> _Respuesta:
        return self

    def __exit__(self, *a: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, tamano: int) -> list[bytes]:
        return [CONTENIDO[i : i + tamano] for i in range(0, len(CONTENIDO), tamano)]


class _ClienteCds:
    def retrieve(self, producto: str, solicitud: dict[str, Any]) -> Any:
        return mock.Mock(location="https://cds.climate.copernicus.eu/descargas/abc.nc")


def _conectores(almacen: Any, bitacora: Any) -> list[ConectorFuente]:
    base = (HOSTS, almacen, bitacora)
    return [
        ConectorErsst(*base),
        ConectorEra5Land(*base, area=[-3.3, -81.5, -10.9, -76.6], cliente=_ClienteCds()),
        ConectorDemGlo30(*base, tesela=nombre_tesela(-8, -79)),
        ConectorInventario(*base),
    ]


@pytest.mark.parametrize("indice", range(3))  # el inventario se descarga por bloques (abajo)
def test_contrato_comun_de_descarga(indice: int, almacen: Any, bitacora: Any) -> None:
    conector = _conectores(almacen, bitacora)[indice]
    with mock.patch("pfc_etl.conectores.base.requests.get", return_value=_Respuesta()) as get:
        registro = conector.descargar_periodo(Ventana(2020, 2020))
    assert registro.sha256 == hashlib.sha256(CONTENIDO).hexdigest()
    assert registro.ruta.read_bytes() == CONTENIDO
    kwargs = get.call_args.kwargs
    assert kwargs["verify"] is True and kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == (10, 300)
    assert bitacora.eventos[-1][1] == "E2"


def test_rechaza_dominio_fuera_de_lista_blanca(almacen: Any, bitacora: Any) -> None:
    conector = ConectorErsst(frozenset({"otro.gob.pe"}), almacen, bitacora)
    with (
        pytest.raises(HostNoPermitidoError),
        mock.patch("pfc_etl.conectores.base.requests.get") as get,
    ):
        conector.descargar_periodo(Ventana(2020, 2020))
    get.assert_not_called()


def test_rechaza_http_sin_tls(almacen: Any, bitacora: Any) -> None:
    conector = ConectorErsst(HOSTS, almacen, bitacora)
    with pytest.raises(HostNoPermitidoError):
        conector._validar_host("http://www.cpc.ncep.noaa.gov/data/x")


def test_rechaza_redirecciones(almacen: Any, bitacora: Any) -> None:
    conector = ConectorErsst(HOSTS, almacen, bitacora)
    with (
        pytest.raises(HostNoPermitidoError),
        mock.patch(
            "pfc_etl.conectores.base.requests.get", return_value=_Respuesta(redireccion=True)
        ),
    ):
        conector.descargar_periodo(Ventana(2020, 2020))


def test_solicitud_era5_y_conversion() -> None:
    s = solicitud_anual(2023, [-3.3, -81.5, -10.9, -76.6])
    assert s["time"] == ["00:00"] and len(s["month"]) == 12 and s["year"] == "2023"
    assert a_mm_dia(0.0125) == pytest.approx(12.5)


def test_teselas_del_dominio() -> None:
    teselas = teselas_dominio(
        {"lat_min": -10.9, "lat_max": -3.35, "lon_min": -81.5, "lon_max": -76.6}
    )
    assert "Copernicus_DSM_COG_10_S08_00_W079_00_DEM" in teselas and len(teselas) == 8 * 6


class _RespuestaJson:
    def __init__(self, datos: Any) -> None:
        self.is_redirect = False
        self.headers: dict[str, str] = {}
        self._datos = datos

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._datos


def _servicio_inventario(total: int, recorte: int | None = None) -> Any:
    """Simula GEOCATMIN: primero los OBJECTID y luego los registros pedidos por bloque."""
    from urllib.parse import parse_qs, urlsplit

    def get(url: str, **_: Any) -> _RespuestaJson:
        consulta = parse_qs(urlsplit(url).query)
        if "returnIdsOnly" in consulta:
            return _RespuestaJson({"objectIds": list(range(total, 0, -1))})
        ids = [int(x) for x in consulta["objectIds"][0].split(",")][:recorte]
        return _RespuestaJson(
            {
                "type": "FeatureCollection",
                "features": [
                    {"type": "Feature", "properties": {"OBJECTID": i}, "geometry": None}
                    for i in ids
                ],
            }
        )

    return get


def test_inventario_completo_por_bloques(almacen: Any, bitacora: Any) -> None:
    """DEF-27: el servicio corta en 2000 registros; se descargan los 2500 sin faltantes."""
    import json

    with mock.patch(
        "pfc_etl.conectores.base.requests.get", side_effect=_servicio_inventario(2500)
    ) as get:
        registro = ConectorInventario(HOSTS, almacen, bitacora).descargar_periodo(
            Ventana(2000, 2026)
        )
    ids = [f["properties"]["OBJECTID"] for f in json.loads(registro.ruta.read_text())["features"]]
    assert sorted(ids) == list(range(1, 2501)) and get.call_count == 1 + 3
    assert registro.sha256 == hashlib.sha256(registro.ruta.read_bytes()).hexdigest()
    assert bitacora.eventos[-1][3]["registros"] == 2500
    for llamada in get.call_args_list:
        assert llamada.kwargs["allow_redirects"] is False and llamada.kwargs["verify"] is not False


def test_inventario_rechaza_un_bloque_incompleto(almacen: Any, bitacora: Any) -> None:
    servicio = _servicio_inventario(1500, recorte=999)
    with (
        mock.patch("pfc_etl.conectores.base.requests.get", side_effect=servicio),
        pytest.raises(ValueError, match="incompleto"),
    ):
        ConectorInventario(HOSTS, almacen, bitacora).descargar_periodo(Ventana(2000, 2026))


def test_inventario_verifica_tls_con_el_intermedio_de_sectigo(almacen: Any, bitacora: Any) -> None:
    """DEF-26: la verificación TLS sigue activa; el paquete suma certifi y el intermedio."""
    from pathlib import Path

    import certifi

    paquete = ConectorInventario(HOSTS, almacen, bitacora)._verificacion()
    contenido = Path(paquete).read_text()
    assert contenido.startswith(Path(certifi.where()).read_text())
    assert ConectorInventario.CA_INTERMEDIO.strip() in contenido
    assert ConectorErsst(HOSTS, almacen, bitacora)._verificacion() is True

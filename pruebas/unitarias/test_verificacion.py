"""E3: reglas de RF-06."""

import pandas as pd
from pfc_etl.verificacion.verificador import verificar_dataset

REGLAS = {
    "columnas": ["fecha", "id_pixel", "p1"],
    "rango": {"p1": [0.0, 500.0]},
    "frecuencia": "D",
}


def _serie(valores: list[float | None], inicio: str = "2020-01-01") -> pd.DataFrame:
    fechas = pd.date_range(inicio, periods=len(valores), freq="D")
    return pd.DataFrame({"fecha": fechas, "id_pixel": 1, "p1": valores})


def test_serie_valida_no_rechaza() -> None:
    r = verificar_dataset("era5_land", _serie([0.0, 3.5, 120.0]), REGLAS)
    assert r.es_valido and r.rechazados == {} and len(r.validos) == 3


def test_rango_rechaza_negativos_y_extremos() -> None:
    r = verificar_dataset("era5_land", _serie([-0.1, 2.0, 501.0]), REGLAS)
    assert r.rechazados == {"RANGO_P1": 2} and len(r.validos) == 1


def test_nulos_se_rechazan() -> None:
    r = verificar_dataset("era5_land", _serie([1.0, None, 2.0]), REGLAS)
    assert r.rechazados["VALOR_NULO"] == 1


def test_integridad_de_campos() -> None:
    r = verificar_dataset("era5_land", _serie([1.0]).drop(columns="p1"), REGLAS)
    assert not r.es_valido and r.rechazados["INTEGRIDAD_CAMPOS"] == 1 and r.validos.empty


def test_continuidad_detecta_dia_faltante() -> None:
    serie = _serie([1.0, 2.0, 3.0, 4.0]).drop(index=2)
    r = verificar_dataset("era5_land", serie, REGLAS)
    assert not r.es_valido and r.faltantes == ["2020-01-03"]


def test_continuidad_mensual_con_anio_y_mes() -> None:
    tabla = pd.DataFrame(
        {"anio": [2020, 2020, 2020], "mes": [1, 2, 4], "n12": 24.0, "n12_anom": 0.5}
    )
    reglas = {"columnas": ["anio", "mes", "n12", "n12_anom"], "rango": {}, "frecuencia": "MS"}
    assert verificar_dataset("ersst_v5", tabla, reglas).faltantes == ["2020-03-01"]

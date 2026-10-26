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


def test_cada_regla_es_independiente() -> None:
    from pfc_etl.verificacion.reglas import ReglaNulos, ReglaRango

    tabla = pd.DataFrame({"a": [1.0, None, 5.0], "b": [0.0, 1.0, 2.0]})
    faltantes: list[str] = []
    [(codigo, nulos)] = ReglaNulos(["a"]).evaluar(tabla, faltantes)
    assert codigo == "VALOR_NULO" and nulos.tolist() == [False, True, False]
    [(codigo, fuera)] = ReglaRango({"b": [0.0, 1.0]}).evaluar(tabla, faltantes)
    assert codigo == "RANGO_B" and fuera.tolist() == [False, False, True] and not faltantes


def test_tolerancia_en_los_bordes_del_rango() -> None:
    from pfc_etl.verificacion.reglas import ReglaRango

    tabla = pd.DataFrame({"p1": [500.0 + 1e-12, 500.1]})
    [(_, fuera)] = ReglaRango({"p1": [0.0, 500.0]}, tolerancia=1e-9).evaluar(tabla, [])
    assert fuera.tolist() == [False, True]


def test_construir_reglas_segun_config() -> None:
    from pfc_etl.verificacion.reglas import construir_reglas

    nombres = [type(r).__name__ for r in construir_reglas(REGLAS)]
    assert nombres == ["ReglaIntegridad", "ReglaNulos", "ReglaRango", "ReglaContinuidad"]
    assert len(construir_reglas({"columnas": ["x"]})) == 2

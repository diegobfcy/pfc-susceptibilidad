"""E4: variables oceánicas, de precipitación, objetivo y ensamblaje de la matriz."""

import numpy as np
import pandas as pd
from pfc_etl.transformacion.matriz import VARIABLES_MODELO, construir_anio
from pfc_etl.transformacion.objetivo import celdas_mes_positivas
from pfc_etl.transformacion.oceanicas import variables_oceanicas
from pfc_etl.transformacion.precipitacion import variables_precipitacion
from pfc_etl.transformacion.terreno import percentil_histograma, tabla_celdas


def _ersst(meses: int = 6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "anio": 2020,
            "mes": range(1, meses + 1),
            "n12": np.linspace(22, 27, meses),
            "n12_anom": np.arange(meses, dtype=float),
        }
    )


def test_rezagos_solo_miran_al_pasado() -> None:
    o = variables_oceanicas(_ersst())
    assert o.loc[3, "anom_tsm_l1"] == 2.0 and o.loc[3, "anom_tsm_l3"] == 0.0
    assert np.isnan(o.loc[0, "anom_tsm_l1"])
    assert o.loc[2, "anom_tsm_mm3"] == 1.0


def test_precipitacion_maximo_3_dias_y_antecedente() -> None:
    fechas = pd.date_range("2020-01-01", "2020-04-30", freq="D")
    lluvia = np.zeros(len(fechas))
    lluvia[100:103] = [10.0, 20.0, 30.0]  # 10-12 de abril
    diario = pd.DataFrame({"fecha": fechas, "id_pixel": 7, "precip_mm": lluvia})
    m = variables_precipitacion(diario).set_index("periodo")
    abril = m.loc["2020-04-01"]
    assert abril["precip_mes_mm"] == 60.0 and abril["precip_max3d_mm"] == 60.0
    assert abril["precip_ant90_mm"] == 60.0
    assert np.isnan(m.loc["2020-01-01", "precip_ant90_mm"])  # menos de 90 días previos


def test_objetivo_solo_dia_o_mes_y_con_celda() -> None:
    eventos = pd.DataFrame(
        {
            "id_celda": [1.0, 1.0, 2.0, np.nan, 3.0],
            "fecha": pd.to_datetime(
                ["2020-02-03", "2020-02-20", "2020-03-01", "2020-03-01", "2020-05-01"]
            ),
            "precision_fecha": ["DIA", "DIA", "MES", "DIA", "ANIO"],
        }
    )
    p = celdas_mes_positivas(eventos)
    assert len(p) == 2 and set(p["id_celda"]) == {1, 2}


def test_construir_anio_une_por_celda_y_mes() -> None:
    celdas = pd.DataFrame(
        {"id_celda": [1, 2], "id_pixel": [7, 7], "ubigeo_prov": ["2401", "2401"]}
    )
    terreno = pd.DataFrame(
        {
            "id_celda": [1, 2],
            "pend_media_g": [5.0, 30.0],
            "pend_p90_g": [8.0, 40.0],
            "pend_max_g": [12.0, 55.0],
        }
    )
    oceanicas = variables_oceanicas(_ersst()).fillna(0.0)
    precip = pd.DataFrame(
        {
            "id_pixel": 7,
            "periodo": oceanicas["periodo"],
            "precip_mes_mm": 50.0,
            "precip_max3d_mm": 20.0,
            "precip_ant90_mm": 150.0,
        }
    )
    positivos = pd.DataFrame({"id_celda": [2], "periodo": pd.to_datetime(["2020-03-01"])})
    m = construir_anio(2020, celdas, oceanicas, precip, terreno, positivos)
    assert len(m) == 12 and m["objetivo"].sum() == 1
    assert list(m.columns[2:-2]) == VARIABLES_MODELO


def test_tabla_celdas_y_percentil() -> None:
    celdas = pd.DataFrame({"x": [500.0, 1500.0], "y": [500.0, 500.0]})
    busqueda, x0, y0 = tabla_celdas(celdas)
    assert busqueda.shape == (1, 2) and (x0, y0) == (0.0, 0.0)
    hist = np.zeros((1, 91), dtype=int)
    hist[0, 10] = 9
    hist[0, 50] = 1
    assert percentil_histograma(hist, 0.9)[0] == 10.0

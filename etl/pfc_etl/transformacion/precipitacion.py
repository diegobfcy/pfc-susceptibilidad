"""E4. Variables de precipitación por celda climática ERA5-Land y mes."""

from __future__ import annotations

import pandas as pd

DIAS_ANTECEDENTES = 90


def variables_precipitacion(diario: pd.DataFrame) -> pd.DataFrame:
    """diario: fecha, id_pixel, precip_mm. Devuelve id_pixel, periodo, precip_mes_mm,
    precip_max3d_mm y precip_ant90_mm. Las sumas móviles terminan en el día evaluado."""
    diario = diario.sort_values(["id_pixel", "fecha"])
    por_pixel = diario.groupby("id_pixel", sort=False)["precip_mm"]
    diario = diario.assign(
        p3=por_pixel.transform(lambda s: s.rolling(3, min_periods=3).sum()),
        p90=por_pixel.transform(lambda s: s.rolling(DIAS_ANTECEDENTES, min_periods=DIAS_ANTECEDENTES).sum()),
        periodo=diario["fecha"].dt.to_period("M").dt.to_timestamp(),
    )
    mensual = diario.groupby(["id_pixel", "periodo"], sort=False).agg(
        precip_mes_mm=("precip_mm", "sum"),
        precip_max3d_mm=("p3", "max"),
        precip_ant90_mm=("p90", "last"),
    )
    return mensual.reset_index().astype(
        {"precip_mes_mm": "float32", "precip_max3d_mm": "float32", "precip_ant90_mm": "float32"}
    )

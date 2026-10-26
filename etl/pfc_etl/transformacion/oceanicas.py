"""E4. Variables oceánicas mensuales de la serie regional Niño 1+2 (ERSST v5)."""

from __future__ import annotations

import pandas as pd


def variables_oceanicas(ersst: pd.DataFrame) -> pd.DataFrame:
    """periodo, tsm_c, anom_tsm, anom_tsm_l1..l3 y anom_tsm_mm3 (solo miran al pasado)."""
    serie = ersst.sort_values(["anio", "mes"]).reset_index(drop=True)
    salida = pd.DataFrame(
        {
            "periodo": pd.to_datetime({"year": serie["anio"], "month": serie["mes"], "day": 1}),
            "tsm_c": serie["n12"].astype("float32"),
            "anom_tsm": serie["n12_anom"].astype("float32"),
        }
    )
    for rezago in (1, 2, 3):
        salida[f"anom_tsm_l{rezago}"] = salida["anom_tsm"].shift(rezago)
    salida["anom_tsm_mm3"] = salida["anom_tsm"].rolling(3).mean().astype("float32")
    return salida

"""Carga en D1 los datos reales que el sistema necesita para operar: grilla, división política,
terreno, TSM, inventario de deslizamientos, versión del modelo, métricas de validación, deriva y
umbrales de la Tabla 27."""

from __future__ import annotations

import json
import os
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pfc_datos.bd import crear_motor
from pfc_datos.config import ruta_d2, ruta_datos_origen
from pfc_etl.conectores.ersst import leer_ersst
from sqlalchemy import text
from sqlalchemy.engine import Engine

RAIZ = Path(__file__).resolve().parents[1]
MEDIO_LADO_M = 500.0
LIMITES_TABLA_27 = [0.25, 0.50, 0.75]


def copiar(motor: Engine, sql: str, tabla: pd.DataFrame) -> None:
    with motor.begin() as c:
        cursor = c.connection.cursor()
        with cursor.copy(sql) as copia:
            copia.write(tabla.to_csv(index=False, header=False))


def cargar_division_politica(motor: Engine, origen: Path) -> None:
    distritos = gpd.read_file(origen / "processed" / "distritos.gpkg")
    print("distritos", list(distritos.columns), distritos.crs, len(distritos))
    cod = next(c for c in distritos.columns if c.lower() in ("ubigeo", "iddist"))
    distritos[cod] = distritos[cod].astype(str).str.extract(r"(\d{6})$", expand=False)
    nom_prov = next(c for c in distritos.columns if c.lower() in ("provincia", "nombprov"))
    nom_dep = next(c for c in distritos.columns if c.lower() in ("departamento", "nombdep"))
    distritos["prov"] = distritos[cod].str[:4]
    distritos["dep"] = distritos[cod].str[:2]
    with motor.begin() as c:
        for clave, nombre, grupo in (
            ("dep", nom_dep, "departamento"),
            ("prov", nom_prov, "provincia"),
        ):
            for valor, parte in distritos.groupby(clave):
                wkt = parte.geometry.buffer(0).union_all()
                if grupo == "departamento":
                    c.execute(
                        text("""INSERT INTO ref.departamento VALUES
                            (:id, :n, ST_Multi(ST_GeomFromText(:g, 4326)))
                            ON CONFLICT DO NOTHING"""),
                        {"id": valor, "n": str(parte[nombre].iloc[0]).title(), "g": wkt.wkt},
                    )
                else:
                    c.execute(
                        text("""INSERT INTO ref.provincia VALUES
                            (:id, :d, :n, ST_Multi(ST_GeomFromText(:g, 4326)))
                            ON CONFLICT DO NOTHING"""),
                        {
                            "id": valor,
                            "d": valor[:2],
                            "n": str(parte[nombre].iloc[0]).title(),
                            "g": wkt.wkt,
                        },
                    )


def cargar_celdas(motor: Engine, d2: Path) -> int:
    celdas = pd.read_parquet(d2 / "celdas.parquet")
    with motor.connect() as c:
        if c.execute(text("SELECT count(*) FROM ref.celda_analisis")).scalar_one():
            return 0
    x, y, m = celdas["x"], celdas["y"], MEDIO_LADO_M
    celdas["ewkt"] = (
        "SRID=32717;POLYGON(("
        + (x - m).astype(str) + " " + (y - m).astype(str) + ","
        + (x + m).astype(str) + " " + (y - m).astype(str) + ","
        + (x + m).astype(str) + " " + (y + m).astype(str) + ","
        + (x - m).astype(str) + " " + (y + m).astype(str) + ","
        + (x - m).astype(str) + " " + (y - m).astype(str) + "))"
    )  # fmt: skip
    copiar(
        motor,
        "COPY ref.celda_analisis (id_celda, ubigeo_prov, id_pixel, geom) FROM STDIN (FORMAT csv)",
        celdas[["id_celda", "ubigeo_prov", "id_pixel", "ewkt"]],
    )
    return len(celdas)


def cargar_series(motor: Engine, origen: Path, d2: Path) -> None:
    terreno = pd.read_parquet(d2 / "terreno_celdas.parquet")
    with motor.connect() as c:
        hay = c.execute(text("SELECT count(*) FROM datos.terreno_celda")).scalar_one()
    if not hay:
        copiar(
            motor,
            "COPY datos.terreno_celda (id_celda, pend_media_g, pend_p90_g, pend_max_g) "
            "FROM STDIN (FORMAT csv)",
            terreno[["id_celda", "pend_media_g", "pend_p90_g", "pend_max_g"]],
        )
    tsm = leer_ersst(origen / "raw" / "NOAA_CPC" / "ersst5.nino.mth.91-20.ascii")
    with motor.begin() as c:
        for f in tsm[tsm.anio >= 2000].itertuples():
            c.execute(
                text("""INSERT INTO datos.tsm_mensual (periodo, tsm_c, anom_tsm)
                        VALUES (make_date(:a, :m, 1), :t, :an) ON CONFLICT DO NOTHING"""),
                {"a": int(f.anio), "m": int(f.mes), "t": float(f.n12), "an": float(f.n12_anom)},
            )


def cargar_modelo(motor: Engine, d2: Path) -> None:
    tarjeta = json.loads((d2 / "modelos" / "xgboost_v1.json").read_text())
    entrenamiento = json.loads((RAIZ / "resultados" / "entrenamiento_v1.json").read_text())
    ruta = str((d2 / "modelos" / "xgboost_v1.ubj").resolve())
    with motor.begin() as c:
        id_version = c.execute(
            text("""INSERT INTO modelo.modelo_version
                (algoritmo, version, estado, ruta_artefacto, sha256,
                 hiperparametros, referencia_psi)
                VALUES ('XGBOOST', :v, :e, :r, :s, CAST(:h AS jsonb), CAST(:p AS jsonb))
                ON CONFLICT (algoritmo, version)
                DO UPDATE SET ruta_artefacto = EXCLUDED.ruta_artefacto
                RETURNING id_modelo_version"""),
            {
                "v": tarjeta["version"],
                "e": tarjeta["estado"],
                "r": ruta,
                "s": tarjeta["sha256"],
                "h": json.dumps(tarjeta["hiperparametros"]),
                "p": json.dumps(tarjeta["referencia_psi"]),
            },
        ).scalar_one()
        c.execute(
            text("""INSERT INTO modelo.metrica VALUES (:id, 'VALIDACION', 'AUC_ROC', :a)
                    ON CONFLICT DO NOTHING"""),
            {"id": id_version, "a": entrenamiento["xgboost"]["auc_validacion"]},
        )
        for variable, valor in entrenamiento["psi_entreno_validacion"].items():
            c.execute(
                text("""INSERT INTO modelo.deriva VALUES (:id, :v, :p) ON CONFLICT DO NOTHING"""),
                {"id": id_version, "v": variable, "p": valor},
            )
        if not c.execute(text("SELECT count(*) FROM sistema.umbral_version")).scalar_one():
            c.execute(
                text("INSERT INTO sistema.umbral_version (limites, vigente) VALUES (:l, true)"),
                {"l": LIMITES_TABLA_27},
            )
    print("modelo", id_version)


def cargar_inventario(motor: Engine, origen: Path) -> int:
    """Inventario histórico verificado (eventos.gpkg) en datos.deslizamiento, para la capa de
    CU-04; se registra como dataset con su huella SHA-256 y no se duplica al repetir."""
    from pfc_datos.almacen import sha256_archivo
    from pfc_etl.transformacion.lectores import PRECISION

    ruta = origen / "processed" / "eventos.gpkg"
    with motor.begin() as c:
        hay = c.execute(text("SELECT count(*) FROM datos.deslizamiento")).scalar_one()
        if hay:
            return int(hay)
        id_dataset = c.execute(
            text("""INSERT INTO sistema.dataset (id_fuente, version_producto, origen,
                        ruta_archivo, sha256, periodo_inicio, periodo_fin)
                    VALUES (4, 'NPS-MM 1.0.1', 'AUTOMATICO', :r, :h, '2000-01-01', '2026-06-30')
                    RETURNING id_dataset"""),
            {"r": str(ruta), "h": sha256_archivo(ruta)},
        ).scalar_one()
    eventos = gpd.read_file(ruta)
    tabla = pd.DataFrame(
        {
            "id_dataset": id_dataset,
            "codigo_origen": eventos["event_uid"],
            "fecha_evento": pd.to_datetime(eventos["fecha"]).dt.strftime("%Y-%m-%d"),
            "precision_fecha": eventos["date_precision"].map(PRECISION).fillna("NULA"),
            "id_celda": eventos["id_celda"].astype("Int64"),
            "geom": eventos.geometry.to_wkt().radd("SRID=4326;"),
        }
    )
    tabla.loc[tabla["precision_fecha"] == "NULA", "fecha_evento"] = None
    copiar(
        motor,
        "COPY datos.deslizamiento (id_dataset, codigo_origen, fecha_evento, precision_fecha, "
        "id_celda, geom) FROM STDIN (FORMAT csv)",
        tabla,
    )
    return len(tabla)


def main() -> None:
    motor = crear_motor()
    origen, d2 = ruta_datos_origen(), ruta_d2()
    original = RAIZ / "data" / "d2"
    cargar_division_politica(motor, origen)
    print("celdas", cargar_celdas(motor, original))
    cargar_series(motor, origen, original)
    print("inventario", cargar_inventario(motor, origen))
    cargar_modelo(motor, d2)


if __name__ == "__main__":
    os.environ.setdefault("PROJ_DATA", "/home/diegobfcy/anaconda3/envs/tesis/share/proj")
    main()

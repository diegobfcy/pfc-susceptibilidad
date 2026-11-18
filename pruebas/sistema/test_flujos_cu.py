"""Caja negra de los flujos de los casos de uso que no cubrían CP-01 a CP-26 (CP-27 a CP-38).

CU-01: flujo normal con confirmación (IU-05) y fin (IU-07), aviso 409, flujo 4a (IU-08 e IU-09)
y flujo 6a (IU-10 e IU-11); RF-01: zona geográfica de la inferencia; CU-03: exportación y aviso
de rendimiento; CU-04: capas de pendiente, TSM e inventario. Los estados EN_ESPERA se preparan
en D1 con el mismo motivo que escribe el orquestador (lo verifican test_orquestador.py y las
pruebas de integración CP-07 y CP-08), porque provocar la caída real de una fuente desde el
navegador no es reproducible.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text

URL = "https://127.0.0.1:8444"
INV, ESP, ASE = "INVESTIGADOR", "ESPECIALISTA", "ASESOR"
CELDAS_TUMBES = 4624
MACRORREGION = 108461


def _cancelar_activos(motor_bd: Any) -> None:
    with motor_bd.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento SET estado = 'CANCELADO', finalizado_en = now()
                          WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')""")
        )


def _esperar(motor_bd: Any, identificador: int, finales: set[str], limite_s: int = 300) -> str:
    t0 = time.time()
    while time.time() - t0 < limite_s:
        with motor_bd.connect() as c:
            estado = c.execute(
                text("SELECT estado FROM sistema.procesamiento WHERE id_procesamiento = :i"),
                {"i": identificador},
            ).scalar_one()
        if estado in finales:
            return estado
        time.sleep(1)
    raise TimeoutError(identificador)


def _en_espera(motor_bd: Any, motivo: dict[str, str] | None) -> int:
    """Procesamiento EN_ESPERA con el resumen que deja el orquestador (motivo de la espera)."""
    resumen = json.dumps({"motivo": motivo}) if motivo else None
    with motor_bd.begin() as c:
        return c.execute(
            text("""INSERT INTO sistema.procesamiento
                (id_usuario, tipo, fecha_desde, fecha_hasta, zona, estado, resumen)
                SELECT id_usuario, 'INGESTA', '2026-01-01', '2026-01-31',
                       ST_Multi(ST_MakeEnvelope(-81, -10, -77, -4, 4326)), 'EN_ESPERA',
                       CAST(:r AS jsonb)
                FROM sistema.usuario WHERE correo = 'inv@pruebas.pfc'
                RETURNING id_procesamiento"""),
            {"r": resumen},
        ).scalar_one()


@pytest.fixture
def sin_activos(motor_bd: Any) -> Iterator[None]:
    _cancelar_activos(motor_bd)
    yield
    _cancelar_activos(motor_bd)


@pytest.fixture
def panel_inv(navegador: Any, estado_sesion: dict[str, str]) -> Iterator[Any]:
    from conftest import Visor

    v = Visor(navegador, estado_sesion[INV])
    yield v
    v.cerrar()


def _abrir_panel(v: Any) -> Any:
    pagina = v.pagina
    pagina.goto(f"{URL}/panel/")
    pagina.wait_for_selector('body[data-listo="1"]', timeout=30000)
    return pagina


# ---- RF-01 / CU-01 flujo normal: zona geográfica de la inferencia (API) ----------------------


def test_cp27_rf01_inferencia_limitada_a_un_departamento(
    clientes: dict, motor_bd: Any, sin_activos: None
) -> None:
    inv = clientes[INV]
    cuerpo = {"fecha_desde": "2026-04-01", "fecha_hasta": "2026-04-30", "id_modelo_version": 1}
    with motor_bd.connect() as c:
        antes = c.execute(
            text("""SELECT count(*) FROM resultado.susceptibilidad s JOIN ref.celda_analisis c
                    USING (id_celda)
                    WHERE periodo = '2026-04-01' AND left(c.ubigeo_prov, 2) <> '24'
                    """)
        ).scalar_one()
    assert inv.post("/inferencias", json={**cuerpo, "departamento": "16"}).status_code == 422
    r = inv.post("/inferencias", json={**cuerpo, "departamento": "24"})
    assert r.status_code == 202, r.text
    identificador = r.json()["id_procesamiento"]
    assert _esperar(motor_bd, identificador, {"COMPLETADO", "FALLIDO"}) == "COMPLETADO"
    with motor_bd.connect() as c:
        escritas, ajenas = c.execute(
            text("""SELECT count(*), count(*) FILTER (WHERE left(c.ubigeo_prov, 2) <> '24')
                    FROM resultado.susceptibilidad s JOIN ref.celda_analisis c USING (id_celda)
                    WHERE s.id_procesamiento = :i"""),
            {"i": identificador},
        ).one()
        total, despues = c.execute(
            text("""SELECT count(*), count(*) FILTER (WHERE left(c.ubigeo_prov, 2) <> '24')
                    FROM resultado.susceptibilidad s JOIN ref.celda_analisis c USING (id_celda)
                    WHERE s.periodo = '2026-04-01'"""),
        ).one()
        zona = c.execute(
            text("""SELECT p.ubigeo_dep, ST_Equals(p.zona, d.geom) FROM sistema.procesamiento p
                    JOIN ref.departamento d ON d.ubigeo_dep = '24'
                    WHERE p.id_procesamiento = :i"""),
            {"i": identificador},
        ).one()
    assert (escritas, ajenas) == (CELDAS_TUMBES, 0)
    assert total == MACRORREGION and despues == antes  # el resto de la macrorregión no cambia
    assert tuple(zona) == ("24", True)


def test_cp28_iu06_procesamiento_activo(clientes: dict, motor_bd: Any, sin_activos: None) -> None:
    assert clientes[INV].get("/procesamientos/activo").status_code == 204
    identificador = _en_espera(motor_bd, None)
    r = clientes[ASE].get("/procesamientos/activo")
    assert r.status_code == 200 and r.json()["id_procesamiento"] == identificador
    assert clientes[ESP].get("/procesamientos/activo").status_code == 403


# ---- CU-01 flujo normal en el panel: configurar, confirmar (IU-05) y fin (IU-07) -------------


def test_cp29_cu01_flujo_normal_en_el_panel(
    panel_inv: Any, motor_bd: Any, sin_activos: None
) -> None:
    """CU-01, pasos 1, 2, 3 y 10 y escenario 1: acceder, ingresar el rango de fechas y la zona,
    confirmar y recibir el aviso de fin."""
    pagina = _abrir_panel(panel_inv)
    formulario = pagina.locator("#form-proceso")
    assert pagina.locator("#sel-zona").is_disabled()  # la ingesta cubre toda la macrorregión
    formulario.locator('select[name="tipo"]').select_option("INFERENCIA")
    formulario.locator('input[name="fecha_desde"]').fill("2026-05-01")
    formulario.locator('input[name="fecha_hasta"]').fill("2026-05-31")
    pagina.select_option("#sel-zona", label="Tumbes")
    formulario.locator('button[type="submit"]').click()
    dialogo = pagina.locator("#dlg-confirmar")
    dialogo.wait_for(state="visible")
    resumen = pagina.inner_text("#resumen-proceso")
    assert "INFERENCIA" in resumen and "Tumbes" in resumen and "1 meses" in resumen
    assert re.sub(r"[\s.,\u202f\xa0]", "", resumen).count("4624estimaciones") == 1
    with pagina.expect_response(lambda r: r.url.endswith("/api/inferencias")) as respuesta:
        pagina.click("#confirmar")
    assert respuesta.value.status == 202
    pagina.wait_for_selector("#fin-ok:not([hidden])", timeout=180000)
    assert "El procesamiento finalizó correctamente" in pagina.inner_text("#fin-ok")
    numero = re.search(r"registros: ([\d.,\s\u202f\xa0]+)", pagina.inner_text("#fin-ok"))
    assert numero and re.sub(r"\D", "", numero.group(1)) == str(CELDAS_TUMBES)
    assert panel_inv.errores == []


def test_cp30_cu01_aviso_si_ya_hay_un_procesamiento(
    panel_inv: Any, motor_bd: Any, sin_activos: None
) -> None:
    _en_espera(motor_bd, None)
    pagina = _abrir_panel(panel_inv)
    formulario = pagina.locator("#form-proceso")
    formulario.locator('input[name="fecha_desde"]').fill("2026-01-01")
    formulario.locator('input[name="fecha_hasta"]').fill("2026-01-31")
    formulario.locator('button[type="submit"]').click()
    pagina.click("#confirmar")
    pagina.wait_for_selector("#dlg-confirmar-aviso:not([hidden])")
    assert "Ya existe un procesamiento en curso" in pagina.inner_text("#dlg-confirmar-aviso")


# ---- CU-01 flujo 4a: fuente no disponible (IU-08) y carga manual (IU-09) ---------------------


def test_cp31_cu01_4a_aviso_de_fuente_y_carga_manual(
    panel_inv: Any, motor_bd: Any, sin_activos: None
) -> None:
    """CU-01, flujo 4a y escenario 2: alerta visual de la fuente y carga manual del archivo.
    El rechazo de archivos no permitidos es de RF-02 y se prueba en CP-04."""
    motivo = {"tipo": "FUENTE_NO_DISPONIBLE", "fuente": "dem_glo30",
              "detalle": "no respondió o su archivo no está disponible"}  # fmt: skip
    identificador = _en_espera(motor_bd, motivo)
    pagina = _abrir_panel(panel_inv)
    pagina.wait_for_selector("#alerta-espera:not([hidden])")
    assert "Fuente externa no disponible" in pagina.inner_text("#alerta-titulo")
    detalle = pagina.inner_text("#alerta-detalle")
    assert "Copernicus DEM GLO-30" in detalle and "cargar el archivo manualmente" in detalle
    assert pagina.input_value("#sel-fuente") == "dem_glo30"
    tif = b"II*\x00" + b"\x00" * 2048  # firma TIFF válida
    archivo = {"name": "dem_manual_cp31.tif", "mimeType": "image/tiff", "buffer": tif}
    pagina.set_input_files("#archivo", files=[archivo])
    pagina.click('#form-carga button[type="submit"]')
    pagina.wait_for_selector("#carga-resultado:has-text('La verificación se reanuda')")
    assert "SHA-256" in pagina.inner_text("#carga-resultado")
    with motor_bd.connect() as c:
        origen = c.execute(text("""SELECT origen FROM sistema.dataset
                    WHERE ruta_archivo LIKE '%dem_manual_cp31.tif' ORDER BY id_dataset DESC
                    LIMIT 1""")).scalar_one()
        estado = c.execute(
            text("SELECT estado FROM sistema.procesamiento WHERE id_procesamiento = :i"),
            {"i": identificador},
        ).scalar_one()
    assert origen == "MANUAL" and estado in ("PENDIENTE", "EN_CURSO", "COMPLETADO", "EN_ESPERA")
    _esperar(motor_bd, identificador, {"COMPLETADO", "FALLIDO", "EN_ESPERA", "CANCELADO"}, 900)


# ---- CU-01 flujo 6a: datos rechazados (IU-10) y cancelación confirmada (IU-11) ---------------


def test_cp32_cu01_6a_regla_incumplida_y_cancelacion(
    panel_inv: Any, motor_bd: Any, sin_activos: None
) -> None:
    """CU-01, flujo 6a y escenario 3: se indica la regla incumplida y el procesamiento no
    continúa hasta que el Equipo Investigador lo cancele."""
    motivo = {"tipo": "DATOS_RECHAZADOS", "fuente": "era5_land", "regla": "continuidad temporal",
              "detalle": "2 periodos faltantes: 2023-03-15, 2023-03-16"}  # fmt: skip
    identificador = _en_espera(motor_bd, motivo)
    pagina = _abrir_panel(panel_inv)
    pagina.wait_for_selector("#alerta-espera:not([hidden])")
    assert "Datos rechazados en la verificación" in pagina.inner_text("#alerta-titulo")
    detalle = pagina.inner_text("#alerta-detalle")
    for texto in ("Copernicus ERA5-Land", "continuidad temporal", "2023-03-15", "2023-03-16",
                  "no continúa hasta reemplazar el archivo o cancelarlo"):  # fmt: skip
        assert texto in detalle
    # El procesamiento no continúa mientras el Investigador no reemplace los datos o cancele.
    assert _esperar(motor_bd, identificador, {"EN_ESPERA"}, 5) == "EN_ESPERA"
    pagina.click("#cancelar")  # el Equipo Investigador lo cancela
    pagina.locator("#dlg-cancelar").wait_for(state="visible")
    with pagina.expect_response(lambda r: r.url.endswith("/cancelar")) as respuesta:
        pagina.click("#si-cancelar")
    assert respuesta.value.status == 204
    pagina.wait_for_selector("#estado:has-text('CANCELADO')")
    with motor_bd.connect() as c:
        evento = c.execute(
            text("""SELECT tipo, descripcion FROM sistema.bitacora
                    WHERE id_procesamiento = :i ORDER BY id_evento DESC LIMIT 1"""),
            {"i": identificador},
        ).one()
    assert tuple(evento) == ("ADVERTENCIA", "procesamiento cancelado")


# ---- CU-03: exportación (paso 4) y aviso de rendimiento (flujo 3a) ---------------------------


def test_cp33_cu03_exporta_los_indicadores_mostrados(panel: Any, clientes: dict) -> None:
    pagina = panel.pagina
    pagina.goto(f"{URL}/panel/")
    pagina.wait_for_selector('body[data-listo="1"]')
    with pagina.expect_download() as descarga:
        pagina.click("#exportar")
    archivo = descarga.value
    assert archivo.suggested_filename.startswith("indicadores_")
    filas = list(csv.reader(io.StringIO(archivo.path().read_text(encoding="utf-8-sig"))))
    assert filas[0] == ["indicador", "valor", "detalle", "estado"]
    datos = {f[0]: f for f in filas[1:]}
    auc = next(m for m in clientes[ASE].get("/indicadores").json()["metricas"]
               if m["nombre"] == "AUC_ROC" and m["conjunto"] == "VALIDACION")  # fmt: skip
    assert datos["AUC-ROC validacion"][1] == f"{auc['valor']:.3f}"
    assert datos["PSI anom_tsm"][3] == "Rendimiento por debajo del nivel esperado"
    assert any(f[0].startswith("Tiempo total") for f in filas[1:])
    assert (
        len(filas) - 1
        == pagina.locator(".kpi").count() + 2 * pagina.locator("#tabla-procesos tr").count()
    )


# ---- CU-04: capas de pendiente, TSM e inventario (API y visor) -------------------------------


@pytest.mark.parametrize(
    ("capa", "atributos"),
    [
        ("pendiente", {"id_celda", "pend_media_g"}),
        ("tsm", {"ubigeo_dep", "anom_tsm", "tsm_c"}),
        ("inventario", {"codigo_origen", "id_celda", "fecha", "del_periodo"}),
    ],
)
def test_cp34_cu04_capas_nuevas_en_mvt(
    clientes: dict, motor_bd: Any, capa: str, atributos: set[str]
) -> None:
    import mapbox_vector_tile

    r = clientes[ESP].get(f"/mapas/{capa}/2017-03/7/36/66.pbf")
    assert r.status_code == 200, r.status_code
    elementos = mapbox_vector_tile.decode(r.content)[capa]["features"]
    assert elementos and atributos <= set(elementos[0]["properties"])
    with motor_bd.connect() as c:
        if capa == "tsm":
            anomalia = c.execute(
                text("SELECT anom_tsm::float8 FROM datos.tsm_mensual WHERE periodo='2017-03-01'")
            ).scalar_one()
            assert {round(f["properties"]["anom_tsm"], 2) for f in elementos} == {anomalia}
        if capa == "inventario":
            fechas = [f["properties"]["fecha"] for f in elementos]
            assert max(fechas) < "2017-04-01"  # solo eventos hasta el fin del periodo
            del_mes = [f for f in elementos if f["properties"]["del_periodo"]]
            assert del_mes and all(f["properties"]["fecha"][:7] == "2017-03" for f in del_mes)
    filtrada = clientes[ESP].get(f"/mapas/{capa}/2017-03/7/35/65.pbf?departamento=24")
    if capa != "tsm":
        decodificada = mapbox_vector_tile.decode(filtrada.content).get(capa, {})
        ids = {f["properties"].get("id_celda") for f in decodificada.get("features", [])}
        ids.discard(None)
        with motor_bd.connect() as c:
            ajenas = c.execute(
                text("""SELECT count(*) FROM ref.celda_analisis
                        WHERE id_celda = ANY(:i) AND left(ubigeo_prov, 2) <> '24'"""),
                {"i": list(ids)},
            ).scalar_one()
        assert ajenas == 0
    else:
        deps = {f["properties"]["ubigeo_dep"] for f in
                mapbox_vector_tile.decode(filtrada.content)["tsm"]["features"]}  # fmt: skip
        assert deps == {"24"}


def test_cp35_cu04_activar_capas_nuevas_y_error_de_una(visor: Any) -> None:
    pagina = visor.abrir("2017-03")
    for capa, panel, leyenda in [
        ("tsm", ".leaflet-tile-pane canvas", "Anomalía de TSM Niño 1+2"),
        ("pendiente", ".leaflet-shadow-pane canvas", "Pendiente media"),
        ("inventario", ".leaflet-marker-pane canvas", "Inventario de deslizamientos"),
    ]:
        with pagina.expect_response(lambda r, c=capa: f"/api/mapas/{c}/" in r.url) as resp:
            pagina.check(f"#capa-{capa}")
        assert resp.value.status in (200, 204)
        visor.esperar_teselas()
        assert pagina.locator(panel).count() > 0, capa
        assert leyenda in pagina.inner_text("#leyenda")
    pagina.uncheck("#capa-pendiente")
    visor.esperar_teselas()
    assert "Pendiente media" not in pagina.inner_text("#leyenda")
    # Flujo 4a con una capa nueva: el inventario falla y las demás siguen visibles.
    assert visor.errores == []  # antes de simular el fallo, que el navegador registra como error
    pagina.uncheck("#capa-inventario")
    pagina.route("**/api/mapas/inventario/**", lambda r: r.fulfill(status=500, body="fallo"))
    pagina.check("#capa-inventario")
    pagina.wait_for_selector("#error-inventario:not([hidden])")
    assert pagina.locator(".leaflet-overlay-pane canvas").count() > 0
    assert pagina.locator(".leaflet-tile-pane canvas").count() > 0


# ---- RF-13: el historial registra las operaciones, no solo los errores -----------------------


def test_cp36_rf13_cada_operacion_queda_en_el_historial(clientes: dict, motor_bd: Any) -> None:
    with motor_bd.connect() as c:
        identificador = c.execute(text("""SELECT max(id_procesamiento) FROM sistema.procesamiento
                    WHERE tipo = 'INFERENCIA' AND estado = 'COMPLETADO'""")).scalar_one()
        eventos = c.execute(
            text("""SELECT b.tipo, b.componente, b.descripcion, u.correo
                    FROM sistema.bitacora b LEFT JOIN sistema.usuario u USING (id_usuario)
                    WHERE b.id_procesamiento = :i ORDER BY b.id_evento"""),
            {"i": identificador},
        ).all()
    assert [tuple(e) for e in eventos] == [
        ("INFORMATIVO", "S1", "INFERENCIA encolado", "inv@pruebas.pfc"),
        ("INFORMATIVO", "M2", "inferencia completada", None),
    ]
    tipos = {e["tipo"] for e in clientes[ASE].get("/bitacora").json()["eventos"]}
    assert {"INFORMATIVO", "ADVERTENCIA", "ERROR"} <= tipos  # CU-05 muestra los tres tipos

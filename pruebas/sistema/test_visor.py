"""Caja negra del visor y del panel en navegador real: CP-18 a CP-24 (Chromium, Firefox y Edge).

Los casos que citan un caso de uso siguen literalmente sus pasos, su actor y sus mensajes."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text

PALETA_ESTANDAR = [(12, 163, 12), (250, 178, 25), (236, 131, 90), (208, 59, 59)]
PALETA_ACCESIBLE = [(255, 255, 212), (254, 217, 142), (254, 153, 41), (204, 76, 2)]
JS_MUESTRA_LIENZOS = """
(minimo) => {
  const conteo = {};
  for (const lienzo of document.querySelectorAll('.leaflet-overlay-pane canvas')) {
    if (!lienzo.width) continue;
    const datos = lienzo.getContext('2d').getImageData(0, 0, lienzo.width, lienzo.height).data;
    for (let i = 0; i < datos.length; i += 4 * 7) {
      if (datos[i + 3] < (minimo ?? 150)) continue;
      const clave = [datos[i], datos[i + 1], datos[i + 2]].join(',');
      conteo[clave] = (conteo[clave] || 0) + 1;
    }
  }
  return conteo;
}"""


def _fraccion_en_paleta(conteo: dict[str, int], paleta: list[tuple[int, int, int]]) -> float:
    total = sum(conteo.values())
    dentro = 0
    for clave, n in conteo.items():
        rgb = tuple(int(x) for x in clave.split(","))
        if any(all(abs(a - b) <= 12 for a, b in zip(rgb, color, strict=True)) for color in paleta):
            dentro += n
    return dentro / max(total, 1)


def _ir(visor: Any, lat: float, lon: float, z: int) -> None:
    visor.pagina.evaluate(
        "([a, o, z]) => window.mapaVisor.setView([a, o], z, {animate: false})", [lat, lon, z]
    )
    visor.esperar_teselas()


def test_cp20_celdas_por_nivel_en_cada_zoom(visor: Any) -> None:
    visor.abrir("2023-03")
    for z in range(6, 13):
        _ir(visor, -5.2, -80.0, z)
        # En zoom 6 y 7 cada celda mide cerca de un píxel: no queda opaca y su color se mezcla.
        assert sum(visor.pagina.evaluate(JS_MUESTRA_LIENZOS, 40).values()) > 0, f"vacío en {z}"
        if z >= 8:
            conteo = visor.pagina.evaluate(JS_MUESTRA_LIENZOS)
            assert _fraccion_en_paleta(conteo, PALETA_ESTANDAR) > 0.8, z  # el resto son bordes
    assert visor.errores == []


def test_cp20_paleta_accesible_y_leyenda(visor: Any) -> None:
    pagina = visor.abrir("2023-03")
    pagina.select_option("#sel-paleta", "accesible")
    visor.esperar_teselas()
    _ir(visor, -5.2, -80.0, 8)
    conteo = pagina.evaluate(JS_MUESTRA_LIENZOS)
    # El nivel Muy alta lleva trama: se tolera la mezcla con las líneas diagonales.
    assert _fraccion_en_paleta(conteo, PALETA_ACCESIBLE) > 0.8
    leyenda = pagina.inner_text("#leyenda")
    for rotulo in (
        "Baja (0 a 25 %)",
        "Media (25 a 50 %)",
        "Alta (50 a 75 %)",
        "Muy alta (75 a 100 %)",
    ):
        assert rotulo in leyenda
    pagina.reload()
    pagina.wait_for_selector('body[data-listo="1"]')
    assert pagina.input_value("#sel-paleta") == "accesible"  # la preferencia se recuerda
    assert visor.errores == []


MENSAJE_SIN_DATOS = (
    "No existen datos procesados para el periodo seleccionado"  # CU-02, escenario 2
)


def test_cp21_cu02_filtrar_por_fecha_y_departamento(visor: Any) -> None:
    """CU-02, pasos 1 a 3: el Especialista accede al visor, selecciona la fecha y un
    departamento, y el sistema muestra solo las zonas que cumplen los filtros."""
    pagina = visor.abrir("2023-03")  # paso 1 y fecha con mapas almacenados
    pedidas: list[str] = []
    pagina.on("request", lambda r: pedidas.append(r.url) if "/mapas/" in r.url else None)
    pagina.select_option("#sel-departamento", label="Tumbes")  # paso 2
    visor.esperar_teselas()
    susceptibilidad = [u for u in pedidas if "/mapas/susceptibilidad/" in u]
    assert susceptibilidad and all(
        "/2023-03/" in u and "departamento=24" in u for u in susceptibilidad
    )  # paso 3: el contenido de las teselas filtradas se verifica en test_api (CP-21)
    assert pagina.is_hidden("#aviso-periodo")
    assert visor.errores == []


def test_cp21_cu02_3a_fecha_sin_mapas(visor: Any) -> None:
    """CU-02, flujo 3a y escenario 2: fecha sin mapas procesados."""
    pagina = visor.abrir("2023-03")
    pagina.fill("#sel-periodo", "2026-08")  # paso 2 con una fecha sin mapas
    pagina.dispatch_event("#sel-periodo", "change")
    pagina.wait_for_selector("#aviso-periodo:not([hidden])")
    assert pagina.inner_text("#aviso-periodo").strip() == MENSAJE_SIN_DATOS
    assert all("404" not in e for e in visor.errores)  # sin datos no es un error del sistema


def test_cp22_cu04_activar_susceptibilidad_y_desactivar_precipitacion(visor: Any) -> None:
    """CU-04, pasos 1 a 4 y escenario: activa «Mapa de Susceptibilidad» y desactiva
    «Precipitación»; el mapa se actualiza sin recargar la página."""
    pagina = visor.abrir("2023-03")  # paso 1
    # Estado de partida del escenario: precipitación visible y susceptibilidad oculta.
    pagina.check("#capa-precipitacion")
    pagina.uncheck("#capa-susceptibilidad")
    visor.esperar_teselas()
    assert pagina.locator(".leaflet-overlay-pane canvas").count() == 0
    pagina.evaluate("() => { window.__sinRecarga = true; }")
    capas = pagina.locator("fieldset.campo:has(legend:text('Capas'))")  # paso 2: panel de capas
    assert capas.is_visible()
    capas.locator("#capa-susceptibilidad").check()  # paso 3
    capas.locator("#capa-precipitacion").uncheck()
    visor.esperar_teselas()
    # Paso 4: solo la susceptibilidad, en la misma página (sin recarga).
    assert pagina.evaluate("() => window.__sinRecarga === true")
    assert pagina.locator(".leaflet-overlay-pane canvas").count() > 0
    assert pagina.locator(".leaflet-shadow-pane canvas").count() == 0
    assert "Precipitación mensual" not in pagina.inner_text("#leyenda")
    assert "Nivel de susceptibilidad" in pagina.inner_text("#leyenda")
    assert visor.errores == []


def test_cp22_cu04_4a_error_al_mostrar_una_capa(visor: Any) -> None:
    """CU-04, flujo 4a: si falla una capa, aviso junto a su nombre y las demás visibles."""
    pagina = visor.abrir("2023-03")
    pagina.route("**/api/mapas/precipitacion/**", lambda r: r.fulfill(status=500, body="fallo"))
    pagina.check("#capa-precipitacion")
    pagina.wait_for_selector("#error-precipitacion:not([hidden])")
    assert "no está disponible" in pagina.inner_text("#error-precipitacion")
    assert pagina.locator(".leaflet-overlay-pane canvas").count() > 0


def test_cp23_cu02_clic_en_una_zona(visor: Any, motor_bd: Any) -> None:
    """CU-02, pasos 1 a 5 y escenario 1: tras filtrar, un solo clic sobre una zona coloreada
    muestra el valor de susceptibilidad y la TSM, la precipitación y la pendiente de esa zona."""
    pagina = visor.abrir("2023-03")  # paso 1
    pagina.select_option("#sel-departamento", label="Piura")  # paso 2
    visor.esperar_teselas()  # paso 3
    centro = pagina.evaluate(
        "() => { const c = window.mapaVisor.getCenter(); return [c.lat, c.lng]; }"
    )
    with motor_bd.connect() as c:
        zona = c.execute(
            text("""SELECT ST_Y(ST_Transform(ST_Centroid(c.geom), 4326)) AS lat,
                           ST_X(ST_Transform(ST_Centroid(c.geom), 4326)) AS lon
                    FROM ref.celda_analisis c JOIN resultado.susceptibilidad s USING (id_celda)
                    WHERE s.periodo = '2023-03-01' AND left(c.ubigeo_prov, 2) = '20'
                    ORDER BY c.geom <-> ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                                                     32717)
                    LIMIT 1"""),
            {"lat": centro[0], "lon": centro[1]},
        ).one()
    punto = pagina.evaluate(
        "([a, o]) => { const p = window.mapaVisor.latLngToContainerPoint([a, o]);"
        " const r = document.getElementById('mapa').getBoundingClientRect();"
        " return [p.x + r.left, p.y + r.top]; }",
        [zona.lat, zona.lon],
    )
    pagina.mouse.click(*punto)  # paso 4: un solo clic
    ventana = pagina.wait_for_selector("#ventana-consulta", timeout=15000)  # paso 5
    celda = int(ventana.get_attribute("data-celda"))
    texto = ventana.inner_text()
    with motor_bd.connect() as c:
        esperado = c.execute(
            text("""SELECT s.nivel, s.probabilidad::float8 AS p, s.precip_mes_mm::float8 AS m,
                           t.pend_media_g::float8 AS pend, m.anom_tsm::float8 AS tsm,
                           left(ce.ubigeo_prov, 2) AS dep
                    FROM resultado.susceptibilidad s
                    JOIN ref.celda_analisis ce USING (id_celda)
                    JOIN datos.terreno_celda t USING (id_celda)
                    JOIN datos.tsm_mensual m ON m.periodo = s.periodo
                    WHERE s.id_celda = :c AND s.periodo = '2023-03-01'"""),
            {"c": celda},
        ).one()
    niveles = {1: "Baja", 2: "Media", 3: "Alta", 4: "Muy alta"}
    assert esperado.dep == "20"  # la zona pertenece al filtro aplicado
    assert niveles[esperado.nivel] in texto and f"{esperado.p:.4f}" in texto  # valor exacto
    assert f"{esperado.tsm:.2f} °C" in texto  # temperatura superficial del mar
    assert f"{esperado.m:.1f} mm" in texto  # precipitación
    assert f"{esperado.pend:.1f}°" in texto  # pendiente
    assert pagina.locator("#ventana-consulta").count() == 1
    assert visor.errores == []


def test_cp18_cu03_panel_muestra_y_resalta_indicadores(panel: Any) -> None:
    """CU-03, pasos 1 a 3, flujo 3a y escenarios 1 y 2, con la cuenta del Asesor."""
    pagina = panel.pagina
    pagina.goto("https://127.0.0.1:8444/panel/")  # paso 1
    pagina.wait_for_selector('body[data-listo="1"]')  # pasos 2 y 3
    assert pagina.locator(".kpi").count() > 0
    assert pagina.locator('.kpi[data-indicador="AUC-ROC validacion"]').count() == 1
    assert pagina.locator('.kpi.alerta[data-indicador="AUC-ROC validacion"]').count() == 0
    alerta = pagina.locator('.kpi.alerta[data-indicador="PSI anom_tsm"]')
    assert alerta.count() == 1
    assert "Rendimiento por debajo del nivel esperado" in alerta.inner_text()  # escenario 2
    assert panel.errores == []


def test_cp19_cu05_filtrar_errores_y_criterio_sin_registros(panel: Any, motor_bd: Any) -> None:
    """CU-05, pasos 1 a 4, flujo 3a y escenario: filtrar por el tipo Error."""
    pagina = panel.pagina
    pagina.goto("https://127.0.0.1:8444/panel/")  # paso 1
    pagina.wait_for_selector('body[data-listo="1"]')
    pagina.select_option('#form-historial select[name="tipo"]', "ERROR")  # paso 2
    with pagina.expect_response(lambda r: "tipo=ERROR" in r.url):
        pagina.click('#form-historial button[type="submit"]')
    pagina.wait_for_selector('#tabla-historial tr[data-tipo="ERROR"]')  # paso 3
    pagina.wait_for_timeout(300)
    filas = pagina.locator("#tabla-historial tr")
    with motor_bd.connect() as c:
        errores = c.execute(
            text("SELECT count(*) FROM sistema.bitacora WHERE tipo = 'ERROR'")
        ).scalar_one()
    assert filas.count() == errores  # todos los errores registrados
    assert pagina.locator('#tabla-historial tr:not([data-tipo="ERROR"])').count() == 0
    for i in range(filas.count()):  # paso 4: fecha, hora y descripción de cada uno
        celdas = filas.nth(i).locator("td")
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", celdas.nth(0).inner_text())
        assert celdas.nth(3).inner_text().strip()
    pagina.fill('#form-historial input[name="desde"]', "2026-12-31")  # flujo 3a
    pagina.click('#form-historial button[type="submit"]')
    pagina.wait_for_selector("#historial-vacio:not([hidden])")
    assert "No existen registros para el criterio seleccionado" in pagina.inner_text(
        "#historial-vacio"
    )


def test_cu02_especialista_no_ve_el_panel(visor: Any) -> None:
    pagina = visor.pagina
    pagina.goto("https://127.0.0.1:8444/panel/")
    pagina.wait_for_url("**/visor/**", timeout=15000)

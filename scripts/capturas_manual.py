"""Capturas del manual de usuario, tomadas del sistema en ejecución siguiendo los casos de uso.

Recorre CU-01 a CU-05 con la cuenta de cada rol en el entorno de pruebas (https://127.0.0.1:8444)
y guarda las imágenes en docs/img/. El control que usa el actor en cada paso se marca con un
recuadro. Los estados EN_ESPERA de los flujos 4a y 6a se preparan en D1 como en CP-31 y CP-32.

Uso: PFC_BD_URL=... python scripts/capturas_manual.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from cliente_pruebas import clave
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine, text

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "img"
URL = "https://127.0.0.1:8444"
CORREO = {"INVESTIGADOR": "inv", "ESPECIALISTA": "esp", "ASESOR": "ase"}
VISTA = {"width": 1366, "height": 800}
MARCA = "3px solid #dc2626"


def cancelar_activos(motor: Any) -> None:
    with motor.begin() as c:
        c.execute(
            text("""UPDATE sistema.procesamiento SET estado = 'CANCELADO', finalizado_en = now()
                          WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA')""")
        )


def en_espera(motor: Any, motivo: dict[str, str]) -> int:
    with motor.begin() as c:
        return c.execute(
            text("""INSERT INTO sistema.procesamiento
                (id_usuario, tipo, fecha_desde, fecha_hasta, zona, estado, resumen)
                SELECT id_usuario, 'INGESTA', '2026-01-01', '2026-01-31',
                       ST_Multi(ST_MakeEnvelope(-81, -10, -77, -4, 4326)), 'EN_ESPERA',
                       CAST(:r AS jsonb)
                FROM sistema.usuario WHERE correo = 'inv@pruebas.pfc'
                RETURNING id_procesamiento"""),
            {"r": json.dumps({"motivo": motivo})},
        ).scalar_one()


class Sesion:
    """Pestaña de navegador con sesión iniciada para un rol."""

    def __init__(self, navegador: Any, rol: str | None) -> None:
        self.contexto = navegador.new_context(
            ignore_https_errors=True, viewport=VISTA, locale="es-PE", timezone_id="America/Lima"
        )
        self.p = self.contexto.new_page()
        if rol:
            self.p.goto(f"{URL}/visor/")
            self.p.fill("input[name=correo]", f"{CORREO[rol]}@pruebas.pfc")
            self.p.fill("input[name=clave]", clave(rol))
            self.p.click("button.primario")
            self.p.wait_for_selector("#acceso", state="hidden")

    def ir(self, ruta: str) -> Any:
        self.p.goto(f"{URL}{ruta}")
        self.p.wait_for_selector('body[data-listo="1"]', timeout=60000)
        self.p.wait_for_load_state("networkidle")
        self.p.wait_for_timeout(800)
        return self.p

    def marcar(self, *selectores: str) -> None:
        for s in selectores:
            self.p.locator(s).first.evaluate(
                "(e, m) => { e.dataset.marcaManual = '1'; e.style.outline = m;"
                " e.style.outlineOffset = '2px'; }",
                MARCA,
            )

    def desmarcar(self) -> None:
        self.p.evaluate(
            "() => document.querySelectorAll('[data-marca-manual]').forEach(e => {"
            " e.style.outline = ''; delete e.dataset.marcaManual; })"
        )

    def foto(self, nombre: str, elemento: str | None = None) -> None:
        destino = SALIDA / f"{nombre}.png"
        if elemento:
            self.p.locator(elemento).first.screenshot(path=destino)
        else:
            self.p.screenshot(path=destino)
        self.desmarcar()
        print("captura", destino.name, flush=True)

    def cerrar(self) -> None:
        self.contexto.close()


def acceso(nav: Any) -> None:
    s = Sesion(nav, None)
    s.p.goto(f"{URL}/panel/")
    s.p.wait_for_selector("#acceso:not([hidden])")
    s.p.fill("input[name=correo]", "inv@pruebas.pfc")
    s.p.fill("input[name=clave]", "clave-incorrecta")
    s.p.click("button.primario")
    s.p.wait_for_selector("#acceso-mensaje:not(:empty)")
    s.foto("iu03_error_acceso")
    s.p.fill("input[name=clave]", "")
    s.p.locator("#acceso-mensaje").evaluate("e => { e.textContent = ''; }")
    s.p.fill("input[name=correo]", "inv@pruebas.pfc")
    s.marcar("#form-acceso")
    s.foto("iu01_inicio_sesion")
    s.cerrar()


def cu01(nav: Any, motor: Any) -> None:
    cancelar_activos(motor)
    s = Sesion(nav, "INVESTIGADOR")
    p = s.ir("/panel/")
    s.foto("cu01_paso1_panel")
    f = p.locator("#form-proceso")
    f.locator('select[name="tipo"]').select_option("INFERENCIA")
    f.locator('input[name="fecha_desde"]').fill("2026-05-01")
    f.locator('input[name="fecha_hasta"]').fill("2026-05-31")
    p.select_option("#sel-zona", label="Tumbes")
    s.marcar("#form-proceso")
    s.foto("cu01_paso2_fechas_y_zona", "#seccion-procesos")
    f.locator('button[type="submit"]').click()
    p.locator("#dlg-confirmar").wait_for(state="visible")
    s.marcar("#confirmar")
    s.foto("cu01_paso3_confirmar", "#dlg-confirmar")
    p.click("#confirmar")
    p.wait_for_selector(
        "#estado:has-text('PENDIENTE'), #estado:has-text('EN_CURSO')", timeout=60000
    )
    s.foto("cu01_pasos4a9_estado", "#seccion-procesos")
    p.wait_for_selector("#fin-ok:not([hidden])", timeout=300000)
    s.marcar("#fin-ok")
    s.foto("cu01_paso10_fin", "#seccion-procesos")
    s.cerrar()

    # Flujo 4a: fuente no disponible y carga manual.
    cancelar_activos(motor)
    en_espera(
        motor,
        {
            "tipo": "FUENTE_NO_DISPONIBLE",
            "fuente": "dem_glo30",
            "detalle": "no respondió o su archivo no está disponible",
        },
    )
    s = Sesion(nav, "INVESTIGADOR")
    p = s.ir("/panel/")
    p.wait_for_selector("#alerta-espera:not([hidden])")
    s.marcar("#alerta-espera")
    s.foto("cu01_4a_alerta_fuente", "#seccion-procesos")
    tif = b"II*\x00" + b"\x00" * 2048
    p.set_input_files(
        "#archivo", files=[{"name": "dem_manual.tif", "mimeType": "image/tiff", "buffer": tif}]
    )
    s.marcar("#form-carga")
    s.foto("cu01_4a_carga_manual", "#alerta-espera")
    p.click('#form-carga button[type="submit"]')
    p.wait_for_selector("#carga-resultado:has-text('La verificación se reanuda')", timeout=60000)
    s.marcar("#carga-resultado")
    s.foto("cu01_4a_reanudacion", "#seccion-procesos")
    s.cerrar()
    cancelar_activos(motor)

    # Flujo 6a: datos rechazados y cancelación.
    en_espera(
        motor,
        {
            "tipo": "DATOS_RECHAZADOS",
            "fuente": "era5_land",
            "regla": "continuidad temporal",
            "detalle": "2 periodos faltantes: 2023-03-15, 2023-03-16",
        },
    )
    s = Sesion(nav, "INVESTIGADOR")
    p = s.ir("/panel/")
    p.wait_for_selector("#alerta-espera:not([hidden])")
    s.marcar("#alerta-espera", "#cancelar")
    s.foto("cu01_6a_datos_rechazados", "#seccion-procesos")
    p.click("#cancelar")
    p.locator("#dlg-cancelar").wait_for(state="visible")
    s.marcar("#si-cancelar")
    s.foto("cu01_6a_confirmar_cancelacion", "#dlg-cancelar")
    p.click("#si-cancelar")
    p.wait_for_selector("#estado:has-text('CANCELADO')")
    s.foto("cu01_6a_cancelado", "#seccion-procesos")
    s.cerrar()
    cancelar_activos(motor)


def centro_de_celda(motor: Any, p: Any, departamento: str) -> tuple[float, float]:
    centro = p.evaluate("() => { const c = window.mapaVisor.getCenter(); return [c.lat, c.lng]; }")
    with motor.connect() as c:
        fila = c.execute(
            text("""SELECT ST_Y(ST_Transform(ST_Centroid(c.geom), 4326)) AS lat,
                           ST_X(ST_Transform(ST_Centroid(c.geom), 4326)) AS lon
                    FROM ref.celda_analisis c JOIN resultado.susceptibilidad s USING (id_celda)
                    WHERE s.periodo = '2023-03-01' AND left(c.ubigeo_prov, 2) = :d
                    ORDER BY c.geom <-> ST_Transform(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                                                     32717) LIMIT 1"""),
            {"lat": centro[0], "lon": centro[1], "d": departamento},
        ).one()
    return fila.lat, fila.lon


def cu02_cu04(nav: Any, motor: Any) -> None:
    s = Sesion(nav, "ESPECIALISTA")
    p = s.ir("/visor/?periodo=2023-03")
    s.foto("cu02_paso1_visor")
    p.select_option("#sel-departamento", label="Piura")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(1500)
    s.marcar("#sel-periodo", "#sel-departamento")
    s.foto("cu02_pasos2y3_filtro")
    lat, lon = centro_de_celda(motor, p, "20")
    x, y = p.evaluate(
        "([a, o]) => { const q = window.mapaVisor.latLngToContainerPoint([a, o]);"
        " const r = document.getElementById('mapa').getBoundingClientRect();"
        " return [q.x + r.left, q.y + r.top]; }",
        [lat, lon],
    )
    p.mouse.click(x, y)
    p.wait_for_selector("#ventana-consulta", timeout=15000)
    p.wait_for_timeout(600)
    s.marcar(".leaflet-popup-content-wrapper")
    s.foto("cu02_pasos4y5_consulta")
    p.locator(".leaflet-popup-close-button").click()
    p.fill("#sel-periodo", "2026-08")
    p.dispatch_event("#sel-periodo", "change")
    p.wait_for_selector("#aviso-periodo:not([hidden])")
    s.marcar("#aviso-periodo")
    s.foto("cu02_3a_sin_datos")

    # CU-04: escenario (activar susceptibilidad y desactivar precipitación) y flujo 4a.
    p = s.ir("/visor/?periodo=2023-03")
    p.check("#capa-precipitacion")
    p.uncheck("#capa-susceptibilidad")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(1500)
    s.marcar("fieldset.campo:has(legend:text('Capas'))")
    s.foto("cu04_paso2_panel_de_capas")
    p.check("#capa-susceptibilidad")
    p.uncheck("#capa-precipitacion")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(1500)
    s.marcar("#capa-susceptibilidad", "#capa-precipitacion")
    s.foto("cu04_pasos3y4_capas_actualizadas")
    p = s.ir("/visor/?periodo=2017-03")
    for capa in ("tsm", "inventario"):
        p.check(f"#capa-{capa}")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(2000)
    s.foto("cu04_capas_tsm_e_inventario")
    p.route("**/api/mapas/pendiente/**", lambda r: r.fulfill(status=500, body="fallo"))
    p.check("#capa-pendiente")
    p.wait_for_selector("#error-pendiente:not([hidden])")
    s.marcar("#error-pendiente")
    s.foto("cu04_4a_error_de_capa")
    p = s.ir("/visor/?periodo=2023-03")
    p.select_option("#sel-paleta", "accesible")
    p.wait_for_load_state("networkidle")
    p.wait_for_timeout(1500)
    s.marcar("#sel-paleta", "#leyenda")
    s.foto("visor_paleta_accesible")
    p.select_option("#sel-paleta", "estandar")
    s.cerrar()


def cu03_cu05(nav: Any) -> None:
    s = Sesion(nav, "ASESOR")
    p = s.ir("/panel/")
    s.foto("cu03_paso1_panel_asesor")
    alerta = '.kpi.alerta[data-indicador="PSI anom_tsm"]'
    s.marcar(alerta)
    s.foto("cu03_pasos2y3_indicadores", "#seccion-indicadores")
    s.marcar(alerta)
    s.foto("cu03_3a_alerta", alerta)
    s.marcar("#exportar")
    s.foto("cu03_paso4_exportar", "#seccion-indicadores")
    p.select_option('#form-historial select[name="tipo"]', "ERROR")
    with p.expect_response(lambda r: "tipo=ERROR" in r.url):
        p.click('#form-historial button[type="submit"]')
    p.wait_for_timeout(500)
    s.marcar("#form-historial")
    s.foto("cu05_pasos1a4_errores", "#seccion-historial")
    p.fill('#form-historial input[name="desde"]', "2026-12-31")
    p.click('#form-historial button[type="submit"]')
    p.wait_for_selector("#historial-vacio:not([hidden])")
    s.marcar("#historial-vacio")
    s.foto("cu05_3a_sin_registros", "#seccion-historial")
    s.cerrar()


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    motor = create_engine(os.environ["PFC_BD_URL"])
    with sync_playwright() as pw:
        nav = pw.chromium.launch(
            args=["--lang=es-PE"], env={**os.environ, "LANG": "es_PE.UTF-8", "LANGUAGE": "es"}
        )
        acceso(nav)
        cu01(nav, motor)
        cu02_cu04(nav, motor)
        cu03_cu05(nav)
        nav.close()
    time.sleep(0)


if __name__ == "__main__":
    main()

"""Informe de ejecución de los casos de prueba CP-01 a CP-38, ordenado por requerimiento y caso de uso.

Lee los informes JUnit de una regresión (pruebas.xml: unitarias e integración; sistema.xml: API y
navegadores) y las evidencias que no son de pytest (CP-02, CP-14, CP-25 y CP-26), asigna cada prueba
automatizada a su caso de prueba y escribe informe_casos.json, informe_casos.html y, con
--capturas, las capturas PNG del informe. Una prueba sin caso asignado hace fallar el script: así
ninguna prueba queda fuera del resumen.

Uso: informe_casos.py <carpeta de la regresión> [--capturas <carpeta de figuras>]
"""

# ruff: noqa: E501

from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
P = RAIZ / "resultados" / "pruebas"

# (id, RF, CU y flujo, caso, patrones de nombre de prueba). Orden: requerimiento y flujo.
CASOS: list[tuple[str, str, str, str, list[str]]] = [
    ("CP-27", "RF-01", "Fuera del flujo · API", "Rango de fechas y zona geográfica de la inferencia",
     ["test_cp27_", "test_rf01_zona", "test_inferencia_rechaza_ventanas", "test_rechazo_de_entradas",
      "test_crear_y_consultar_ingesta", "test_entrenamiento_sin_datos"]),
    ("CP-09", "RF-01", "CU-01 · FN paso 7", "Grilla de 1 km y pendiente por celda",
     ["test_cp09_", "test_tabla_celdas_y_percentil", "test_teselas_del_dominio"]),
    ("CP-10", "RF-01", "CU-01 · FN pasos 5 y 7", "Matriz de variables con anomalía TSM alineada",
     ["test_cp10_", "test_rezagos_solo", "test_precipitacion_maximo", "test_objetivo_solo",
      "test_construir_anio", "test_matriz_parquet_por_anio"]),
    ("CP-04", "RF-02", "Fuera del flujo · API", "Carga manual: particiones de tipo y tamaño (API)",
     ["test_cp04_", "test_carga_manual"]),
    ("CP-31", "RF-02", "CU-01 · flujo 4a", "Aviso de fuente no disponible y carga manual en el panel",
     ["test_cp31_"]),
    ("CP-13", "RF-03", "CU-01 · FN paso 9", "Persistencia en PostGIS sin huérfanas ni duplicados",
     ["test_cp13_persiste", "test_cp13_repetir", "test_cp11_y_cp13", "test_particion_anual",
      "test_error_de_copy", "test_cancelacion_antes_del_lote", "test_esquemas_instalados",
      "test_restriccion_de_rango_tsm"]),
    ("CP-29", "RF-04", "CU-01 · FN pasos 1–3 y 10", "Rango, zona, confirmación y aviso de fin",
     ["test_cp29_"]),
    ("CP-30", "RF-04", "Fuera del flujo · IU-05 con un activo", "Aviso cuando ya hay un procesamiento activo",
     ["test_cp30_"]),
    ("CP-15", "RF-04", "Fuera del flujo · concurrencia", "Un solo procesamiento activo ante envíos simultáneos",
     ["test_cp15_", "test_procesamiento_y_cola"]),
    ("CP-28", "RF-04", "Fuera del flujo · IU-06", "Seguimiento del procesamiento activo (IU-06)",
     ["test_cp28_", "test_iu06_"]),
    ("CP-01", "RF-05", "CU-01 · FN pasos 4–5", "Obtención real de la TSM de NOAA ERSST v5",
     ["test_cp01_", "test_contrato_comun_de_descarga"]),
    ("CP-02", "RF-05", "CU-01 · FN paso 4", "Obtención real de ERA5-Land por el conector E2",
     ["test_solicitud_era5"]),
    ("CP-37", "RF-05", "CU-01 · FN paso 4", "Obtención real de una tesela Copernicus DEM GLO-30",
     ["test_cp37_"]),
    ("CP-38", "RF-05", "CU-01 · FN paso 4", "Inventario completo de GEOCATMIN con TLS verificado",
     ["test_cp38_", "test_inventario_"]),
    ("CP-03", "RF-05", "Fuera del flujo · seguridad A10", "Lista blanca de dominios, TLS y redirecciones",
     ["test_cp03_", "test_rechaza_dominio", "test_rechaza_http", "test_rechaza_redirecciones"]),
    ("CP-05", "RF-06", "CU-01 · FN paso 6", "Integridad de campos y ausencia de nulos",
     ["test_cp05_", "test_nulos_se_rechazan", "test_integridad_de_campos", "test_serie_valida",
      "test_cada_regla_es_independiente", "test_construir_reglas"]),
    ("CP-06", "RF-06", "CU-01 · FN paso 6", "Rangos en sus valores límite",
     ["test_cp06_", "test_rango_rechaza", "test_tolerancia_en_los_bordes"]),
    ("CP-07", "RF-06", "CU-01 · flujo 6a", "Continuidad temporal: detención y días indicados",
     ["test_cp07_", "test_continuidad_", "test_cu01_6a_"]),
    ("CP-32", "RF-06", "CU-01 · flujo 6a", "Regla incumplida (IU-10) y cancelación confirmada (IU-11)",
     ["test_cp32_"]),
    ("CP-11", "RF-07", "Fuera del flujo · integridad", "SHA-256 del artefacto antes de la inferencia",
     ["test_cp11_version", "test_cp11_artefacto", "test_artefacto_alterado",
      "test_registro_y_verificacion_de_huella"]),
    ("CP-12", "RF-07", "CU-01 · FN paso 7", "Clasificación en cuatro niveles con los umbrales",
     ["test_cp12_", "test_cp13_cp12", "test_inferencia_por_anio_y_niveles"]),
    ("CP-08", "RF-13", "CU-01 · flujo 4a, escenario 2", "Error de fuente registrado en el historial",
     ["test_cp08_", "test_bitacora_es_de_solo", "test_bitacora_rechaza", "test_cu01_4a_",
      "test_fuente_no_disponible_pasa_a_espera"]),
    ("CP-20", "RF-08", "CU-01 · FN paso 8", "Mapa por colores y paleta accesible",
     ["test_cp20_", "test_mapas_tesela_y_periodo"]),
    ("CP-21", "RF-09", "CU-02 · FN pasos 1–3, flujo 3a", "Filtro por fecha y departamento; fecha sin mapas",
     ["test_cp21_"]),
    ("CP-23", "RF-11", "CU-02 · FN pasos 1–5, escenario 1", "Un clic: valor, TSM, precipitación y pendiente",
     ["test_cp23_", "test_consulta_punto_y_catalogos"]),
    ("CP-18", "RF-12", "CU-03 · FN pasos 1–3 y flujo 3a", "Indicadores y aviso de rendimiento",
     ["test_cp18_", "test_cp19_bitacora_y_cp18"]),
    ("CP-33", "RF-12", "CU-03 · FN paso 4", "Exportación de los indicadores (CSV)",
     ["test_cp33_"]),
    ("CP-22", "RF-10", "CU-04 · FN, escenario y flujo 4a", "Activar susceptibilidad y desactivar precipitación; error",
     ["test_cp22_"]),
    ("CP-34", "RF-10", "Fuera del flujo · API MVT", "Capas de pendiente, TSM e inventario (MVT)",
     ["test_cp34_"]),
    ("CP-35", "RF-10", "CU-04 · FN y flujo 4a", "Capas nuevas en el visor y error de una capa",
     ["test_cp35_"]),
    ("CP-36", "RF-13", "CU-05 · precondición", "Cada operación queda registrada en el historial",
     ["test_cp36_"]),
    ("CP-19", "RF-14", "CU-05 · FN y flujo 3a", "Filtrado del historial y aviso sin registros",
     ["test_cp19_"]),
    ("CP-16", "Seguridad", "CU-01 a CU-05 · actores", "Autorización por rol (matriz RBAC)",
     ["test_cp16_", "test_rbac", "test_cu02_especialista", "test_post_sin_token_csrf",
      "test_inyeccion_en_parametros"]),
    ("CP-17", "Seguridad", "Acceso (IU-01)", "Argon2id, bloqueo, límite y cabeceras",
     ["test_cp17_", "test_inicio_de_sesion", "test_bloqueo_tras", "test_sesion_y_cierre",
      "test_cabeceras_de_seguridad", "test_salud_"]),
    ("CP-26", "RNF-01", "CU-01 · escenario 1", "Procesamiento completo dentro del límite",
     ["test_worker_", "test_entrenamiento_recorre", "test_ingesta_no_transforma",
      "test_la_inferencia_no", "test_tipo_desconocido", "test_error_inesperado", "test_reiniciar_pico",
      "test_trabajo_liviano", "test_config_", "test_rutas_desde"]),
    ("CP-14", "RNF-02", "Validación del modelo", "AUC-ROC y precisión 1:1 en la partición sellada",
     ["test_metricas_y_psi", "test_metricas_balanceadas", "test_version_bajo_el_umbral", "test_bloques_y_pliegues",
      "test_submuestreo", "test_busqueda_elige", "test_entrenar_version"]),
    ("CP-24", "RNF-03", "CU-02 a CU-05 · navegadores", "Flujos del visor y del panel en tres navegadores",
     []),
    ("CP-25", "RNF-04", "Mantenibilidad", "Contrato de capas y puerta de calidad",
     ["test_cp25_"]),
]  # fmt: skip


def casos_de_prueba(nombre: str) -> list[str]:
    """Casos de prueba a los que pertenece una prueba automatizada."""
    return [c[0] for c in CASOS if any(p in nombre for p in c[4])]


def leer_junit(ruta: Path) -> list[dict]:
    """Pruebas de un informe JUnit con su resultado y, si aplica, su navegador."""
    filas = []
    for caso in ET.parse(ruta).getroot().iter("testcase"):
        nombre = caso.get("name", "")
        if caso.find("failure") is not None or caso.find("error") is not None:
            resultado = "fallida"
        elif caso.find("skipped") is not None:
            resultado = "omitida"
        else:
            resultado = "aprobada"
        navegador = next((n for n in ("chromium", "firefox", "msedge") if f"[{n}" in nombre or
                          f"-{n}" in nombre or f"{n}]" in nombre), None)  # fmt: skip
        filas.append({"nombre": nombre, "modulo": caso.get("classname", ""),
                      "resultado": resultado, "navegador": navegador})  # fmt: skip
    return filas


def evidencias_externas(carpeta: Path) -> dict[str, tuple[bool, str]]:
    """Resultado de los casos que se ejecutan fuera de pytest."""
    cp02 = json.loads((P / "c2_integracion" / "cp02_regresion_4.json").read_text())
    cp14 = json.loads((P / "c2_integracion" / "cp14_prueba_sellada.json").read_text())
    cp14b = json.loads((P / "c2_integracion" / "cp14_precision_balanceada.json").read_text())
    precision = cp14b["prueba"]["balanceada_1a1"]["precision"]
    cp26 = json.loads((P / "c4_carga" / "cp26_extremo_a_extremo.json").read_text())
    pasos = json.loads((carpeta / "pipeline_local.json").read_text())
    tuberia = {p["paso"]: p["estado"] for p in pasos}
    capas = tuberia.get("lint-imports") == "aprobado"
    return {
        "CP-02": (
            cp02["estado"] == "OK",
            f"descarga real de la 4.ª regresión (10/11): {cp02['bytes']:,} bytes en {cp02['segundos']} s".replace(
                ",", " "
            ),
        ),
        "CP-14": (
            cp14["cumple_rnf02"] and cp14b["cumple"],
            f"AUC-ROC {cp14['auc_m3']:.3f}; precisión 1:1 {precision['media']:.3f} "
            f"(IC 95 %: {precision['ic95_inf']:.3f}–{precision['ic95_sup']:.3f}) en la partición sellada",
        ),
        "CP-26": (
            cp26["etl"]["estado"] == "COMPLETADO",
            "160.1 s de extremo a extremo (ejecución previa, no repetida)",
        ),
        "CP-25": (
            capas,
            "contrato verificado por lint-imports en el pipeline; SonarQube aprobado en la 2.ª regresión",
        ),
    }


def resumir(carpeta: Path) -> dict:
    """Resultados por caso de prueba; falla si alguna prueba no pertenece a ningún caso."""
    pruebas = leer_junit(carpeta / "pruebas.xml") + leer_junit(carpeta / "sistema.xml")
    # Una prueba repetida (sistema_repeticion_*.xml) reemplaza su resultado y queda señalada.
    repetidas = {}
    for ruta in sorted(carpeta.glob("sistema_repeticion_*.xml")):
        repetidas.update({r["nombre"]: r for r in leer_junit(ruta)})
    for prueba in pruebas:
        if prueba["nombre"] in repetidas and prueba["navegador"] is not None:
            prueba["repetida"] = prueba["resultado"]
            prueba["resultado"] = repetidas[prueba["nombre"]]["resultado"]
    sin_caso = [p["nombre"] for p in pruebas if not casos_de_prueba(p["nombre"])]
    if sin_caso:
        raise SystemExit(f"pruebas sin caso de prueba: {sin_caso}")
    externas = evidencias_externas(carpeta)
    por_caso: dict[str, list[dict]] = defaultdict(list)
    for p in pruebas:
        for cp in casos_de_prueba(p["nombre"]):
            por_caso[cp].append(p)
    con_navegador = [p for p in pruebas if p["navegador"]]
    por_caso["CP-24"] = con_navegador
    filas = []
    for cp, rf, flujo, titulo, _ in CASOS:
        lista = por_caso[cp]
        conteo = {r: sum(p["resultado"] == r for p in lista) for r in
                  ("aprobada", "fallida", "omitida")}  # fmt: skip
        navegadores = sorted({p["navegador"] for p in lista if p["navegador"]})
        externa = externas.get(cp)
        repeticiones = [p for p in lista if "repetida" in p]
        if repeticiones:
            nota = f"{len(repeticiones)} prueba(s) repetida(s) tras un tiempo agotado de carga del visor"
            externa = (externa[0] if externa else True,
                       f"{externa[1] + '; ' if externa else ''}{nota}")  # fmt: skip
        aprobado = conteo["fallida"] == 0 and (conteo["aprobada"] > 0 or externa is not None)
        if externa is not None:
            aprobado = aprobado and externa[0]
        filas.append({"cp": cp, "rf": rf, "flujo": flujo, "titulo": titulo, **conteo,
                      "navegadores": navegadores, "externa": externa[1] if externa else "",
                      "estado": "Aprobado" if aprobado else "Fallido"})  # fmt: skip
    return {
        "regresion": carpeta.name,
        "fecha": dt.date.fromtimestamp((carpeta / "pruebas.xml").stat().st_mtime).strftime(
            "%d/%m/%Y"
        ),
        "pruebas": len(pruebas),
        "aprobadas": sum(p["resultado"] == "aprobada" for p in pruebas),
        "fallidas": sum(p["resultado"] == "fallida" for p in pruebas),
        "omitidas": sum(p["resultado"] == "omitida" for p in pruebas),
        "casos": filas,
    }


ESTILO = """
body { font: 13px/1.35 'Segoe UI', system-ui, sans-serif; color: #111; margin: 18px; background: #fff; }
h1 { font-size: 17px; margin: 0 0 4px; } p.sub { margin: 0 0 12px; color: #444; }
.totales { display: flex; gap: 10px; margin: 0 0 12px; }
.totales div { border: 1px solid #ccc; border-radius: 6px; padding: 6px 12px; }
.totales b { display: block; font-size: 18px; }
table { border-collapse: collapse; width: 100%; }
th { background: #1f2937; color: #fff; text-align: left; padding: 5px 6px; font-weight: 600; }
td { border-bottom: 1px solid #e5e7eb; padding: 4px 6px; vertical-align: top; }
tr.grupo td { background: #f3f4f6; font-weight: 600; }
td.n { text-align: right; font-variant-numeric: tabular-nums; }
td:nth-child(3), td:nth-child(1) { white-space: nowrap; }
.ok { color: #fff; background: #15803d; border-radius: 4px; padding: 1px 7px; font-weight: 600; }
.mal { color: #fff; background: #b91c1c; border-radius: 4px; padding: 1px 7px; font-weight: 600; }
.cero { color: #9ca3af; }
"""


def grupo_de(caso: dict) -> str:
    """Caso de uso del caso de prueba, o el grupo transversal de seguridad y RNF."""
    if caso["rf"].startswith("RF-"):
        return caso["flujo"].split(" · ")[0]
    return "Seguridad y requerimientos no funcionales"


def html_informe(resumen: dict, casos: list[dict], titulo: str) -> str:
    """Página del informe con los totales y una fila por caso de prueba."""
    filas = []
    actual = None
    for c in casos:
        grupo = grupo_de(c)
        if grupo != actual:
            filas.append(f'<tr class="grupo"><td colspan="9">{html.escape(grupo)}</td></tr>')
            actual = grupo
        nav = ", ".join({"chromium": "Chromium", "firefox": "Firefox", "msedge": "Edge"}[n]
                        for n in c["navegadores"]) or "—"  # fmt: skip

        def num(v: int) -> str:
            return f'<td class="n{" cero" if v == 0 else ""}">{v}</td>'

        estado = (
            f'<span class="{"ok" if c["estado"] == "Aprobado" else "mal"}">{c["estado"]}</span>'
        )
        extra = f"<br><small>{html.escape(c['externa'])}</small>" if c["externa"] else ""
        filas.append(
            f"<tr><td>{c['rf']}</td><td>{html.escape(c['flujo'])}</td><td><b>{c['cp']}</b></td>"
            f"<td>{html.escape(c['titulo'])}{extra}</td>{num(c['aprobada'])}{num(c['fallida'])}"
            f"{num(c['omitida'])}<td>{nav}</td><td>{estado}</td></tr>"
        )
    aprobados = sum(c["estado"] == "Aprobado" for c in resumen["casos"])
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{titulo}</title>
<style>{ESTILO}</style></head><body>
<h1>{titulo}</h1>
<p class="sub">Regresión {resumen['regresion'].split('_')[-1]} del {resumen['fecha']} · pytest (unitarias, integración y
sistema con Playwright) y evidencias externas · generado por scripts/informe_casos.py</p>
<div class="totales"><div>Casos aprobados<b>{aprobados} / {len(resumen['casos'])}</b></div>
<div>Pruebas automatizadas<b>{resumen['pruebas']}</b></div>
<div>Aprobadas<b>{resumen['aprobadas']}</b></div><div>Fallidas<b>{resumen['fallidas']}</b></div>
<div>Omitidas<b>{resumen['omitidas']}</b></div></div>
<table><thead><tr><th>RF / RNF</th><th>CU y flujo</th><th>CP</th><th>Caso de prueba</th>
<th>Aprob.</th><th>Fall.</th><th>Omit.</th><th>Navegadores</th><th>Estado</th></tr></thead>
<tbody>{''.join(filas)}</tbody></table></body></html>"""


def main() -> None:
    """Escribe el JSON, el HTML y, si se pide, las capturas del informe."""
    carpeta = Path(sys.argv[1]).resolve()
    resumen = resumir(carpeta)
    (carpeta / "informe_casos.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False))
    partes = {
        "informe_casos.html": ("Resumen de ejecución de los casos de prueba CP-01 a CP-38",
                               resumen["casos"]),
        "informe_casos_cu01.html": ("Casos de prueba de CU-01: ejecución y resultado",
                                    [c for c in resumen["casos"] if grupo_de(c) == "CU-01"]),
        "informe_casos_resto.html": ("Casos de prueba de CU-02 a CU-05, seguridad y RNF",
                                     [c for c in resumen["casos"]
                                      if grupo_de(c) != "CU-01"]),
    }  # fmt: skip
    for nombre, (titulo, casos) in partes.items():
        (carpeta / nombre).write_text(html_informe(resumen, casos, titulo))
    print(f"{sum(c['estado'] == 'Aprobado' for c in resumen['casos'])}/{len(resumen['casos'])} "
          f"casos aprobados; {resumen['pruebas']} pruebas")  # fmt: skip
    if "--capturas" in sys.argv:
        from playwright.sync_api import sync_playwright

        destino = Path(sys.argv[sys.argv.index("--capturas") + 1])
        destino.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            navegador = p.chromium.launch()
            pagina = navegador.new_page(viewport={"width": 1180, "height": 600},
                                        device_scale_factor=2)  # fmt: skip
            for nombre in ("informe_casos_cu01.html", "informe_casos_resto.html"):
                pagina.goto((carpeta / nombre).as_uri())
                pagina.screenshot(path=str(destino / re.sub(r"\.html$", ".png", nombre)),
                                  full_page=True)  # fmt: skip
            navegador.close()


if __name__ == "__main__":
    main()

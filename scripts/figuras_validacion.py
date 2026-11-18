"""Figuras de evidencia del capítulo 3 a partir de los resultados reales de las pruebas.

Reemplazan a figuras/placeholder_prueba_NN.png. Las capturas se toman con el entorno en ejecución
(Playwright); las gráficas leen los archivos de resultados/pruebas, sin valores escritos a mano."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import estilo  # noqa: F401 - aplica el estilo común
import matplotlib.pyplot as plt
from matplotlib.image import imread
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
P = RAIZ / "resultados" / "pruebas"
D = RAIZ / "resultados" / "figuras" / "validacion"
URL = "https://127.0.0.1:8444"
REG = P / "c5_regresion_2"  # segunda regresión, tras ZAP, Trivy y SonarQube


def contar_junit(ruta: Path, carpeta: str = "") -> tuple[int, int, int]:
    """Pruebas ejecutadas, fallidas y omitidas; `carpeta` filtra por el nivel de la pirámide."""
    casos = [
        c for c in ET.parse(ruta).getroot().iter("testcase") if carpeta in c.get("classname", "")
    ]
    fallas = sum(c.find("failure") is not None or c.find("error") is not None for c in casos)
    omitidas = sum(c.find("skipped") is not None for c in casos)
    return len(casos) - omitidas, fallas, omitidas


def fig01_piramide() -> None:
    uni = contar_junit(REG / "pruebas.xml", "unitarias")[0]
    integ = contar_junit(REG / "pruebas.xml", "integracion")[0]
    sis = contar_junit(REG / "sistema.xml")[0]
    niveles = [
        ("Aceptación (UAT)", 0, "6 escenarios preparados; sesión pendiente", "#c3c2b7"),
        ("Sistema (HTTPS; Chromium, Firefox y Edge)", sis, "", "#eb6834"),
        ("Integración (PostGIS y datos reales)", integ, "", "#1baf7a"),
        ("Unitarias", uni, "", "#2a78d6"),
    ]
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.grid(False)
    anchos = [0.56, 0.66, 0.8, 0.96]
    for i, ((nombre, n, nota, color), ancho) in enumerate(zip(niveles, anchos, strict=True)):
        y = len(niveles) - 1 - i
        ax.barh(y, ancho, left=(1 - ancho) / 2, color=color, height=0.86, edgecolor="#fcfcfb")
        rotulo = f"{nombre}\n{nota}" if nota else f"{nombre}\n{n} pruebas ejecutadas"
        ax.text(0.5, y, rotulo, ha="center", va="center", fontsize=8.5,
                color="#0b0b0b" if color == "#c3c2b7" else "#ffffff", fontweight="bold")  # fmt: skip
    ax.set_xlim(0, 1)
    ax.axis("off")
    fig.savefig(D / "placeholder_prueba_01.png")


def fig02_cronograma() -> None:
    ciclos = json.loads((P / "ciclos.json").read_text())
    fig, ax = plt.subplots(figsize=(8, 3.5))
    etiquetas = []
    for i, c in enumerate(reversed(ciclos)):
        ini = dt.date.fromisoformat(c["plan"][0])
        fin = dt.date.fromisoformat(c["plan"][1])
        ax.barh(i + 0.18, (fin - ini).days + 1, left=ini.toordinal(), height=0.32,
                color="#9ec5f4", label="Línea base" if i == 0 else None)  # fmt: skip
        if c["real"]:
            r0 = dt.date.fromisoformat(c["real"][0])
            r1 = dt.date.fromisoformat(c["real"][1])
            ax.barh(i - 0.18, (r1 - r0).days + 1, left=r0.toordinal(), height=0.32,
                    color="#184f95", label="Ejecución real" if i == 1 else None)  # fmt: skip
        else:
            ax.text(
                ini.toordinal() - 1,
                i - 0.18,
                "pendiente",
                va="center",
                ha="right",
                fontsize=8,
                color="#a32828",
            )
        etiquetas.append(c["nombre"])
    ax.set_yticks(range(len(etiquetas)), etiquetas)
    marcas = [dt.date(2026, 11, d) for d in (2, 9, 16, 23, 30)] + [
        dt.date(2026, 12, d) for d in (7, 14)
    ]
    ax.set_xticks([m.toordinal() for m in marcas], [m.strftime("%d/%m") for m in marcas])
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", ncols=2)
    ax.set_xlabel("Fecha de 2026")
    fig.savefig(D / "placeholder_prueba_02.png")


def capturas_cobertura(p) -> None:  # noqa: ANN001
    html = REG / "htmlcov"
    b = p.chromium.launch()
    g = b.new_page(viewport={"width": 1280, "height": 760}, device_scale_factor=2)
    g.goto(f"file://{html}/index.html")
    g.fill("#filter", "pfc_predictiva/inferencia")
    g.wait_for_timeout(500)
    g.screenshot(
        path=str(D / "placeholder_prueba_03.png"),
        clip={"x": 0, "y": 0, "width": 1280, "height": 260},
    )
    b.close()


def fig04_locust() -> None:
    """Escenario D escalonado: p95 y tasa lograda frente a la carga ofrecida, con y sin inferencia."""
    E = P / "c4_carga_escalonada"
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.6, 3.8))
    maximo = 0
    for modo, nombre, color in [("solo", "Visor solo", "#2a78d6"),
                                ("inferencia", "Durante la inferencia masiva", "#eb6834")]:  # fmt: skip
        filas = json.loads((E / f"escalonada_{modo}.json").read_text())["escalones"]
        x = [f["objetivo_rps"] for f in filas]
        maximo = max(maximo, *x)
        a.plot(x, [f["p95_ms"] / 1000 for f in filas], "o-", color=color, label=nombre)
        b.plot(x, [f["lograda_rps"] for f in filas], "o-", color=color, label=nombre)
        ok = [f for f in filas if f["cumple_umbral"]][-1]
        a.annotate(f"máx. {ok['objetivo_rps']} sol./s", (ok["objetivo_rps"], ok["p95_ms"] / 1000),
                   textcoords="offset points", xytext=(6, -14), ha="left", fontsize=8, color=color)  # fmt: skip
    a.axhline(2, color="#a32828", linestyle="--", linewidth=1)
    a.text(2, 2.08, "Umbral p95: 2 s", fontsize=8, color="#a32828")
    a.set_xlabel("Carga ofrecida (solicitudes/s)")
    a.set_ylabel("Latencia p95 (s)")
    a.legend(loc="upper left", fontsize=8)
    b.plot(
        [0, maximo],
        [0, maximo],
        color="#888888",
        linestyle=":",
        linewidth=1,
        label="Ideal (lograda = ofrecida)",
    )
    b.set_xlabel("Carga ofrecida (solicitudes/s)")
    b.set_ylabel("Carga atendida (solicitudes/s)")
    b.legend(loc="upper left", fontsize=8)
    fig.savefig(D / "placeholder_prueba_04.png")


def fig05_recursos() -> None:
    filas = list(csv.DictReader((P / "c4_carga" / "recursos_escenario_a.csv").open()))
    t0 = float(filas[0]["t"])
    t = [(float(f["t"]) - t0) / 60 for f in filas]
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 4.6), sharex=True)
    series = [("postgres", "PostgreSQL", "#2a78d6"), ("worker_m2", "Worker M2", "#eb6834"),
              ("gunicorn", "API (gunicorn)", "#1baf7a"), ("worker_etl", "Worker ETL", "#6250d6")]  # fmt: skip
    for clave, nombre, color in series:
        a.plot(t, [float(f[clave]) for f in filas], label=nombre, color=color, linewidth=1.5)
    a.axhline(4, color="#a32828", linestyle="--", linewidth=1)
    a.text(
        t[-1],
        3.9,
        "Límite del grupo de control: 4 GB",
        ha="right",
        va="top",
        fontsize=8,
        color="#a32828",
    )
    a.set_ylabel("Memoria PSS (GB)")
    a.set_ylim(0, 4.3)
    a.legend(loc="center left", ncols=2)
    b.plot(t, [float(f["cpu_nucleos"]) for f in filas], color="#184f95", linewidth=1)
    b.axhline(2, color="#a32828", linestyle="--", linewidth=1)
    b.set_ylabel("CPU (núcleos)")
    b.set_xlabel("Minutos desde el inicio del escenario A")
    fig.savefig(D / "placeholder_prueba_05.png")


def fig06_seguridad() -> None:
    bandit = json.loads((P / "c4_seguridad" / "bandit_final.json").read_text())["metrics"][
        "_totals"
    ]
    prod = json.loads((P / "c4_seguridad" / "pip_audit_produccion.json").read_text())
    vuln = sum(len(d.get("vulns", [])) for d in prod["dependencies"])
    filas = [
        ["Bandit (código Python)", "Ejecutado", f"{bandit['SEVERITY.HIGH']} altos, "
         f"{bandit['SEVERITY.MEDIUM']} medios, {bandit['SEVERITY.LOW']} bajos"],
        ["pip-audit (producción)", "Ejecutado",
         f"{len(prod['dependencies'])} paquetes, {vuln} vulnerabilidades"],
        ["Pruebas de sistema (OWASP)", "Ejecutado", "Ver CP-03, CP-04, CP-11, CP-16 y CP-17"],
        ["OWASP ZAP (base y activo)", "Ejecutado", _resumen_zap()],
        ["Trivy (4 imágenes)", "Ejecutado", _resumen_trivy()],
    ]  # fmt: skip
    fig, ax = plt.subplots(figsize=(8, 2.2))
    ax.axis("off")
    tabla = ax.table(cellText=filas, colLabels=["Control", "Estado", "Resultado"], loc="center",
                     cellLoc="left", colWidths=[0.40, 0.13, 0.47])  # fmt: skip
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(8.5)
    tabla.scale(1, 1.5)
    for (fila, col), celda in tabla.get_celld().items():
        celda.set_edgecolor("#e4e3df")
        if fila == 0:
            celda.set_text_props(fontweight="bold")
        elif col == 1 and filas[fila - 1][1] == "Pendiente":
            celda.set_text_props(color="#a32828", fontweight="bold")
    fig.savefig(D / "placeholder_prueba_06.png")


def _resumen_zap() -> str:
    """Tipos de alerta distintos por riesgo en los cuatro escaneos finales de ZAP."""
    tipos: dict[str, set[str]] = {"3": set(), "2": set(), "1": set()}
    for archivo in (P / "c4_seguridad" / "zap_final").glob("*.json"):
        for sitio in json.loads(archivo.read_text())["site"]:
            for alerta in sitio["alerts"]:
                tipos.get(alerta["riskcode"], set()).add(alerta["name"])
    return f"{len(tipos['3'])} altas, {len(tipos['2'])} media (falso positivo), {len(tipos['1'])} bajas"


def _resumen_trivy() -> str:
    """CVE críticas y altas distintas en las imágenes finales y cuántas tienen corrección."""
    criticas: set[str] = set()
    altas: set[str] = set()
    corregibles: set[str] = set()
    for archivo in (P / "c4_seguridad").glob("trivy_final_*.json"):
        for resultado in json.loads(archivo.read_text()).get("Results", []):
            for v in resultado.get("Vulnerabilities") or []:
                grupo = {"CRITICAL": criticas, "HIGH": altas}.get(v["Severity"])
                if grupo is not None:
                    grupo.add(v["VulnerabilityID"])
                    if v.get("FixedVersion"):
                        corregibles.add(v["VulnerabilityID"])
    return f"{len(criticas)} críticas; {len(altas)} CVE altas, {len(corregibles)} corregibles"


def fig07_cobertura() -> None:
    raiz = ET.parse(REG / "coverage.xml").getroot()
    paquetes = [
        (q.get("name").replace(".pfc_", " · pfc_"), float(q.get("line-rate")) * 100, q)
        for q in raiz.iter("package")
        if q.find("classes").findall("class")
        and any(c.find("lines").findall("line") for c in q.iter("class"))
    ]
    paquetes.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8, 4.4))
    nombres = [n for n, _, _ in paquetes]
    valores = [v for _, v, _ in paquetes]
    ax.barh(nombres, valores, color="#2a78d6", height=0.68)
    for i, v in enumerate(valores):
        ax.text(v + 1, i, f"{v:.1f} %", va="center", fontsize=8)
    ax.axvline(80, color="#a32828", linestyle="--", linewidth=1)
    ax.text(80.5, -0.2, "Umbral: 80 %", color="#a32828", fontsize=8, va="center")
    total = float(raiz.get("line-rate")) * 100
    ax.set_xlabel(f"Cobertura de líneas (%); total del proyecto: {total:.1f} %")
    ax.set_xlim(0, 112)
    ax.grid(axis="y", visible=False)
    fig.savefig(D / "placeholder_prueba_07.png")


def fig08_def01() -> None:
    a = json.loads((P / "c2_integracion" / "cp02_primera_pasada.json").read_text())
    b = json.loads((P / "c2_integracion" / "cp02_regresion.json").read_text())
    fig, ejes = plt.subplots(1, 2, figsize=(8.6, 3))
    for eje, datos, titulo in ((ejes[0], a, "Antes: rechazo por la lista blanca"),
                               (ejes[1], b, "Después: descarga registrada en D2")):  # fmt: skip
        eje.axis("off")
        eje.set_title(titulo, fontsize=9)
        eje.text(0, 0.95, json.dumps({k: v[:16] + "…" if k == "sha256" else v for k, v in datos.items()}, indent=1, ensure_ascii=False).replace('", "', '",\n"'),
                 family="DejaVu Sans Mono", fontsize=6.7, va="top", wrap=True)  # fmt: skip
    fig.savefig(D / "placeholder_prueba_08.png")


def fig09_def_visor() -> None:
    fig, ejes = plt.subplots(1, 2, figsize=(9.4, 3.2))
    for eje, ruta, titulo in (
        (
            ejes[0],
            P / "linea_base" / "visor_v010.png",
            "v0.1.0: mapa vacío, /api/escenarios responde 404",
        ),
        (ejes[1], D / "despues_visor.png", "Versión corregida: celdas por nivel (marzo de 2023)"),
    ):
        eje.imshow(imread(ruta))
        eje.set_title(titulo, fontsize=8.5)
        eje.axis("off")
    fig.savefig(D / "placeholder_prueba_09.png")


def fig10_pipeline() -> None:
    pasos = json.loads((REG / "pipeline_local.json").read_text())
    sonar = json.loads((REG / "sonar_resultado.json").read_text())["estado_final"]["status"]
    docker = (P / "c4_seguridad" / "docker_verificacion.log").read_text()
    externos = {
        "analisis-sonarqube": ("puerta PFC", "aprobado" if sonar == "OK" else "falla"),
        "desplegar-staging": (
            "pila Docker (proyecto aislado)",
            "aprobado" if "errores en registros: 0" in docker else "falla",
        ),
    }
    for paso in pasos:
        if paso["trabajo"] in externos:
            paso["paso"] = f"{paso['trabajo']}: {externos[paso['trabajo']][0]}"
            paso["estado"] = externos[paso["trabajo"]][1]
    colores = {"aprobado": "#1baf7a", "falla": "#e34948", "no ejecutado": "#c3c2b7"}
    fig, ax = plt.subplots(figsize=(8, 3.1))
    ax.grid(False)
    for i, p in enumerate(reversed(pasos)):
        ax.barh(i, 1, color=colores[p["estado"]], height=0.8, edgecolor="#fcfcfb")
        ax.text(0.02, i, p["paso"], va="center", fontsize=8.5)
        ax.text(0.98, i, f"{p['estado']}" + (f" · {p['segundos']} s" if p["segundos"] else ""),
                va="center", ha="right", fontsize=8.5, fontweight="bold")  # fmt: skip
    ax.set_xlim(0, 1)
    ax.axis("off")
    fig.savefig(D / "placeholder_prueba_10.png")


def capturas_visor(p) -> None:  # noqa: ANN001
    clave = (RAIZ / "data" / "pruebas" / ".clave_esp").read_text().strip()
    b = p.chromium.launch()
    c = b.new_context(
        ignore_https_errors=True, viewport={"width": 1440, "height": 900}, device_scale_factor=2
    )
    g = c.new_page()
    g.goto(f"{URL}/visor/?periodo=2023-03")
    g.fill("input[name=correo]", "esp@pruebas.pfc")
    g.fill("input[name=clave]", clave)
    g.click("button.primario")
    g.wait_for_selector('body[data-listo="1"]', timeout=45000)
    g.evaluate("localStorage.removeItem('pfc-paleta')")
    g.reload()
    g.wait_for_selector('body[data-listo="1"]', timeout=45000)
    g.wait_for_load_state("networkidle")
    g.wait_for_timeout(2500)
    g.screenshot(path=str(D / "despues_visor.png"))
    g.evaluate("window.mapaVisor.setView([-5.1, -80.0], 8, {animate: false})")
    g.wait_for_load_state("networkidle")
    g.wait_for_timeout(2500)
    g.screenshot(path=str(D / "placeholder_prueba_11.png"))
    g.select_option("#sel-paleta", "accesible")
    g.wait_for_load_state("networkidle")
    g.wait_for_timeout(2500)
    punto = g.evaluate(
        "() => { const p = window.mapaVisor.latLngToContainerPoint([-5.1, -79.7]);"
        " const r = document.getElementById('mapa').getBoundingClientRect();"
        " return [p.x + r.left, p.y + r.top]; }"
    )
    g.mouse.click(*punto)
    g.wait_for_selector("#ventana-consulta", timeout=15000)
    g.wait_for_timeout(600)
    g.screenshot(path=str(D / "placeholder_prueba_12.png"))
    g.evaluate("localStorage.removeItem('pfc-paleta')")
    b.close()


def captura_sonar(p) -> None:  # noqa: ANN001
    """Tablero del proyecto en el SonarQube de pruebas (PFC_SONAR_URL y PFC_SONAR_CLAVE)."""
    url, clave = os.environ.get("PFC_SONAR_URL"), os.environ.get("PFC_SONAR_CLAVE")
    if not (url and clave):
        print("sin PFC_SONAR_URL/PFC_SONAR_CLAVE: se omite la captura de SonarQube")
        return
    b = p.chromium.launch()
    g = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    g.goto(f"{url}/sessions/new")
    g.fill("#login-input", "admin")
    g.fill("#password-input", clave)
    g.keyboard.press("Enter")
    g.wait_for_url("**/projects**", timeout=30000)
    g.goto(f"{url}/dashboard?id=pfc-susceptibilidad&codeScope=overall")
    g.wait_for_load_state("networkidle")
    g.wait_for_timeout(2500)
    aviso = g.get_by_role("button", name="Dismiss").first  # aviso promocional
    if aviso.is_visible():
        aviso.click()
    g.add_style_tag(content="[role=alert], .sw-banner {display: none !important}")
    g.wait_for_timeout(800)
    g.screenshot(path=str(D / "placeholder_prueba_13.png"))
    b.close()


def captura_edge(p) -> None:  # noqa: ANN001
    """CP-24: el visor en Microsoft Edge, con la misma vista que la Figura de la paleta estándar."""
    clave = (RAIZ / "data" / "pruebas" / ".clave_esp").read_text().strip()
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(
        ignore_https_errors=True, viewport={"width": 1440, "height": 900}, device_scale_factor=2
    )
    g = c.new_page()
    g.goto(f"{URL}/visor/?periodo=2023-03")
    g.fill("input[name=correo]", "esp@pruebas.pfc")
    g.fill("input[name=clave]", clave)
    g.click("button.primario")
    g.wait_for_selector('body[data-listo="1"]', timeout=45000)
    g.evaluate("window.mapaVisor.setView([-5.1, -80.0], 8, {animate: false})")
    g.wait_for_load_state("networkidle")
    g.wait_for_timeout(2500)
    version = b.version
    g.evaluate(
        "v => { const d = document.createElement('div'); d.textContent = 'Microsoft Edge ' + v;"
        " d.style.cssText = 'position:fixed;right:12px;bottom:12px;z-index:9999;"
        "background:#fff;padding:4px 8px;border:1px solid #888;font:13px sans-serif';"
        " document.body.append(d); }",
        version,
    )
    g.screenshot(path=str(D / "placeholder_prueba_14.png"))
    b.close()


def main() -> None:
    D.mkdir(parents=True, exist_ok=True)
    fig01_piramide()
    fig02_cronograma()
    fig04_locust()
    fig05_recursos()
    fig06_seguridad()
    fig07_cobertura()
    fig08_def01()
    fig10_pipeline()
    with sync_playwright() as p:
        capturas_visor(p)
        capturas_cobertura(p)
        captura_edge(p)
        captura_sonar(p)
    fig09_def_visor()
    print(sys.argv[0], "ok")


if __name__ == "__main__":
    main()

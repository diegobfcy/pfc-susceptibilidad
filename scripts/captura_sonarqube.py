"""Figura de la sección 2.9.4: captura del tablero de SonarQube (código completo del proyecto).

Uso: SONAR_CLAVE=... python scripts/captura_sonarqube.py [http://localhost:9000]
Requiere playwright con Chromium (entorno de capturas)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
PROYECTO = "pfc-susceptibilidad"


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9000"
    destino = RAIZ / "resultados" / "figuras" / "fig46_sonarqube.png"
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(
            viewport={"width": 1440, "height": 1000}, device_scale_factor=2
        )
        respuesta = pagina.request.post(
            f"{url}/api/authentication/login",
            form={
                "login": os.environ.get("SONAR_USUARIO", "admin"),
                "password": os.environ["SONAR_CLAVE"],
            },
        )
        if not respuesta.ok:
            raise SystemExit(f"inicio de sesión rechazado: {respuesta.status}")
        pagina.goto(f"{url}/dashboard?id={PROYECTO}&codeScope=overall")
        pagina.wait_for_load_state("networkidle")
        pagina.wait_for_timeout(2500)
        cerrar = pagina.get_by_role("button", name="Dismiss")
        if cerrar.count():
            cerrar.first.click()
        # Recorte: puerta de calidad y métricas del código completo
        pagina.screenshot(path=str(destino), clip={"x": 0, "y": 40, "width": 1440, "height": 800})
        navegador.close()
    print(destino)


if __name__ == "__main__":
    main()

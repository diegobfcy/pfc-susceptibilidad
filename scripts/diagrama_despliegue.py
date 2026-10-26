"""Figura de la sección 2.9.1: carpetas de capa -> imágenes Docker -> nodos de despliegue."""

from __future__ import annotations

import sys
from pathlib import Path

import graphviz

FUENTE = "DejaVu Sans"
NODO = dict(
    shape="box",
    style="rounded,filled",
    fillcolor="#f0efec",
    color="#52514e",
    fontname=FUENTE,
    fontsize="10",
)
CAPA = {
    "presentacion": "#cde2fb",
    "servicios": "#d6f0e4",
    "etl": "#fde9c8",
    "predictiva": "#fbd9cc",
    "datos": "#e4def8",
}


def main(salida: Path) -> None:
    g = graphviz.Digraph(
        "despliegue",
        graph_attr=dict(rankdir="LR", fontname=FUENTE, nodesep="0.3", ranksep="0.9", dpi="200"),
        node_attr=NODO,
        edge_attr=dict(color="#52514e", fontname=FUENTE, fontsize="8"),
    )
    with g.subgraph(name="cluster_repo") as c:
        c.attr(
            label="Repositorio pfc-susceptibilidad (git)",
            style="dashed",
            color="#9a9893",
            fontname=FUENTE,
        )
        for n, t in [
            ("presentacion", "presentacion/\nP1 visor · P2 panel"),
            ("servicios", "servicios/pfc_servicios\nS1 API · S2 seguridad · S3 teselas"),
            (
                "etl",
                "etl/pfc_etl\nE1 orquestador · E2 conectores\nE3 verificación · E4 transformación",
            ),
            (
                "predictiva",
                "predictiva/pfc_predictiva\nM1 entrenamiento · M2 inferencia\nM3 evaluación",
            ),
            ("datos", "datos/\nsql/01_esquema.sql · pfc_datos\nrespaldo/"),
        ]:
            c.node(n, t, fillcolor=CAPA[n])
        c.node(
            "desp",
            "despliegue/ · docker-compose.yml\n.github/workflows/ci-cd.yml",
            fillcolor="#ffffff",
        )
    with g.subgraph(name="cluster_img") as c:
        c.attr(
            label="Imágenes y contenedores (etiqueta = commit)",
            style="rounded",
            color="#2a78d6",
            fontname=FUENTE,
        )
        c.node("proxy", "proxy\nnginx 1.27 · TLS\nestáticos + proxy /api")
        c.node("app", "app\nDockerfile.app\nFlask + gunicorn")
        c.node("worker", "worker\nDockerfile.worker\nETL + XGBoost")
        c.node(
            "db",
            "db\npostgis/postgis:15-3.4\n01_esquema.sql",
            shape="cylinder",
            fillcolor="#e4def8",
        )
    with g.subgraph(name="cluster_nodos") as c:
        c.attr(label="Nodos", style="rounded", color="#52514e", fontname=FUENTE)
        c.node(
            "staging",
            "Entorno de pruebas (staging)\nDocker Compose · proyecto pfc-staging\nhttps://localhost:8443",
        )
        c.node(
            "estacion", "Estación de entrenamiento\nRTX 5090 · 32 GB RAM\nSonarQube · act (CI/CD)"
        )
        c.node(
            "registro", "Registro local de imágenes\nregistry:2 (localhost:5000)", shape="folder"
        )
    g.edge("presentacion", "proxy", label="copiado (volumen)")
    g.edge("servicios", "app")
    g.edge("datos", "app", label="pfc_datos")
    g.edge("etl", "worker")
    g.edge("predictiva", "worker")
    g.edge("datos", "worker", label="pfc_datos")
    g.edge("datos", "db", label="inicializa")
    g.edge("desp", "registro", label="construir_y_publicar.sh", style="dashed")
    for n in ("proxy", "app", "worker", "db"):
        g.edge(n, "staging")
    g.edge("worker", "estacion", label="misma imagen\npara entrenar", style="dashed")
    g.edge("registro", "staging", label="desplegar.sh", style="dashed")
    salida.parent.mkdir(parents=True, exist_ok=True)
    g.render(str(salida.with_suffix("")), format="png", cleanup=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))

"""Mide la documentación del código: funciones, clases y métodos públicos con docstring.

Recorre los cuatro paquetes con ast (sin importarlos) y escribe el resultado en
resultados/pruebas/docstrings.json. Público: nombre sin guion bajo inicial, dentro de un
ámbito también público. Termina con código 1 si falta algún docstring, para usarlo en CI."""

from __future__ import annotations

import ast
import json
import sys
from collections.abc import Iterator
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAQUETES = {
    "Ingesta y ETL": "etl/pfc_etl",
    "Predictiva": "predictiva/pfc_predictiva",
    "Servicios": "servicios/pfc_servicios",
    "Datos espaciales": "datos/pfc_datos",
}
Definicion = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def publicas(nodo: ast.AST, prefijo: str = "") -> Iterator[tuple[str, Definicion]]:
    """Definiciones públicas de un nodo y de las clases públicas que contiene."""
    for hijo in ast.iter_child_nodes(nodo):
        if isinstance(hijo, Definicion) and not hijo.name.startswith("_"):
            yield prefijo + hijo.name, hijo
            if isinstance(hijo, ast.ClassDef):
                yield from publicas(hijo, f"{prefijo}{hijo.name}.")


def medir(carpeta: Path) -> dict[str, object]:
    """Módulos, definiciones públicas, cuántas tienen docstring y cuáles faltan."""
    modulos = sorted(carpeta.rglob("*.py"))
    total, faltan, modulos_sin = 0, [], []
    for ruta in modulos:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        if not ast.get_docstring(arbol) and ruta.name != "__init__.py":
            modulos_sin.append(str(ruta.relative_to(RAIZ)))
        for nombre, nodo in publicas(arbol):
            total += 1
            if not ast.get_docstring(nodo):
                faltan.append(f"{ruta.relative_to(RAIZ)}:{nodo.lineno} {nombre}")
    return {
        "modulos": len(modulos),
        "modulos_sin_docstring": modulos_sin,
        "definiciones_publicas": total,
        "con_docstring": total - len(faltan),
        "faltan": faltan,
    }


def main() -> None:
    """Imprime la medición por capa, la guarda en JSON y falla si falta algún docstring."""
    resultado = {capa: medir(RAIZ / ruta) for capa, ruta in PAQUETES.items()}
    total = sum(r["definiciones_publicas"] for r in resultado.values())
    con = sum(r["con_docstring"] for r in resultado.values())
    resultado["total"] = {"definiciones_publicas": total, "con_docstring": con}
    destino = RAIZ / "resultados" / "pruebas" / "docstrings.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    for capa, r in resultado.items():
        print(f"{capa}: {r['con_docstring']}/{r['definiciones_publicas']}")
    faltan = [f for r in resultado.values() for f in r.get("faltan", [])]
    sin_modulo = [m for r in resultado.values() for m in r.get("modulos_sin_docstring", [])]
    print("\n".join(faltan + sin_modulo))
    sys.exit(1 if faltan or sin_modulo else 0)


if __name__ == "__main__":
    main()

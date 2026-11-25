# pfc-susceptibilidad

[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

Sistema de estimación de la susceptibilidad a deslizamientos asociada a El Niño en el norte del
Perú (macrorregión Tumbes–La Libertad, celdas de 1 km, 2000–2026). Monolito modular en cinco
capas; cada carpeta de primer nivel corresponde a una capa de la arquitectura.

| Capa | Carpeta | Componentes |
|---|---|---|
| Presentación | `presentacion/` | P1 visor, P2 panel |
| Servicios | `servicios/pfc_servicios` | S1 API, S2 seguridad, S3 teselas |
| Ingesta y ETL | `etl/pfc_etl` | E1 orquestador, E2 conectores, E3 verificación, E4 transformación |
| Predictiva | `predictiva/pfc_predictiva` | M1 entrenamiento, M2 inferencia, M3 evaluación |
| Datos espaciales | `datos/` | D1 PostGIS, D2 archivos, D3 bitácora |

```bash
conda activate pfc && pip install -e ".[dev,geo]"
pytest && ruff check . && black --check . && lint-imports
```

## Documentación

| Documento | Markdown | PDF |
| --- | --- | --- |
| Manual de usuario: tareas por rol con capturas | [Leer](docs/manual_usuario.md) | [PDF](docs/manual_usuario.pdf) |
| Manual técnico de instalación: despliegue, verificación y recuperación | [Leer](docs/manual_tecnico.md) | [PDF](docs/manual_tecnico.pdf) |
| Manual de mantenimiento: arquitectura, datos, API y extensiones | [Leer](docs/manual_mantenimiento.md) | [PDF](docs/manual_mantenimiento.pdf) |
| Plan de mantenimiento y soporte: atención, prevención y transferencia | [Leer](docs/plan_soporte.md) | [PDF](docs/plan_soporte.pdf) |

Los PDF se regeneran con `python scripts/manuales_pdf.py` (Pandoc y Playwright con Chromium) y las
capturas con `python scripts/capturas_manual.py`. El [contrato OpenAPI](api/openapi.yaml) documenta
la API.

## Resultados del modelo (versión 1)

Partición de prueba sellada 2020–2026: AUC-ROC de 0.902 (IC 95 %: 0.891 a 0.913) y precisión en
muestras caso-control 1:1 de 0.834 (IC 95 %: 0.816 a 0.852). El puntaje ordena las celdas por
susceptibilidad pero no está calibrado como probabilidad. El sistema es una prueba de concepto
académica y **no es un sistema de alerta**.

## Autoría y licencia

Proyecto de fin de carrera de la Escuela Profesional de Ingeniería de Sistemas de la Universidad
Católica de Santa María (Arequipa, 2026), de Maxi Salas, Andrea Sofía y Treviño Ticlavilca, Juan
Diego. Código publicado bajo la [licencia MIT](LICENSE). Los datos de las fuentes oficiales (NOAA,
Copernicus, INGEMMET y CENEPRED) no se incluyen y mantienen sus propias condiciones de uso.

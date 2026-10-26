# pfc-susceptibilidad

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

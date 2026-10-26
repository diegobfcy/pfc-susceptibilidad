# Contenedor app: capa de Servicios (Flask + gunicorn)
FROM python:3.11.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY pyproject.toml README.md ./
COPY servicios servicios
COPY datos/pfc_datos datos/pfc_datos
COPY etl/pfc_etl etl/pfc_etl
COPY predictiva/pfc_predictiva predictiva/pfc_predictiva
COPY config config
RUN pip install --no-cache-dir . && useradd --system --uid 10001 pfc
USER pfc
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "pfc_servicios:crear_app()"]

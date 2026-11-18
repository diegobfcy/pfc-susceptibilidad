# Contenedor app: capa de Servicios (Flask + gunicorn)
# Debian 13 con Python 3.11.18, la misma versión de las pruebas; parches del sistema al construir
FROM python:3.11.18-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PFC_CONFIG=/srv/config/config.yaml
WORKDIR /srv
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY servicios servicios
COPY datos/pfc_datos datos/pfc_datos
COPY etl/pfc_etl etl/pfc_etl
COPY predictiva/pfc_predictiva predictiva/pfc_predictiva
COPY config config
# pip se desinstala al final: no se usa en ejecución y trae una copia vulnerable de setuptools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && pip install --no-cache-dir . \
    && pip uninstall -y pip && useradd --system --create-home --uid 10001 pfc \
    && mkdir -p /datos/d2 && chown pfc /datos/d2  # el volumen d2 hereda el propietario
# Endurecimiento (DEF-20): sin los paquetes base con CVE altas que la aplicación no usa
COPY despliegue/endurecer_imagen.sh /tmp/endurecer_imagen.sh
RUN sh /tmp/endurecer_imagen.sh && rm /tmp/endurecer_imagen.sh
USER pfc
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "pfc_servicios:crear_app()"]

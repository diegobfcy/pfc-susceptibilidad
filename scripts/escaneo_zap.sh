#!/usr/bin/env bash
# Escaneo OWASP ZAP del entorno de pruebas (A03, A05 y A07 de la Tabla de OWASP del capítulo 3):
# base pasivo del visor y del panel, y escaneo activo de la API a partir del contrato OpenAPI,
# sin sesión y con la sesión del rol ASESOR (solo lectura: el ataque no inicia procesamientos).
# Uso: escaneo_zap.sh <carpeta de salida>. Requiere el entorno iniciado (entorno.sh iniciar).
set -uo pipefail
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SALIDA="$(mkdir -p "$1" && cd "$1" && pwd)"
URL="https://127.0.0.1:8444"
IMAGEN="zaproxy/zap-stable"
PY="$HOME/anaconda3/envs/pfc-pruebas/bin/python"

sed "s#^  - url: /api#  - url: $URL/api#" "$RAIZ/api/openapi.yaml" > "$SALIDA/openapi_entorno.yaml"
zap() { docker run --rm --network host -v "$SALIDA:/zap/wrk:rw" "$IMAGEN" "$@"; }

# Código de salida de los scripts de ZAP: 0 sin alertas, 1 con FAIL, 2 con WARN, 3 error.
zap zap-baseline.py -t "$URL/visor/" -j -a -J base_visor.json -r base_visor.html -I
echo "base_visor: $?" >> "$SALIDA/codigos.txt"
zap zap-baseline.py -t "$URL/panel/" -j -a -J base_panel.json -r base_panel.html -I
echo "base_panel: $?" >> "$SALIDA/codigos.txt"
zap zap-api-scan.py -t openapi_entorno.yaml -f openapi -a -J api_sin_sesion.json \
  -r api_sin_sesion.html -I
echo "api_sin_sesion: $?" >> "$SALIDA/codigos.txt"

COOKIE="$(cd "$RAIZ/scripts" && "$PY" -c '
from cliente_pruebas import Cliente
c = Cliente(); assert c.entrar("ASESOR").status_code == 204
print(";".join(f"{k}={v}" for k, v in c.s.cookies.items()))')"
REGLA="replacer.full_list(0)"
zap zap-api-scan.py -t openapi_entorno.yaml -f openapi -a -J api_asesor.json -r api_asesor.html -I \
  -z "-config $REGLA.description=sesion -config $REGLA.enabled=true \
      -config $REGLA.matchtype=REQ_HEADER -config $REGLA.matchstr=Cookie \
      -config $REGLA.regex=false -config $REGLA.replacement=$COOKIE"
echo "api_asesor: $?" >> "$SALIDA/codigos.txt"

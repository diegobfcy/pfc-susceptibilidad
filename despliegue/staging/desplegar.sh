#!/usr/bin/env bash
# Despliegue al entorno de pruebas: descarga la versión, aplica el esquema, levanta los
# contenedores y ejecuta la prueba de humo; si falla, vuelve a la versión anterior.
set -euo pipefail
VERSION="${1:?uso: desplegar.sh <commit>}"
cd "$(dirname "$0")/../.."
ANTERIOR_ARCHIVO=despliegue/staging/.version_actual
ANTERIOR=$(cat "$ANTERIOR_ARCHIVO" 2>/dev/null || echo "")

levantar() {
  PFC_VERSION="$1" docker compose pull app worker
  PFC_VERSION="$1" docker compose up -d --wait db
  docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d pfc < datos/sql/01_esquema.sql
  PFC_VERSION="$1" docker compose up -d app worker proxy
}

prueba_humo() {
  for _ in $(seq 1 20); do
    if curl -fsk https://localhost:8443/api/salud | grep -q '"estado":"ok"' \
       && docker compose exec -T db psql -U postgres -d pfc -tAc \
          "SELECT count(*) FROM sistema.procesamiento" >/dev/null \
       && [ -n "$(docker compose ps --status running --quiet worker)" ]; then
      return 0
    fi
    sleep 3
  done
  return 1
}

levantar "$VERSION"
if prueba_humo; then
  echo "$VERSION" > "$ANTERIOR_ARCHIVO"
  echo "despliegue $VERSION: prueba de humo superada"
else
  echo "despliegue $VERSION: prueba de humo fallida" >&2
  if [ -n "$ANTERIOR" ]; then
    levantar "$ANTERIOR"
    echo "revertido a $ANTERIOR" >&2
  fi
  exit 1
fi

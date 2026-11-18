#!/usr/bin/env bash
# Construye las imágenes app, worker, db y proxy, las etiqueta con el commit y las publica en el registro.
set -euo pipefail
VERSION="${1:?uso: construir_y_publicar.sh <commit>}"
REGISTRO="${PFC_REGISTRO:-localhost:5000}"
cd "$(dirname "$0")/.."
for imagen in app worker db proxy; do
  docker build -f "despliegue/Dockerfile.$imagen" -t "$REGISTRO/pfc-$imagen:$VERSION" .
  docker push "$REGISTRO/pfc-$imagen:$VERSION"
done

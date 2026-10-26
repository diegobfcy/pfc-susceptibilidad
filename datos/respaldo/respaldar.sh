#!/usr/bin/env bash
# Respaldo cifrado de D1 (pg_dump en formato custom + GPG simétrico) con retención de 7 copias.
set -euo pipefail
DESTINO="${PFC_RESPALDOS:-/var/backups/pfc}"
mkdir -p "$DESTINO"
ARCHIVO="$DESTINO/pfc_$(date +%Y%m%d_%H%M%S).dump.gpg"
pg_dump --format=custom "$PFC_BD_URL_PG" \
  | gpg --batch --yes --symmetric --cipher-algo AES256 --passphrase-file "$PFC_CLAVE_RESPALDO" -o "$ARCHIVO"
sha256sum "$ARCHIVO" > "$ARCHIVO.sha256"
ls -1t "$DESTINO"/pfc_*.dump.gpg | tail -n +8 | xargs -r rm -f
echo "respaldo: $ARCHIVO"

#!/usr/bin/env bash
# Restauración del último respaldo cifrado tras verificar su huella SHA-256.
set -euo pipefail
DESTINO="${PFC_RESPALDOS:-/var/backups/pfc}"
ULTIMO=$(ls -1t "$DESTINO"/pfc_*.dump.gpg | head -1)
sha256sum -c "$ULTIMO.sha256"
gpg --batch --decrypt --passphrase-file "$PFC_CLAVE_RESPALDO" "$ULTIMO" \
  | pg_restore --clean --if-exists --no-owner -d "$PFC_BD_URL_PG"
echo "restaurado: $ULTIMO"

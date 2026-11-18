#!/usr/bin/env bash
# Entorno de pruebas nativo con los límites del VPS (2 vCPU, 4 GB y sin intercambio): PostGIS,
# gunicorn, workers y nginx con TLS. Uso: entorno.sh iniciar|detener|estado|esquema
set -euo pipefail
RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
BASE="$RAIZ/data/pruebas"
PG="$HOME/anaconda3/envs/pfc-postgis/bin"
PY="$HOME/anaconda3/envs/pfc/bin/python"
GUNICORN="$HOME/anaconda3/envs/pfc/bin/gunicorn"
NGINX="$HOME/anaconda3/envs/pfc-pruebas/bin/nginx"
PUERTO_PG=55433
UNIDAD=pfc-pruebas
mkdir -p "$BASE/nginx/temp" "$BASE/logs"

clave() {
  [ -f "$BASE/.claves" ] || { umask 077; printf 'PG_CLAVE=%s\nPFC_SECRETO_SESION=%s\n' \
    "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" > "$BASE/.claves"; }
  # shellcheck disable=SC1091
  . "$BASE/.claves"
  export PFC_BD_URL="postgresql+psycopg://postgres:${PG_CLAVE}@127.0.0.1:${PUERTO_PG}/pfc"
  export PFC_SECRETO_SESION PFC_D2="$BASE/d2" PFC_DISPOSITIVO_XGB=cpu
  export PYTHONPATH="$RAIZ/servicios:$RAIZ/etl:$RAIZ/predictiva:$RAIZ/datos"
  export OMP_NUM_THREADS=2
  PFC_DATOS_ORIGEN="$(grep '^PFC_DATOS_ORIGEN=' "$RAIZ/.env" | cut -d= -f2)"
  export PFC_DATOS_ORIGEN PROJ_DATA="$HOME/anaconda3/envs/tesis/share/proj"
}

iniciar_bd() {
  if [ ! -d "$BASE/pgdata" ]; then
    printf '%s' "$PG_CLAVE" > "$BASE/.pgpw"
    "$PG/initdb" -D "$BASE/pgdata" -U postgres --pwfile="$BASE/.pgpw" -A scram-sha-256 -E UTF8 \
      --locale=C >/dev/null
    rm -f "$BASE/.pgpw"
    cat >> "$BASE/pgdata/postgresql.conf" <<CONF
listen_addresses = '127.0.0.1'
port = $PUERTO_PG
unix_socket_directories = '$BASE'
shared_buffers = 768MB
effective_cache_size = 2GB
work_mem = 32MB
maintenance_work_mem = 256MB
max_wal_size = 4GB
checkpoint_timeout = 15min
CONF
  fi
  "$PG/pg_ctl" -D "$BASE/pgdata" -l "$BASE/logs/postgres.log" -w start >/dev/null
}

case "${1:-}" in
  iniciar)
    clave
    # Todos los procesos comparten un único grupo de control con los límites del VPS.
    systemd-run --user --quiet --collect --unit="$UNIDAD" --property=MemoryMax=4G \
      --property=MemorySwapMax=0 --property=CPUQuota=200% --property=Type=forking \
      --property=KillMode=mixed --setenv=HOME="$HOME" --working-directory="$RAIZ" \
      bash "$0" _procesos
    ;;
  _procesos)
    clave
    iniciar_bd
    export PFC_D2
    "$PY" -m pfc_etl.orquestador --cola >>"$BASE/logs/worker_etl.log" 2>&1 &
    "$PY" -m pfc_predictiva.inferencia.trabajador >>"$BASE/logs/worker_m2.log" 2>&1 &
    "$GUNICORN" --daemon --pid "$BASE/gunicorn.pid" --bind 127.0.0.1:8000 --workers 2 --threads 4 \
      --timeout 120 --chdir "$RAIZ" --access-logfile "$BASE/logs/gunicorn_acceso.log" \
      --error-logfile "$BASE/logs/gunicorn.log" 'pfc_servicios:crear_app()'
    sed -e "s#@RAIZ@#$RAIZ#g" -e "s#@BASE@#$BASE#g" "$RAIZ/despliegue/pruebas/nginx.conf" \
      > "$BASE/nginx/nginx.conf"
    "$NGINX" -c "$BASE/nginx/nginx.conf" -e "$BASE/logs/nginx_error.log"
    disown -a
    ;;
  detener)
    systemctl --user stop "$UNIDAD.service" 2>/dev/null || true
    ;;
  esquema)
    clave
    export PGPASSWORD="$PG_CLAVE"
    "$PG/psql" -h 127.0.0.1 -p $PUERTO_PG -U postgres -d postgres -tc \
      "SELECT 1 FROM pg_database WHERE datname='pfc'" | grep -q 1 \
      || "$PG/createdb" -h 127.0.0.1 -p $PUERTO_PG -U postgres pfc
    for f in 01_esquema 02_operacion; do
      "$PG/psql" -h 127.0.0.1 -p $PUERTO_PG -U postgres -d pfc -q -v ON_ERROR_STOP=1 \
        -f "$RAIZ/datos/sql/$f.sql"
    done
    ;;
  entorno)
    clave
    printf 'export PFC_BD_URL=%q PFC_D2=%q PYTHONPATH=%q\n' "$PFC_BD_URL" "$PFC_D2" "$PYTHONPATH"
    ;;
  *) echo "uso: $0 iniciar|detener|esquema|entorno"; exit 2 ;;
esac

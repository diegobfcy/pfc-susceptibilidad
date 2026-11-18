#!/usr/bin/env bash
# Escenario D escalonado. Uso: correr_escalonada.sh solo|inferencia
#   solo:       el visor sin otra carga (capacidad propia del visor).
#   inferencia: el escenario A se repite sin pausa mientras dura la carga escalonada.
set -u
cd "$(dirname "$0")/.."
MODO="$1"
PY="$HOME/anaconda3/envs/pfc/bin/python"
L="$HOME/anaconda3/envs/pfc-pruebas/bin/locust"
R=resultados/pruebas/c4_carga_escalonada
mkdir -p "$R"
export PFC_SALIDA_ESCENARIO="$PWD/$R"
"$PY" scripts/muestrear_recursos.py "$R/recursos_$MODO.csv" &
M=$!
A=""
if [ "$MODO" = inferencia ]; then
  (cd scripts && n=1 && while [ ! -f "../$R/.fin" ]; do
     "$PY" escenario_inferencia.py "A_escalonada_$n" 2000-02-01 2026-06-30 \
       > "../$R/escenario_a_escalonada_$n.log" 2>&1; n=$((n + 1)); done) &
  A=$!
  sleep 20
fi
PFC_SALIDA_ESCALONADA="$R/escalonada_$MODO.json" PFC_CLAVE_ESP="$(cat data/pruebas/.clave_esp)" \
  "$L" -f pruebas/carga/escalonada.py --headless --host https://127.0.0.1:8444 \
  --csv "$R/locust_$MODO" --csv-full-history --html "$R/locust_$MODO.html" --only-summary \
  > "$R/locust_$MODO.log" 2>&1
touch "$R/.fin"
[ -n "$A" ] && wait "$A"
rm -f "$R/.fin"
kill "$M"

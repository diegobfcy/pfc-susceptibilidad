#!/usr/bin/env bash
# Escenario A (serie completa) con el escenario D simultáneo durante 15 minutos.
set -u
cd "$(dirname "$0")/.."
PY="$HOME/anaconda3/envs/pfc/bin/python"
L="$HOME/anaconda3/envs/pfc-pruebas/bin/locust"
R=resultados/pruebas/c4_carga
"$PY" scripts/muestrear_recursos.py "$R/recursos_escenario_a.csv" &
M=$!
(cd scripts && "$PY" escenario_inferencia.py A 2000-02-01 2026-06-30) > "$R/escenario_a.log" 2>&1 &
A=$!
sleep 20
PFC_CLAVE_ESP="$(cat data/pruebas/.clave_esp)" "$L" -f pruebas/carga/locustfile.py --headless \
  -u 15 -r 1 -t 15m --host https://127.0.0.1:8444 --html "$R/locust_escenario_d.html" \
  --csv "$R/locust_d" --only-summary > "$R/locust_escenario_d.log" 2>&1
wait $A
kill $M

#!/usr/bin/env bash
# CP-26: procesamiento completo por la API, con el muestreo de memoria y CPU del grupo de control.
set -u
cd "$(dirname "$0")/.."
PY="$HOME/anaconda3/envs/pfc/bin/python"
R=resultados/pruebas/c4_carga
"$PY" scripts/muestrear_recursos.py "$R/recursos_cp26.csv" &
M=$!
(cd scripts && "$PY" cp26_extremo_a_extremo.py "$PWD/../data/pruebas/d2") > "$R/cp26.log" 2>&1
kill $M

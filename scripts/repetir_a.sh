#!/usr/bin/env bash
# Repite el escenario A durante el escenario D; cada repetición reemplaza los resultados (CP-13).
cd "$(dirname "$0")"
for n in 1 2 3 4; do
  "$HOME/anaconda3/envs/pfc/bin/python" escenario_inferencia.py "A_repeticion_$n" 2000-02-01 2026-06-30 \
    > "../resultados/pruebas/c4_carga/escenario_a_rep$n.log" 2>&1
  sleep 45
done

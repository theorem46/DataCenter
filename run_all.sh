#!/usr/bin/env bash
# Reproduce every number in the paper. Exits non-zero if any check fails.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p "Experiment Logs"
for s in E1_geometric_heat E2_insight_baseline E3_cascade E4_leakage_crossover \
         E5_tower E6_best_uses E7_uncertainty E8_incremental_production E9_dataset_value; do
  echo "== $s"
  python3 -I "Scripts/$s.py" > "Experiment Logs/$s.log" 2>&1 || { tail -5 "Experiment Logs/$s.log"; exit 1; }
  tail -1 "Experiment Logs/$s.log"
done
echo "== dependency chain"
python3 -I dependency_graph.py > "Experiment Logs/dependency_graph.log" 2>&1 || { tail -5 "Experiment Logs/dependency_graph.log"; exit 1; }
tail -1 "Experiment Logs/dependency_graph.log"
echo "== paper figures"
python3 -I make_paper_numbers.py
echo "all checks pass"

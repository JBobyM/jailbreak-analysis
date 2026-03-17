#!/usr/bin/env bash
set -e

PROJ="/work/boby/projects/AI Safety Projects/Jailbreak Analysis"
PYTHON="/work/boby/projects/AI Safety Projects/.venv/bin/python"

cd "$PROJ"
export PYTHONPATH="$PROJ"

echo "===== [1/6] Baseline attack (100 prompts) ====="
"$PYTHON" src/runner.py --mode baseline

echo "===== [2/6] Judge baseline responses ====="
"$PYTHON" src/judge.py --input data/results/baseline.jsonl

echo "===== [3/6] Analyze baseline ====="
"$PYTHON" src/analyze.py

echo "===== [4/6] Defense: sysprompt ====="
"$PYTHON" src/defenses.py --defense sysprompt

echo "===== [5/6] Defense: input_filter ====="
"$PYTHON" src/defenses.py --defense input_filter

echo "===== [6/6] Defense: output_classifier ====="
"$PYTHON" src/defenses.py --defense output_classifier

echo "===== Final analysis with all defenses ====="
"$PYTHON" src/analyze.py

echo "===== DONE ====="

#!/usr/bin/env bash
set -e

PROJ="/work/boby/projects/AI Safety Projects/Jailbreak Analysis"
PYTHON="/work/boby/projects/AI Safety Projects/.venv/bin/python"

cd "$PROJ"
export PYTHONPATH="$PROJ"

# ── Baseline (direct-request, Llama 3) ────────────────────────────────────────
echo "===== [1/6] Baseline attack — Llama 3 8B, direct-request ====="
"$PYTHON" src/runner.py --mode baseline --attack direct

echo "===== [2/6] Judge baseline responses ====="
"$PYTHON" src/judge.py --input data/results/baseline.jsonl

# ── Defenses (direct-request framing) ─────────────────────────────────────────
echo "===== [3/6] Defense: sysprompt (direct) ====="
"$PYTHON" src/defenses.py --defense sysprompt

echo "===== [4/6] Defense: input_filter (direct) ====="
"$PYTHON" src/defenses.py --defense input_filter

echo "===== [5/6] Defense: output_classifier (direct) ====="
"$PYTHON" src/defenses.py --defense output_classifier

# ── Roleplay attack framing ────────────────────────────────────────────────────
echo "===== [6/9] Roleplay attack — Llama 3 8B ====="
"$PYTHON" src/runner.py --mode attack --attack roleplay \
  --output data/results/attack_roleplay.jsonl

echo "===== [7/9] Judge roleplay responses ====="
"$PYTHON" src/judge.py \
  --input  data/results/attack_roleplay.jsonl \
  --output data/results/attack_roleplay_labeled.jsonl

# ── Defenses under roleplay framing ───────────────────────────────────────────
echo "===== [7b/9] Defense: sysprompt (roleplay) ====="
"$PYTHON" src/defenses.py --defense sysprompt --attack roleplay

echo "===== [7c/9] Defense: input_filter (roleplay) ====="
"$PYTHON" src/defenses.py --defense input_filter --attack roleplay

echo "===== [7d/9] Defense: output_classifier (roleplay) ====="
"$PYTHON" src/defenses.py --defense output_classifier --attack roleplay

# ── Mistral 7B baseline ────────────────────────────────────────────────────────
echo "===== [8/9] Baseline attack — Mistral 7B, direct-request ====="
"$PYTHON" src/runner.py --mode baseline --model mistral \
  --output data/results/baseline_mistral.jsonl

echo "===== [8b/9] Judge Mistral responses ====="
"$PYTHON" src/judge.py \
  --input  data/results/baseline_mistral.jsonl \
  --output data/results/baseline_mistral_labeled.jsonl

# ── Final analysis (all figures) ───────────────────────────────────────────────
echo "===== [9/9] Final analysis ====="
"$PYTHON" src/analyze.py

echo "===== DONE ====="

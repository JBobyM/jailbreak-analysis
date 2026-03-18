#!/usr/bin/env bash
set -e

PROJ="/work/boby/projects/AI Safety Projects/Jailbreak Analysis"
PYTHON="/work/boby/projects/AI Safety Projects/.venv/bin/python"

cd "$PROJ"
export PYTHONPATH="$PROJ"

# ── Baseline (direct-request, Llama 3) ────────────────────────────────────────
echo "===== [1/11] Baseline attack — Llama 3 8B, direct-request ====="
"$PYTHON" src/runner.py --mode baseline --attack direct

echo "===== [2/11] Judge baseline responses ====="
"$PYTHON" src/judge.py --input data/results/baseline.jsonl

# ── Defenses (direct-request framing) ─────────────────────────────────────────
echo "===== [3/11] Defense: sysprompt (direct) ====="
"$PYTHON" src/defenses.py --defense sysprompt

echo "===== [4/11] Defense: input_filter (direct) ====="
"$PYTHON" src/defenses.py --defense input_filter

echo "===== [5/11] Defense: output_classifier (direct) ====="
"$PYTHON" src/defenses.py --defense output_classifier

# ── Alternative attack framings ────────────────────────────────────────────────
echo "===== [6/11] Roleplay attack — Llama 3 8B ====="
"$PYTHON" src/runner.py --mode attack --attack roleplay \
  --output data/results/attack_roleplay.jsonl
"$PYTHON" src/judge.py \
  --input  data/results/attack_roleplay.jsonl \
  --output data/results/attack_roleplay_labeled.jsonl

echo "===== [7/11] Persona (DAN) attack — Llama 3 8B ====="
"$PYTHON" src/runner.py --mode attack --attack persona \
  --output data/results/attack_persona.jsonl
"$PYTHON" src/judge.py \
  --input  data/results/attack_persona.jsonl \
  --output data/results/attack_persona_labeled.jsonl

echo "===== [8/11] Encoding (Base64) attack — Llama 3 8B ====="
"$PYTHON" src/runner.py --mode attack --attack encoding \
  --output data/results/attack_encoding.jsonl
"$PYTHON" src/judge.py \
  --input  data/results/attack_encoding.jsonl \
  --output data/results/attack_encoding_labeled.jsonl

# ── PAIR ───────────────────────────────────────────────────────────────────────
echo "===== [9/11] PAIR attack — Llama 3 8B (max 10 iters) ====="
"$PYTHON" src/pair.py --max-iters 10

# ── Mistral 7B baseline ────────────────────────────────────────────────────────
echo "===== [10/11] Baseline attack — Mistral 7B, direct-request ====="
"$PYTHON" src/runner.py --mode baseline --model mistral \
  --output data/results/baseline_mistral.jsonl
"$PYTHON" src/judge.py \
  --input  data/results/baseline_mistral.jsonl \
  --output data/results/baseline_mistral_labeled.jsonl

# ── Final analysis (all figures) ───────────────────────────────────────────────
echo "===== [11/11] Final analysis ====="
"$PYTHON" src/analyze.py

echo "===== DONE ====="

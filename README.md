# Jailbreak Analysis on Open-Source LLMs

Empirical evaluation of jailbreak attack techniques and lightweight defenses against **Llama 3 8B**
running locally via [Ollama](https://ollama.com/).

Uses the [JailbreakBench](https://github.com/JailbreakBench/jailbreakbench) dataset as the
standard benchmark of harmful behaviors.

---

## Project Structure

```
AI Safety Projects/
├── data/
│   ├── raw/              # JailbreakBench behaviors CSV (auto-downloaded)
│   └── results/          # Attack run outputs (JSONL)
├── src/
│   ├── config.py         # Model endpoint, paths, constants
│   ├── dataset.py        # Load + parse JailbreakBench
│   ├── runner.py         # Send prompts to Llama 3, collect responses
│   ├── judge.py          # LLM-as-judge compliance classifier
│   ├── defenses.py       # System-prompt hardening, keyword filter, output classifier
│   └── analyze.py        # Compute stats, generate tables/charts
├── notebooks/
│   └── analysis.ipynb    # Interactive exploration
├── results/
│   └── figures/          # Charts for writeup
├── writeup/
│   └── report.md         # Final report
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running
- Llama 3 8B pulled: `ollama pull llama3`

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the baseline attack

```bash
# Quick smoke test (5 prompts)
python src/runner.py --mode baseline --limit 5

# Full dataset
python src/runner.py --mode baseline
```

### 4. Judge the responses

```bash
python src/judge.py --input data/results/baseline.jsonl
```

### 5. Analyze results

```bash
python src/analyze.py
```

Figures are saved to `results/figures/`.

### 6. Test a defense

```bash
# System-prompt hardening
python src/defenses.py --defense sysprompt --limit 20

# Input keyword filter
python src/defenses.py --defense input_filter --limit 20

# Output classifier
python src/defenses.py --defense output_classifier --limit 20
```

---

## Pipeline Overview

```
JailbreakBench CSV
        │
        ▼
  dataset.py  (load behaviors)
        │
        ▼
  runner.py   (send to Llama 3 via Ollama)
        │
        ▼  baseline.jsonl
  judge.py    (LLM-as-judge YES/NO compliance)
        │
        ▼  baseline_labeled.jsonl
  analyze.py  (ASR stats + figures)
        │
        ▼  results/figures/

  defenses.py (wraps runner + judge with a defense)
        │
        ▼  defense_*_labeled.jsonl
  analyze.py  (delta-ASR comparison)
```

---

## Defenses

| Defense                | Description                                     |
|------------------------|-------------------------------------------------|
| `sysprompt`            | Prepend a hardened safety system prompt         |
| `input_filter`         | Block prompts containing harmful keywords       |
| `output_classifier`    | Post-generation LLM safety classification       |

---

## Configuration

All tuneable parameters live in `src/config.py`:

| Variable              | Default                       | Description               |
|-----------------------|-------------------------------|---------------------------|
| `MODEL_NAME`          | `llama3`                      | Ollama model tag          |
| `JUDGE_MODEL`         | `llama3`                      | Judge model tag           |
| `OLLAMA_BASE_URL`     | `http://localhost:11434`      | Ollama API endpoint       |
| `MAX_TOKENS`          | `512`                         | Max tokens per response   |
| `TEMPERATURE`         | `0.7`                         | Sampling temperature      |
| `REQUEST_TIMEOUT`     | `120`                         | Seconds per request       |

Override via environment variables:
```bash
MODEL_NAME=llama3:70b python src/runner.py --mode baseline --limit 10
```

---

## Results

See [`writeup/report.md`](writeup/report.md) for the full analysis writeup.

---

## Ethical Note

This project is conducted for **defensive security research** only. No real harmful content is
generated for deployment. The model runs locally; no data is sent to external services.
Attack prompts from JailbreakBench are used solely to measure defense effectiveness, consistent
with published responsible disclosure guidelines.

# Jailbreak Analysis

Empirical evaluation of jailbreak attack techniques and defenses against open-source LLMs.
Tested on Llama 3 8B and Mistral 7B, running locally on 2x RTX 3090 via Ollama, using the
[JailbreakBench](https://github.com/JailbreakBench/jailbreakbench) benchmark of 100 harmful behaviors.

<p align="center">
  <img src="results/figures/asr_by_attack_framing.png" width="49%"/>
  <img src="results/figures/pair_convergence.png" width="49%"/>
</p>
<p align="center">
  <img src="results/figures/defense_comparison.png" width="49%"/>
  <img src="results/figures/asr_by_model.png" width="49%"/>
</p>

---

## What this is

A lot of jailbreak research focuses on showing that attacks can work. This project asks a
different question: how much do they actually work against a well-aligned 7-8B model, with
real numbers across multiple techniques and defenses?

We ran five attack methods against Llama 3 8B, from a plain direct request up to PAIR, an
automated red-teaming approach that uses a second LLM to iteratively refine prompts until the
target complies. We also tested three defenses and ran a side-by-side with Mistral 7B to see
if the results are model-specific. Everything is automated and reproducible.

The benchmark is [JailbreakBench](https://github.com/JailbreakBench/jailbreakbench), which
provides 100 harmful behaviors across 10 categories (disinformation, malware/hacking,
physical harm, expert advice, and more). Compliance is classified by an LLM judge using a
two-stage approach: a fast keyword check for obvious refusals, then a strict YES/NO prompt
for anything ambiguous.

---

## Results

### Attack success rate by technique

| Technique         | ASR   | Notes |
|-------------------|-------|-------|
| Direct request    | 2.0%  | Baseline |
| Roleplay wrapper  | 2.0%  | No improvement over direct |
| Persona (DAN)     | 1.0%  | Worse than direct |
| Base64 encoding   | 0.0%  | Model decodes and refuses anyway |
| PAIR              | 5.0%  | Only technique that moves the needle |

Static framings (roleplay, DAN persona, Base64 encoding) either matched or underperformed
a plain direct request. The model recognizes these patterns and pushes back harder, not less.

Base64 at 0% is the most interesting result here. The intuition behind encoding attacks is
that safety filters work on surface text, so encoded input slips through. That is not what
happened. Llama 3 8B decodes correctly and applies the same judgment it would to the
plaintext version.

PAIR is a different story. It uses a second instance of Llama 3 8B as an attacker. The
attacker generates a jailbreak prompt, sends it to the target, and if the target refuses,
it gets the refusal back and tries again, up to 10 iterations. Using the same model class
as both attacker and target is a conservative setup. A stronger attacker model would push
the number higher. Even so, PAIR reached 5% where everything else capped out at 2%.

### PAIR convergence

All 5 successes happened within the first 2 iterations. After that the model held firm
through iteration 10. The compliance boundary is narrow but findable quickly, and once
the model refuses the refined prompt, more iterations do not help.

### Where failures happen

The 2% baseline compliance was not in the high-harm categories. It came from two behaviors
in ambiguous advisory domains:

- *economic_harm*: insider betting tips for football games
- *expert_advice*: a bot that recommends stocks and investment products

Neither of these reads like the content safety training is primarily designed to block. Both
are cases where the model was asked for domain-specific advice it probably gives freely in
legitimate contexts, and it did. The harm is in the intent of the requester, not the text
of the response, and the model has no way to tell the difference.

### Defenses

| Defense              | ASR   | Change vs baseline |
|----------------------|-------|--------------------|
| Baseline             | 2.0%  | -                  |
| System-prompt hardening | 0.0% | -2.0 pp         |
| Input keyword filter | 1.0%  | -1.0 pp            |
| Output classifier    | 0.0%  | -2.0 pp            |

System-prompt hardening and the output classifier both got to 0%. The keyword filter looks
like it reduced ASR by 1 pp, but neither of the two prompts that complied in the baseline
was actually blocked by the filter. The drop is run-to-run variance. The filter caught 6
other prompts, but the advisory-domain behaviors that matter most contain no terms from the
blocked keyword list.

### Model comparison

Llama 3 8B (2.0%) and Mistral 7B (1.0%) behave similarly under direct-request attacks. The
difference is within noise at this sample size (1 vs 2 successful prompts out of 100). Both
models are highly resistant to direct jailbreak attempts on this benchmark.

---

## Key takeaways

**Modern 7-8B instruction-tuned models are robust to static jailbreak framings.** Roleplay,
DAN personas, and encoding attacks do not work better than a plain request, and often work
worse. The models have seen these patterns.

**Automated red-teaming (PAIR) is in a different category.** It found 5% compliance where
static attacks found 2%, using only the same model class as the attacker. With a stronger
attacker, that ceiling goes up. This is worth taking seriously.

**The real failure mode is contextual, not lexical.** The compliance that did occur was in
domains where helpfulness and harm look identical at the text level. Output classifiers
struggle with exactly this. System-prompt hardening is more reliable because it changes what
the model generates, not what gets filtered after the fact.

**Keyword filtering is brittle.** It catches what is on the list. The prompts most likely
to actually work are the ones phrased naturally enough to not contain any flagged terms.

---

## Setup

```bash
git clone https://github.com/JBobyM/jailbreak-analysis.git
cd jailbreak-analysis

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Needs Ollama running locally with both models pulled
ollama pull llama3
ollama pull mistral
```

---

## Running

```bash
export PYTHONPATH="$PWD"
PYTHON=".venv/bin/python"

# Full experiment (all attacks, defenses, both models). Takes ~45 min with GPU.
nohup bash run_experiment.sh > experiment.log 2>&1 &

# Or run individual steps
"$PYTHON" src/runner.py --mode baseline --attack direct
"$PYTHON" src/runner.py --mode attack --attack persona --output data/results/attack_persona.jsonl
"$PYTHON" src/pair.py --max-iters 10
"$PYTHON" src/judge.py --input data/results/baseline.jsonl
"$PYTHON" src/defenses.py --defense sysprompt
"$PYTHON" src/analyze.py
```

Results land in `data/results/` as JSONL files. Figures are regenerated by `src/analyze.py`.

---

## Project structure

```
src/
  config.py       central config (paths, model names, generation params)
  dataset.py      loads JailbreakBench from HuggingFace
  attacks.py      attack framing wrappers (direct, roleplay, persona, encoding)
  pair.py         PAIR automated iterative red-teaming
  runner.py       parallel attack runner (ThreadPoolExecutor, 4 workers)
  judge.py        LLM-as-judge compliance classifier (keyword + LLM two-stage)
  defenses.py     three defense implementations
  analyze.py      analysis and figure generation

data/results/     JSONL output files (gitignored, regenerated by running experiments)
results/figures/  generated charts
```

---

## Dataset

[JailbreakBench](https://github.com/JailbreakBench/jailbreakbench), 100 harmful behaviors
across 10 categories. Loaded from HuggingFace: `JailbreakBench/JBB-Behaviors`, harmful split.

Behaviors come from three sources: `original` (written by the JailbreakBench team), `advbench`,
and `tdc/harmbench`. The original behaviors had the highest compliance rate (3.6%) because they
target naturally ambiguous domains rather than overtly harmful content.

"""Attack runner: send prompts to a local Llama 3 via Ollama and save responses.

Usage (CLI):
    python src/runner.py --mode baseline --limit 10
    python src/runner.py --mode baseline               # full dataset
    python src/runner.py --mode defense --defense sysprompt --limit 10

Modes:
    baseline   — no system prompt
    defense    — apply one of the defenses from defenses.py
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

CONCURRENCY = 4  # match OLLAMA_NUM_PARALLEL

from src.config import (
    MODEL_NAME,
    OLLAMA_BASE_URL,
    MAX_TOKENS,
    TEMPERATURE,
    TOP_P,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_DELAY,
    BASELINE_RAW,
    DEFAULT_BATCH_SIZE,
    DEFAULT_LIMIT,
)
from src.dataset import load_behaviors

logger = logging.getLogger(__name__)


# ── Ollama client ──────────────────────────────────────────────────────────────

def _ollama_generate(
    prompt: str,
    system: Optional[str] = None,
    model: str = MODEL_NAME,
    base_url: str = OLLAMA_BASE_URL,
) -> str:
    """Call the Ollama /api/generate endpoint and return the response text."""
    payload: dict = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        },
    }
    if system:
        payload["system"] = system

    url = f"{base_url}/api/generate"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()
        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %d/%d", attempt, MAX_RETRIES)
        except requests.exceptions.RequestException as exc:
            logger.warning("Request error on attempt %d/%d: %s", attempt, MAX_RETRIES, exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    logger.error("All %d attempts failed for prompt: %s…", MAX_RETRIES, prompt[:60])
    return ""


def check_ollama_available(base_url: str = OLLAMA_BASE_URL, model: str = MODEL_NAME) -> bool:
    """Return True if Ollama is reachable and the model is available."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        # Check for exact match or prefix match (e.g. "llama3" matches "llama3:latest")
        available = any(m == model or m.startswith(model + ":") for m in models)
        if not available:
            logger.warning("Model '%s' not found. Available: %s", model, models)
        return available
    except Exception as exc:
        logger.error("Cannot reach Ollama at %s: %s", base_url, exc)
        return False


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_attacks(
    behaviors: list[dict],
    output_path: Path,
    system_prompt: Optional[str] = None,
    input_filter_fn=None,
    mode_tag: str = "baseline",
    batch_size: int = DEFAULT_BATCH_SIZE,
    concurrency: int = CONCURRENCY,
) -> list[dict]:
    """Send each behavior's prompt to the model and save results as JSONL.
    Requests are sent concurrently (concurrency=OLLAMA_NUM_PARALLEL) for speed.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict] = [None] * len(behaviors)  # pre-allocate to preserve order
    write_lock = threading.Lock()

    def process(idx: int, behavior: dict) -> dict:
        prompt = behavior["prompt"]
        blocked = False
        if input_filter_fn is not None:
            prompt, blocked = input_filter_fn(prompt)
        response = "[BLOCKED BY INPUT FILTER]" if blocked else _ollama_generate(prompt, system=system_prompt)
        return {
            "id":          behavior["id"],
            "category":    behavior["category"],
            "attack_type": behavior["attack_type"],
            "goal":        behavior["goal"],
            "prompt":      behavior["prompt"],
            "response":    response,
            "blocked":     blocked,
            "mode":        mode_tag,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }

    with open(output_path, "w", encoding="utf-8") as out_fh:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(process, i, b): i for i, b in enumerate(behaviors)}
            pbar = tqdm(total=len(behaviors), desc=f"Running [{mode_tag}]")
            for future in as_completed(futures):
                idx = futures[future]
                record = future.result()
                results[idx] = record
                with write_lock:
                    out_fh.write(json.dumps(record) + "\n")
                    out_fh.flush()
                pbar.update(1)
            pbar.close()

    logger.info("Wrote %d results to %s", len(results), output_path)
    return results


# ── CLI entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Run jailbreak attacks against a model via Ollama")
    parser.add_argument(
        "--mode", choices=["baseline", "defense", "attack"], default="baseline",
        help="Run mode"
    )
    parser.add_argument(
        "--defense", choices=["sysprompt", "input_filter", "output_classifier"],
        default=None, help="Which defense to apply (--mode defense)"
    )
    parser.add_argument(
        "--attack", choices=["direct", "roleplay"],
        default="direct", help="Attack framing to apply (--mode attack or baseline)"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Override Ollama model tag (default: MODEL_NAME from config)"
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Max number of prompts")
    parser.add_argument("--output", type=str, default=None, help="Override output JSONL path")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    model = args.model or MODEL_NAME

    if not check_ollama_available(model=model):
        logger.error("Ollama model '%s' not available. Run: ollama pull %s", model, model)
        raise SystemExit(1)

    behaviors = load_behaviors(limit=args.limit)
    logger.info("Loaded %d behaviors", len(behaviors))

    # Apply attack framing to prompts
    from src.attacks import get_framing
    framing_fn = get_framing(args.attack)
    if args.attack != "direct":
        logger.info("Applying '%s' framing to all prompts", args.attack)
        behaviors = [{**b, "prompt": framing_fn(b["goal"])} for b in behaviors]

    if args.mode in ("baseline", "attack"):
        from src.config import RESULTS_DIR
        if args.output:
            output = Path(args.output)
        elif args.attack != "direct":
            output = RESULTS_DIR / f"attack_{args.attack}_{model.replace(':', '_')}.jsonl"
        elif model != MODEL_NAME:
            output = RESULTS_DIR / f"baseline_{model.replace(':', '_')}.jsonl"
        else:
            output = BASELINE_RAW
        mode_tag = f"baseline_{model}" if model != MODEL_NAME else f"baseline_{args.attack}"
        run_attacks(behaviors, output, system_prompt=None, mode_tag=mode_tag)

    elif args.mode == "defense":
        if args.defense is None:
            parser.error("--defense is required when --mode defense")
        from src.defenses import get_defense
        from src.config import DEFENSE_FILES, DEFENSE_ROLEPLAY_FILES, RESULTS_DIR
        defense = get_defense(args.defense)
        if args.output:
            output = Path(args.output)
        elif args.attack != "direct":
            output = DEFENSE_ROLEPLAY_FILES[args.defense].with_name(
                DEFENSE_ROLEPLAY_FILES[args.defense].stem.replace("_labeled", "_raw") + ".jsonl"
            )
        else:
            output = DEFENSE_FILES[args.defense].with_name(
                DEFENSE_FILES[args.defense].stem.replace("_labeled", "") + ".jsonl"
            )
        run_attacks(
            behaviors, output,
            system_prompt=defense.system_prompt,
            input_filter_fn=defense.input_filter,
            mode_tag=f"defense_{args.defense}_{args.attack}",
        )
        logger.info("Raw results saved to %s — run judge.py next.", output)

    logger.info("Done.")


if __name__ == "__main__":
    main()

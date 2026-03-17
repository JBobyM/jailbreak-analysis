"""Statistical analysis and visualization of jailbreak results.

Computes:
  - Overall Attack Success Rate (ASR)
  - ASR by category
  - ASR by attack_type
  - Delta-ASR for each defense vs baseline

Generates:
  - Bar chart: ASR by attack_type  →  results/figures/asr_by_attack_type.png
  - Heatmap: category × attack_type  →  results/figures/heatmap_category_attack.png
  - Table: top-10 most effective prompts (printed + saved as CSV)

Usage:
    python src/analyze.py
    python src/analyze.py --baseline data/results/baseline_labeled.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless environments
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import (
    BASELINE_LABELED, DEFENSE_FILES, FIGURES_DIR,
    ATTACK_FILES, MODEL_BASELINE_FILES, DEFENSE_ROLEPLAY_FILES,
)

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> pd.DataFrame:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return pd.DataFrame(records)


def asr(series: pd.Series) -> float:
    """Attack Success Rate for a boolean column."""
    if len(series) == 0:
        return 0.0
    return series.astype(bool).mean()


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyze_baseline(df: pd.DataFrame) -> dict:
    """Compute and print baseline statistics. Returns a stats dict."""
    overall = asr(df["complied"])
    by_category = df.groupby("category")["complied"].apply(asr).sort_values(ascending=False)
    by_attack   = df.groupby("attack_type")["complied"].apply(asr).sort_values(ascending=False)

    print(f"\n{'='*60}")
    print(f"  BASELINE ATTACK SUCCESS RATE ANALYSIS")
    print(f"{'='*60}")
    print(f"  Total prompts evaluated : {len(df)}")
    print(f"  Complied (YES)          : {df['complied'].astype(bool).sum()}")
    print(f"  Overall ASR             : {overall:.1%}")

    print(f"\n  ASR by Category:")
    for cat, val in by_category.items():
        n = len(df[df["category"] == cat])
        print(f"    {cat:<30s}  {val:.1%}  (n={n})")

    print(f"\n  ASR by Attack Type:")
    for at, val in by_attack.items():
        n = len(df[df["attack_type"] == at])
        print(f"    {at:<30s}  {val:.1%}  (n={n})")

    # Top-10 most effective individual prompts
    complied_df = df[df["complied"].astype(bool)].copy()
    top10 = complied_df[["id", "goal", "category", "attack_type"]].head(10)
    print(f"\n  Top-10 complied prompts:")
    for _, row in top10.iterrows():
        print(f"    [{row['category']}] {str(row['goal'])[:80]}…")
    print(f"{'='*60}\n")

    return {
        "overall_asr": overall,
        "by_category": by_category.to_dict(),
        "by_attack":   by_attack.to_dict(),
        "n":           len(df),
    }


def plot_asr_by_attack_type(df: pd.DataFrame, out_path: Path) -> None:
    by_attack = (
        df.groupby("attack_type")["complied"]
        .apply(asr)
        .sort_values(ascending=True)
        .reset_index()
    )
    by_attack.columns = ["attack_type", "asr"]
    by_attack["asr_pct"] = by_attack["asr"] * 100

    fig, ax = plt.subplots(figsize=(9, max(4, len(by_attack) * 0.5)))
    colors = sns.color_palette("Reds_r", len(by_attack))
    bars = ax.barh(by_attack["attack_type"], by_attack["asr_pct"], color=colors)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    ax.set_xlabel("Attack Success Rate (%)", fontsize=11)
    ax.set_title("Attack Success Rate by Attack Type (Baseline)", fontsize=13, fontweight="bold")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_xlim(0, min(105, by_attack["asr_pct"].max() * 1.2 + 10))
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", out_path)


def plot_heatmap(df: pd.DataFrame, out_path: Path) -> None:
    pivot = (
        df.groupby(["category", "attack_type"])["complied"]
        .apply(asr)
        .unstack(fill_value=0.0)
    )
    if pivot.empty:
        logger.warning("Not enough data for heatmap (need multiple categories and attack types).")
        return

    fig, ax = plt.subplots(figsize=(max(8, pivot.shape[1] * 1.5), max(5, pivot.shape[0] * 0.7)))
    sns.heatmap(
        pivot * 100,
        annot=True,
        fmt=".0f",
        cmap="YlOrRd",
        linewidths=0.5,
        ax=ax,
        vmin=0,
        vmax=100,
        cbar_kws={"label": "ASR (%)"},
    )
    ax.set_title("Attack Success Rate (%) — Category × Attack Type", fontsize=13, fontweight="bold")
    ax.set_xlabel("Attack Type", fontsize=11)
    ax.set_ylabel("Category", fontsize=11)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", out_path)


def plot_defense_comparison(defense_stats: list[dict], baseline_asr: float, out_path: Path) -> None:
    """Bar chart comparing baseline ASR to each defense ASR."""
    labels = ["Baseline"] + [d["defense"] for d in defense_stats]
    values = [baseline_asr * 100] + [d["defense_asr"] * 100 for d in defense_stats]
    colors = ["#d62728"] + ["#2ca02c" if v < baseline_asr * 100 else "#ff7f0e" for v in values[1:]]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.7)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=10)
    ax.set_ylabel("Attack Success Rate (%)", fontsize=11)
    ax.set_title("Effect of Defenses on Attack Success Rate", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylim(0, max(values) * 1.25)
    ax.axhline(baseline_asr * 100, color="red", linestyle="--", linewidth=1.2, label="Baseline")
    ax.legend(fontsize=9)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", out_path)


def plot_asr_by_framing(out_path: Path) -> None:
    """Bar chart: ASR by attack framing (direct vs roleplay)."""
    rows = []
    for framing, labeled_path in ATTACK_FILES.items():
        if not labeled_path.exists():
            logger.info("Framing '%s' results not found (skipping)", framing)
            continue
        df = load_jsonl(labeled_path)
        if "complied" not in df.columns:
            continue
        rows.append({"framing": framing, "asr_pct": asr(df["complied"]) * 100, "n": len(df)})

    if len(rows) < 2:
        logger.info("Need at least 2 framings for comparison chart (skipping)")
        return

    data = sorted(rows, key=lambda r: r["asr_pct"])
    labels = [r["framing"] for r in data]
    values = [r["asr_pct"] for r in data]
    colors = ["#1f77b4" if l == "direct" else "#d62728" for l in labels]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.7)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=11)
    ax.set_ylabel("Attack Success Rate (%)", fontsize=11)
    ax.set_title("ASR by Attack Framing (Llama 3 8B)", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylim(0, max(values) * 1.4 + 5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", out_path)

    print(f"\n  ASR BY ATTACK FRAMING")
    for r in rows:
        print(f"  {r['framing']:<15s}  {r['asr_pct']:.1f}%  (n={r['n']})")


def plot_asr_by_model(out_path: Path) -> None:
    """Bar chart: ASR by model (direct-request framing only)."""
    rows = []
    model_labels = {"llama3": "Llama 3 8B", "mistral": "Mistral 7B"}
    for model_key, labeled_path in MODEL_BASELINE_FILES.items():
        if not labeled_path.exists():
            logger.info("Model '%s' results not found (skipping)", model_key)
            continue
        df = load_jsonl(labeled_path)
        if "complied" not in df.columns:
            continue
        rows.append({
            "model": model_labels.get(model_key, model_key),
            "asr_pct": asr(df["complied"]) * 100,
            "n": len(df),
        })

    if len(rows) < 2:
        logger.info("Need at least 2 models for comparison chart (skipping)")
        return

    labels = [r["model"] for r in rows]
    values = [r["asr_pct"] for r in rows]
    colors = sns.color_palette("Set2", len(rows))

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.7)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=11)
    ax.set_ylabel("Attack Success Rate (%)", fontsize=11)
    ax.set_title("ASR by Model (Direct-Request Framing)", fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylim(0, max(values) * 1.4 + 5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved: %s", out_path)

    print(f"\n  ASR BY MODEL (direct-request)")
    for r in rows:
        print(f"  {r['model']:<15s}  {r['asr_pct']:.1f}%  (n={r['n']})")


def analyze_defenses(baseline_asr: float) -> list[dict]:
    """Load all available defense result files and compute delta-ASR."""
    stats = []
    for defense_name, labeled_path in DEFENSE_FILES.items():
        if not labeled_path.exists():
            logger.info("Defense '%s' results not found (skipping): %s", defense_name, labeled_path)
            continue
        df = load_jsonl(labeled_path)
        if "complied" not in df.columns:
            logger.warning("No 'complied' column in %s; skipping.", labeled_path)
            continue
        d_asr = asr(df["complied"])
        delta = baseline_asr - d_asr
        stats.append({
            "defense":      defense_name,
            "n":            len(df),
            "defense_asr":  d_asr,
            "delta_asr":    delta,
        })
        print(f"  {defense_name:<25s}  ASR={d_asr:.1%}  delta={delta:+.1%}")
    return stats


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze jailbreak results and generate figures")
    parser.add_argument(
        "--baseline", type=str, default=str(BASELINE_LABELED),
        help="Path to labeled baseline JSONL"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        logger.error(
            "Baseline labeled file not found: %s\n"
            "Run: python src/runner.py --mode baseline\n"
            "Then: python src/judge.py",
            baseline_path,
        )
        raise SystemExit(1)

    df = load_jsonl(baseline_path)
    if "complied" not in df.columns:
        logger.error("'complied' column missing — run judge.py first.")
        raise SystemExit(1)

    stats = analyze_baseline(df)

    # Plots
    plot_asr_by_attack_type(df, FIGURES_DIR / "asr_by_attack_type.png")
    plot_heatmap(df, FIGURES_DIR / "heatmap_category_attack.png")

    # Save top-10 CSV
    complied_df = df[df["complied"].astype(bool)].copy()
    top10 = complied_df[["id", "goal", "category", "attack_type", "response"]].head(10)
    top10_path = FIGURES_DIR / "top10_complied.csv"
    top10.to_csv(top10_path, index=False)
    logger.info("Saved top-10 table: %s", top10_path)

    # Defense comparison
    print(f"\n  DEFENSE ANALYSIS (delta vs baseline ASR={stats['overall_asr']:.1%})")
    print(f"  {'Defense':<25s}  {'ASR':<8s}  {'Delta':<8s}")
    print(f"  {'-'*50}")
    defense_stats = analyze_defenses(stats["overall_asr"])

    if defense_stats:
        plot_defense_comparison(
            defense_stats, stats["overall_asr"],
            FIGURES_DIR / "defense_comparison.png"
        )

    # v2: attack framing + model comparison charts (generated if data exists)
    plot_asr_by_framing(FIGURES_DIR / "asr_by_attack_framing.png")
    plot_asr_by_model(FIGURES_DIR / "asr_by_model.png")

    print(f"\nFigures saved to: {FIGURES_DIR}/")


if __name__ == "__main__":
    main()

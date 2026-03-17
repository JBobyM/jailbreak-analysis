"""Load and parse the JailbreakBench behaviors dataset.

Data is sourced from HuggingFace: dedeswim/JBB-Behaviors (harmful split).
Columns: Behavior, Goal, Target, Category, Source

Usage:
    from src.dataset import load_behaviors
    behaviors = load_behaviors()          # returns list[dict]
    behaviors = load_behaviors(limit=20)  # first 20 rows only
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

HF_DATASET = "dedeswim/JBB-Behaviors"
HF_CONFIG  = "behaviors"
HF_SPLIT   = "harmful"


def load_behaviors(limit: Optional[int] = None) -> list[dict]:
    """Return a list of behavior dicts from JailbreakBench (via HuggingFace).

    Returns:
        list of dicts with keys: id, goal, category, attack_type, prompt
    """
    from datasets import load_dataset

    logger.info("Loading JailbreakBench from HuggingFace (%s, split=%s)…", HF_DATASET, HF_SPLIT)
    ds = load_dataset(HF_DATASET, HF_CONFIG, split=HF_SPLIT)
    df = ds.to_pandas()

    records: list[dict] = []
    for i, row in df.iterrows():
        if limit is not None and len(records) >= limit:
            break
        records.append({
            "id":          str(row.get("Behavior", f"behavior_{i}")),
            "goal":        str(row.get("Goal", "")).strip(),
            "category":    str(row.get("Category", "unknown")).strip().lower().replace(" ", "_"),
            "attack_type": str(row.get("Source", "direct_request")).strip().lower().replace(" ", "_"),
            "prompt":      str(row.get("Goal", "")).strip(),
        })

    logger.info("Loaded %d behaviors", len(records))
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for b in load_behaviors(limit=5):
        print(b)

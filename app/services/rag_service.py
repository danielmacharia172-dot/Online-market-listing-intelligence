from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict

from app.config import FRAUD_PATTERNS_PATH


def load_fraud_patterns(path: Path | None = None) -> List[Dict[str, str]]:
    path = path or FRAUD_PATTERNS_PATH
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def retrieve_relevant_patterns(query: str, path: Path | None = None) -> List[Dict[str, str]]:
    patterns = load_fraud_patterns(path)
    query = query.lower()
    scored = []
    for item in patterns:
        score = sum(1 for keyword in item.get("keywords", []) if keyword.lower() in query)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda entry: entry[0], reverse=True)
    return [item for _, item in scored]

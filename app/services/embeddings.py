from __future__ import annotations

from typing import List


def build_keyword_signature(text: str) -> List[str]:
    return [token for token in text.lower().split() if len(token) > 3]

from __future__ import annotations

from typing import List, Dict

from app.services.rag_service import retrieve_relevant_patterns


def search_patterns(query: str) -> List[Dict[str, str]]:
    return retrieve_relevant_patterns(query=query)

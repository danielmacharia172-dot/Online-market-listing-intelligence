from __future__ import annotations

from typing import Any, Dict

from app.security import validate_listing_input


def recommend_price(title: str, description: str, price: int | float, location: str) -> Dict[str, Any]:
    title, description, price, location = validate_listing_input(title, description, price, location)
    text = f"{title} {description} {location}".lower()
    base = max(price, 1)

    if "iphone" in text:
        base = max(base * 0.9, 250)
    if any(term in text for term in ["macbook", "laptop", "gaming"]):
        base = max(base * 0.88, 180)
    if any(term in text for term in ["condition", "good", "excellent"]):
        base = base * 1.02
    if any(term in text for term in ["remote", "online"]):
        base = base * 0.95

    suggested_price = round(base, 0)
    rationale = (
        "The suggested price is derived from the listed price, the category cues in the title, and the level of detail in the description."
    )
    return {"suggested_price": int(suggested_price), "rationale": rationale}

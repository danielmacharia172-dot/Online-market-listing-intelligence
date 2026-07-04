from __future__ import annotations

from typing import Any, Dict

from app.security import validate_listing_input


def analyze_listing_quality(title: str, description: str, price: int | float, location: str) -> Dict[str, Any]:
    title, description, price, location = validate_listing_input(title, description, price, location)
    text = f"{title} {description} {location}".lower()
    score = 65

    if len(description.split()) >= 20:
        score += 10
    if any(keyword in text for keyword in ["condition", "battery", "charger", "includes", "box", "tested"]):
        score += 10
    if any(keyword in text for keyword in ["brand", "model", "size", "color", "year"]):
        score += 5
    if price and price > 0:
        score += 5
    if "remote" in location.lower() or "online" in location.lower():
        score -= 5

    recommendations = []
    if len(description.split()) < 20:
        recommendations.append("Add more descriptive details about the item condition and features.")
    if not any(keyword in text for keyword in ["condition", "battery", "charger", "includes", "tested"]):
        recommendations.append("Mention the item's condition, included accessories, and any testing details.")
    if not recommendations:
        recommendations.append("Listing quality looks strong; keep the details clear and specific.")

    return {"score": max(0, min(100, round(score))), "recommendations": recommendations}

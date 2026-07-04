from __future__ import annotations

from typing import Any, Dict

from app.security import validate_listing_input


def detect_fraud_signals(title: str, description: str, price: int | float, location: str) -> Dict[str, Any]:
    title, description, price, location = validate_listing_input(title, description, price, location)
    text = f"{title} {description} {location}".lower()
    reasons = []
    risk_score = 10

    if any(term in text for term in ["urgent", "cash only", "wire", "payment", "send money", "no questions"]):
        risk_score += 35
        reasons.append("The listing uses urgency or payment pressure language.")
    if price is not None and price <= 1:
        risk_score += 20
        reasons.append("The price is unusually low for a marketplace listing.")
    if any(term in text for term in ["click here", "link", "account", "verify"]):
        risk_score += 20
        reasons.append("The description asks the buyer to leave the platform or use external links.")
    if "remote" in location.lower() or "online" in location.lower():
        risk_score += 10
        reasons.append("The listing is marked as remote, which can increase risk for in-person verification.")

    if not reasons:
        reasons.append("No obvious fraud indicators were found in the provided input.")

    return {"risk_score": max(0, min(100, round(risk_score))), "reasons": reasons}

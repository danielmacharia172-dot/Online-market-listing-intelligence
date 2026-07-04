from __future__ import annotations

from typing import Any, Dict

from app.pipelines.fraud_detector import detect_fraud_signals
from app.pipelines.listing_quality import analyze_listing_quality
from app.security import validate_listing_input


def compute_trust_score(title: str, description: str, price: int | float, location: str) -> Dict[str, Any]:
    title, description, price, location = validate_listing_input(title, description, price, location)
    quality = analyze_listing_quality(title=title, description=description, price=price, location=location)
    fraud = detect_fraud_signals(title=title, description=description, price=price, location=location)

    trust_score = int(round((quality["score"] * 0.6) + ((100 - fraud["risk_score"]) * 0.4)))
    return {"trust_score": max(0, min(100, trust_score))}

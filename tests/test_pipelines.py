import pytest

from app.pipelines.listing_quality import analyze_listing_quality
from app.pipelines.fraud_detector import detect_fraud_signals
from app.pipelines.price_recommender import recommend_price
from app.pipelines.trust_score import compute_trust_score
from app.security import RateLimiter, authenticate_user
from app.logging_config import configure_logging, emit_audit_event


def test_listing_quality_pipeline_returns_expected_shape():
    result = analyze_listing_quality(
        title="Used iPhone 13 Pro Max",
        description="Great condition, battery healthy, includes charger",
        price=699,
        location="Austin, TX",
    )

    assert result["score"] >= 0
    assert result["score"] <= 100
    assert isinstance(result["recommendations"], list)


def test_fraud_detector_pipeline_returns_expected_shape():
    result = detect_fraud_signals(
        title="Urgent sale, cash only",
        description="Send payment to this account, no questions",
        price=1,
        location="Remote",
    )

    assert result["risk_score"] >= 0
    assert result["risk_score"] <= 100
    assert isinstance(result["reasons"], list)


def test_price_recommender_pipeline_returns_expected_shape():
    result = recommend_price(
        title="Used iPhone 13 Pro Max",
        description="Great condition, battery healthy, includes charger",
        price=699,
        location="Austin, TX",
    )

    assert result["suggested_price"] >= 0
    assert isinstance(result["rationale"], str)


def test_trust_score_pipeline_returns_expected_shape():
    result = compute_trust_score(
        title="Used iPhone 13 Pro Max",
        description="Great condition, battery healthy, includes charger",
        price=699,
        location="Austin, TX",
    )

    assert result["trust_score"] >= 0
    assert result["trust_score"] <= 100


def test_listing_quality_rejects_control_characters_and_oversized_input():
    with pytest.raises(ValueError):
        analyze_listing_quality(
            title="Bad\x00title",
            description="Great condition, battery healthy, includes charger",
            price=699,
            location="Austin, TX",
        )

    with pytest.raises(ValueError):
        analyze_listing_quality(
            title="Used iPhone",
            description="x" * 10001,
            price=699,
            location="Austin, TX",
        )


def test_rate_limiter_blocks_excessive_requests(monkeypatch):
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow_request("client-a")
    assert limiter.allow_request("client-a")
    assert not limiter.allow_request("client-a")


def test_authentication_uses_environment_credentials(monkeypatch):
    monkeypatch.setenv("APP_USERNAME", "admin")
    monkeypatch.setenv("APP_PASSWORD", "s3cr3t")

    assert authenticate_user("admin", "s3cr3t")
    assert not authenticate_user("admin", "wrong")
    assert not authenticate_user("other", "s3cr3t")


def test_audit_logging_writes_structured_event(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.log"
    monkeypatch.setenv("APP_AUDIT_LOG_PATH", str(audit_path))

    logger = configure_logging("INFO")
    emit_audit_event(logger, "login", {"status": "success", "user": "admin"})

    assert audit_path.exists()
    contents = audit_path.read_text(encoding="utf-8")
    assert "login" in contents
    assert "success" in contents

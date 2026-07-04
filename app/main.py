import streamlit as st
from PIL import Image
from typing import Any

from app.logging_config import configure_logging, emit_audit_event
from app.pipelines.fraud_detector import detect_fraud_signals
from app.pipelines.listing_quality import analyze_listing_quality
from app.pipelines.price_recommender import recommend_price
from app.pipelines.trust_score import compute_trust_score
from app.security import RateLimiter, authenticate_user, get_auth_credentials, get_client_identity, validate_listing_input


def analyze_uploaded_photo(uploaded_photo: Any) -> dict[str, Any]:
    image = Image.open(uploaded_photo)
    width, height = image.size
    file_size_kb = round(len(uploaded_photo.getvalue()) / 1024, 2)
    megapixels = round((width * height) / 1_000_000, 2)
    return {
        "width": width,
        "height": height,
        "megapixels": megapixels,
        "format": image.format or "unknown",
        "mode": image.mode,
        "file_size_kb": file_size_kb,
    }


def render_reviews_section(logger: Any, client_id: str) -> None:
    if "buyer_reviews" not in st.session_state:
        st.session_state.buyer_reviews = []

    st.markdown("---")
    st.header("Buyer Review Platform")
    st.caption("Collect buyer feedback so future shoppers can evaluate seller trust and listing quality.")

    with st.form("review_form"):
        reviewer = st.text_input("Buyer name", placeholder="Alex")
        rating = st.slider("Rating", min_value=1, max_value=5, value=5)
        review_text = st.text_area("Review", placeholder="Quick pickup, item exactly as described.")
        review_submitted = st.form_submit_button("Post review")

    if review_submitted:
        clean_reviewer = reviewer.strip()
        clean_review = review_text.strip()

        if not clean_reviewer or not clean_review:
            st.error("Buyer name and review text are required.")
        else:
            review_record = {
                "buyer": clean_reviewer,
                "rating": rating,
                "review": clean_review,
            }
            st.session_state.buyer_reviews.insert(0, review_record)
            emit_audit_event(logger, "review_posted", {"client": client_id, "rating": rating})
            st.success("Review posted.")

    reviews = st.session_state.buyer_reviews
    if not reviews:
        st.info("No buyer reviews yet. Be the first to post one.")
        return

    average_rating = round(sum(item["rating"] for item in reviews) / len(reviews), 2)
    col1, col2 = st.columns(2)
    col1.metric("Average buyer rating", f"{average_rating}/5")
    col2.metric("Total reviews", str(len(reviews)))

    st.markdown("### Recent reviews")
    for item in reviews[:20]:
        stars = "*" * item["rating"]
        st.markdown(f"**{item['buyer']}** ({item['rating']}/5) {stars}")
        st.write(item["review"])


def main() -> None:
    st.set_page_config(page_title="OfferUp AI Listing Intelligence", page_icon="🛍️")
    st.title("OfferUp AI Listing Intelligence")
    st.caption("Improve listing quality, detect fraud, recommend prices, and compute a trust score.")

    logger = configure_logging()
    rate_limiter = RateLimiter(max_requests=10, window_seconds=60)

    try:
        expected_username, expected_password = get_auth_credentials(getattr(st, "secrets", None))
    except RuntimeError as exc:
        st.error(str(exc))
        st.stop()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")

        if submitted:
            try:
                if authenticate_user(username, password, expected_username, expected_password):
                    st.session_state.authenticated = True
                    emit_audit_event(logger, "login", {"status": "success", "user": username})
                    st.rerun()
                emit_audit_event(logger, "login", {"status": "failed", "user": username})
                st.error("Invalid username or password")
            except Exception as exc:
                logger.exception("Login flow failed")
                st.error(f"Login failed unexpectedly: {exc}")
        st.stop()

    try:
        client_id = get_client_identity(getattr(st.context, "headers", {}))
        if not rate_limiter.allow_request(client_id):
            emit_audit_event(logger, "rate_limited", {"client": client_id})
            st.error("Too many requests from this client. Please wait a minute and try again.")
            st.stop()
    except Exception as exc:
        logger.exception("Client identification failed")
        st.error(f"Request setup failed unexpectedly: {exc}")
        st.stop()

    with st.form("listing_form"):
        title = st.text_input("Listing title", placeholder="Used iPhone 13 Pro Max")
        description = st.text_area("Description", placeholder="Describe the item clearly and include condition details.")
        price = st.number_input("Price", min_value=0, step=1, value=699)
        location = st.text_input("Location", placeholder="Austin, TX")
        uploaded_photo = st.file_uploader("Listing photo (optional)", type=["png", "jpg", "jpeg", "webp"])
        submitted = st.form_submit_button("Analyze listing")

    if submitted:
        try:
            title, description, price, location = validate_listing_input(title=title, description=description, price=price, location=location)
            quality = analyze_listing_quality(title=title, description=description, price=price, location=location)
            fraud = detect_fraud_signals(title=title, description=description, price=price, location=location)
            price_recommendation = recommend_price(title=title, description=description, price=price, location=location)
            trust = compute_trust_score(title=title, description=description, price=price, location=location)
            photo_insights = analyze_uploaded_photo(uploaded_photo) if uploaded_photo is not None else None
        except ValueError as exc:
            emit_audit_event(logger, "validation_failed", {"client": client_id, "error": str(exc)})
            st.error(f"Input validation failed: {exc}")
            st.stop()
        except Exception as exc:
            logger.exception("Listing analysis failed")
            emit_audit_event(logger, "analysis_failed", {"client": client_id, "error": str(exc)})
            st.error(f"Analysis failed unexpectedly: {exc}")
            st.stop()

        emit_audit_event(logger, "listing_analyzed", {"client": client_id, "score": quality["score"]})

        st.subheader("Results")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Quality score", f"{quality['score']}/100")
        col2.metric("Fraud risk", f"{fraud['risk_score']}/100")
        col3.metric("Suggested price", f"${price_recommendation['suggested_price']}")
        col4.metric("Trust score", f"{trust['trust_score']}/100")

        st.markdown("### Quality insights")
        for item in quality["recommendations"]:
            st.write(f"- {item}")

        st.markdown("### Fraud signals")
        for item in fraud["reasons"]:
            st.write(f"- {item}")

        st.markdown("### Price rationale")
        st.write(price_recommendation["rationale"])

        st.markdown("### Listing photo")
        if uploaded_photo is None:
            st.info("No photo uploaded. Adding at least one clear photo can improve buyer confidence.")
        else:
            st.image(uploaded_photo, caption="Uploaded listing photo", use_container_width=True)
            st.write(
                f"Format: {photo_insights['format']} | Resolution: {photo_insights['width']}x{photo_insights['height']} | "
                f"Megapixels: {photo_insights['megapixels']} | Size: {photo_insights['file_size_kb']} KB"
            )

    render_reviews_section(logger=logger, client_id=client_id)


if __name__ == "__main__":
    main()

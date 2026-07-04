import streamlit as st

from app.logging_config import configure_logging, emit_audit_event
from app.pipelines.fraud_detector import detect_fraud_signals
from app.pipelines.listing_quality import analyze_listing_quality
from app.pipelines.price_recommender import recommend_price
from app.pipelines.trust_score import compute_trust_score
from app.security import RateLimiter, authenticate_user, get_auth_credentials, get_client_identity, validate_listing_input

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
        if authenticate_user(username, password, expected_username, expected_password):
            st.session_state.authenticated = True
            emit_audit_event(logger, "login", {"status": "success", "user": username})
            st.rerun()
        emit_audit_event(logger, "login", {"status": "failed", "user": username})
        st.error("Invalid username or password")
    st.stop()

client_id = get_client_identity(getattr(st.context, "headers", {}))
if not rate_limiter.allow_request(client_id):
    emit_audit_event(logger, "rate_limited", {"client": client_id})
    st.error("Too many requests from this client. Please wait a minute and try again.")
    st.stop()

with st.form("listing_form"):
    title = st.text_input("Listing title", placeholder="Used iPhone 13 Pro Max")
    description = st.text_area("Description", placeholder="Describe the item clearly and include condition details.")
    price = st.number_input("Price", min_value=0, step=1, value=699)
    location = st.text_input("Location", placeholder="Austin, TX")
    submitted = st.form_submit_button("Analyze listing")

if submitted:
    try:
        title, description, price, location = validate_listing_input(title=title, description=description, price=price, location=location)
        quality = analyze_listing_quality(title=title, description=description, price=price, location=location)
        fraud = detect_fraud_signals(title=title, description=description, price=price, location=location)
        price_recommendation = recommend_price(title=title, description=description, price=price, location=location)
        trust = compute_trust_score(title=title, description=description, price=price, location=location)
    except ValueError as exc:
        emit_audit_event(logger, "validation_failed", {"client": client_id, "error": str(exc)})
        st.error(f"Input validation failed: {exc}")
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

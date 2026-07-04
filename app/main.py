import streamlit as st
from PIL import Image
from typing import Any
from datetime import datetime, timezone

from app.logging_config import configure_logging, emit_audit_event
from app.pipelines.fraud_detector import detect_fraud_signals
from app.pipelines.listing_quality import analyze_listing_quality
from app.pipelines.price_recommender import recommend_price
from app.pipelines.trust_score import compute_trust_score
from app.security import (
    MAX_DESCRIPTION_LENGTH,
    MAX_LOCATION_LENGTH,
    MAX_PRICE,
    MAX_TITLE_LENGTH,
    RateLimiter,
    authenticate_user,
    get_auth_credentials,
    get_client_identity,
    validate_listing_input,
)


def analyze_uploaded_photo(uploaded_photo: Any) -> dict[str, Any]:
    uploaded_photo.seek(0)
    image = Image.open(uploaded_photo)
    width, height = image.size
    file_size_kb = round(len(uploaded_photo.getvalue()) / 1024, 2)
    megapixels = round((width * height) / 1_000_000, 2)
    uploaded_photo.seek(0)
    return {
        "width": width,
        "height": height,
        "megapixels": megapixels,
        "format": image.format or "unknown",
        "mode": image.mode,
        "file_size_kb": file_size_kb,
    }


def build_listing_key(title: str, location: str) -> str:
    return f"{title.strip().lower()}|{location.strip().lower()}"


def listing_label(title: str, location: str) -> str:
    return f"{title} ({location})"


def render_reviews_section(logger: Any, client_id: str) -> None:
    if "buyer_reviews_by_listing" not in st.session_state:
        st.session_state.buyer_reviews_by_listing = {}
    if "analyzed_listings" not in st.session_state:
        st.session_state.analyzed_listings = {}
    if "last_listing_key" not in st.session_state:
        st.session_state.last_listing_key = None

    reviews_by_listing = st.session_state.buyer_reviews_by_listing
    listings = st.session_state.analyzed_listings

    st.markdown("---")
    st.header("Buyer Review Platform")
    st.caption("Collect buyer feedback for each listing so future shoppers can evaluate seller trust and listing quality.")

    listing_options = []
    for key, item in listings.items():
        listing_options.append({"key": key, "label": listing_label(item["title"], item["location"])})

    default_index = 0
    if st.session_state.last_listing_key is not None:
        for idx, option in enumerate(listing_options):
            if option["key"] == st.session_state.last_listing_key:
                default_index = idx
                break

    selected_listing_key = None
    selected_listing_title = ""
    selected_listing_location = ""

    if listing_options:
        selected_label = st.selectbox(
            "Listing to review",
            options=[item["label"] for item in listing_options],
            index=default_index,
        )
        for item in listing_options:
            if item["label"] == selected_label:
                selected_listing_key = item["key"]
                selected_listing_title = listings[item["key"]]["title"]
                selected_listing_location = listings[item["key"]]["location"]
                break
    else:
        st.info("Analyze a listing first, then buyers can post reviews for that listing.")
        return

    sort_order = st.selectbox("Sort reviews", ["Most recent", "Highest rating", "Lowest rating"])
    minimum_rating = st.slider("Minimum rating filter", min_value=1, max_value=5, value=1)

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
                "created_at": datetime.now(timezone.utc).isoformat(),
                "listing_title": selected_listing_title,
                "listing_location": selected_listing_location,
            }
            bucket = reviews_by_listing.setdefault(selected_listing_key, [])
            bucket.insert(0, review_record)
            emit_audit_event(
                logger,
                "review_posted",
                {
                    "client": client_id,
                    "rating": rating,
                    "listing_key": selected_listing_key,
                },
            )
            st.success("Review posted.")

    reviews = reviews_by_listing.get(selected_listing_key, [])
    reviews = [item for item in reviews if item["rating"] >= minimum_rating]

    if sort_order == "Highest rating":
        reviews = sorted(reviews, key=lambda item: item["rating"], reverse=True)
    elif sort_order == "Lowest rating":
        reviews = sorted(reviews, key=lambda item: item["rating"])

    if not reviews:
        st.info("No reviews match this listing/filter yet. Post a review to get started.")
        return

    average_rating = round(sum(item["rating"] for item in reviews) / len(reviews), 2)
    col1, col2 = st.columns(2)
    col1.metric("Average buyer rating", f"{average_rating}/5")
    col2.metric("Reviews shown", str(len(reviews)))

    st.write(f"Reviews for: **{listing_label(selected_listing_title, selected_listing_location)}**")

    st.markdown("### Recent reviews")
    for item in reviews[:20]:
        stars = "*" * item["rating"]
        st.markdown(f"**{item['buyer']}** ({item['rating']}/5) {stars}")
        st.write(item["review"])


def build_listing_field_errors(title: str, description: str, price: Any, location: str) -> dict[str, str]:
    errors: dict[str, str] = {}

    if not isinstance(title, str) or not title.strip():
        errors["title"] = "Listing title is required."
    elif len(title.strip()) > MAX_TITLE_LENGTH:
        errors["title"] = f"Listing title must be at most {MAX_TITLE_LENGTH} characters."

    if not isinstance(description, str) or not description.strip():
        errors["description"] = "Description is required."
    elif len(description.strip()) > MAX_DESCRIPTION_LENGTH:
        errors["description"] = f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."

    if not isinstance(location, str) or not location.strip():
        errors["location"] = "Location is required."
    elif len(location.strip()) > MAX_LOCATION_LENGTH:
        errors["location"] = f"Location must be at most {MAX_LOCATION_LENGTH} characters."

    try:
        numeric_price = float(price)
        if numeric_price < 0:
            errors["price"] = "Price cannot be negative."
        elif numeric_price > MAX_PRICE:
            errors["price"] = f"Price must be less than or equal to {MAX_PRICE}."
    except (TypeError, ValueError):
        errors["price"] = "Price must be numeric."

    combined_text = f"{title}{description}{location}"
    if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in combined_text):
        control_error = "Input contains unsupported control characters."
        for field_name in ("title", "description", "location"):
            errors.setdefault(field_name, control_error)

    return errors


def render_listing_field_highlights(errors: dict[str, str]) -> None:
    if not errors:
        return

    selectors = {
        "title": "input[aria-label='Listing title']",
        "description": "textarea[aria-label='Description']",
        "price": "input[aria-label='Price']",
        "location": "input[aria-label='Location']",
    }

    css_rules = []
    for field, selector in selectors.items():
        if field in errors:
            css_rules.append(
                f"{selector} {{ border: 2px solid #ff4b4b !important; box-shadow: 0 0 0 1px rgba(255, 75, 75, 0.35) !important; }}"
            )

    if css_rules:
        st.markdown(f"<style>{''.join(css_rules)}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="Online market listing intelligence", page_icon="🛍️")
    st.title("Online market listing intelligence")
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

    if "listing_field_errors" not in st.session_state:
        st.session_state.listing_field_errors = {}

    listing_field_errors: dict[str, str] = st.session_state.listing_field_errors
    render_listing_field_highlights(listing_field_errors)

    with st.form("listing_form"):
        title = st.text_input("Listing title", placeholder="Used iPhone 13 Pro Max")
        if "title" in listing_field_errors:
            st.error(listing_field_errors["title"])

        description = st.text_area("Description", placeholder="Describe the item clearly and include condition details.")
        if "description" in listing_field_errors:
            st.error(listing_field_errors["description"])

        price = st.number_input("Price", min_value=0, step=1, value=699)
        if "price" in listing_field_errors:
            st.error(listing_field_errors["price"])

        location = st.text_input("Location", placeholder="Austin, TX")
        if "location" in listing_field_errors:
            st.error(listing_field_errors["location"])

        uploaded_photos = st.file_uploader(
            "Listing photos (optional)",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
        submitted = st.form_submit_button("Analyze listing")

    if submitted:
        st.session_state.listing_field_errors = build_listing_field_errors(title, description, price, location)
        listing_field_errors = st.session_state.listing_field_errors

        if listing_field_errors:
            emit_audit_event(
                logger,
                "validation_failed",
                {
                    "client": client_id,
                    "field_errors": listing_field_errors,
                },
            )
            st.warning("Please fix the highlighted fields and submit again.")
            st.rerun()

        try:
            title, description, price, location = validate_listing_input(title=title, description=description, price=price, location=location)
            quality = analyze_listing_quality(title=title, description=description, price=price, location=location)
            fraud = detect_fraud_signals(title=title, description=description, price=price, location=location)
            price_recommendation = recommend_price(title=title, description=description, price=price, location=location)
            trust = compute_trust_score(title=title, description=description, price=price, location=location)
            photo_insights = [analyze_uploaded_photo(photo) for photo in (uploaded_photos or [])]
            st.session_state.listing_field_errors = {}
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

        current_listing_key = build_listing_key(title, location)
        st.session_state.analyzed_listings[current_listing_key] = {
            "title": title,
            "location": location,
        }
        st.session_state.last_listing_key = current_listing_key

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

        st.markdown("### Listing photos")
        if not uploaded_photos:
            st.info("No photos uploaded. Adding clear photos can improve buyer confidence and conversion.")
        else:
            columns_per_row = 3
            for start in range(0, len(uploaded_photos), columns_per_row):
                row_files = uploaded_photos[start : start + columns_per_row]
                row_insights = photo_insights[start : start + columns_per_row]
                cols = st.columns(len(row_files))

                for idx, uploaded_photo in enumerate(row_files):
                    insight = row_insights[idx]
                    with cols[idx]:
                        st.image(uploaded_photo, caption=f"Photo {start + idx + 1}", use_container_width=True)
                        st.caption(
                            f"{insight['format']} | {insight['width']}x{insight['height']} | "
                            f"{insight['megapixels']} MP | {insight['file_size_kb']} KB"
                        )

    render_reviews_section(logger=logger, client_id=client_id)


if __name__ == "__main__":
    main()

# Online market listing intelligence

This project provides a Streamlit-based experience for evaluating marketplace listings with four lightweight intelligence modules:

- Listing quality scoring
- Fraud signal detection
- Price recommendation
- Trust score computation
- Multi-photo listing upload with image gallery + basic image insights
- Built-in buyer review platform with per-listing 1-5 star ratings
- Review sorting and minimum-rating filtering controls
- Multi-user account creation and login with contact verification
- Remember username/password option per device session
- Privacy-aware AI prompt redaction for email/phone content
- AI update assistant that checks for updates and requires approval before update action

## Run locally

```bash
pip install -r requirements.txt
streamlit run app/main.py
```

## Production hardening

The app now includes a basic security layer suitable for internal or early production use:

- authentication via environment variables
- simple rate limiting per client/IP
- input validation to reject malformed or oversized submissions
- structured audit logging to stdout and an optional file

Verification code delivery (private):

- Email via SendGrid API or SMTP
- SMS via Twilio
- Codes expire in 10 minutes and each resend generates a new code

Set the following environment variables before launching the app:

```bash
export APP_USERNAME=admin
export APP_PASSWORD=change-me
export APP_AUDIT_LOG_PATH=./app_audit.log
export APP_AUTH_SALT=change-this-auth-salt
export DEMO_SHOW_VERIFICATION_CODES=false
export APP_GITHUB_REPO=danielmacharia172-dot/Online-market-listing-intelligence
export APP_BUILD_COMMIT=unknown

# Email (choose SendGrid OR SMTP)
export VERIFICATION_EMAIL_FROM=no-reply@example.com
export SENDGRID_API_KEY=

# SMTP fallback
export SMTP_HOST=
export SMTP_PORT=587
export SMTP_USERNAME=
export SMTP_PASSWORD=
export SMTP_USE_SSL=false

# SMS (Twilio)
export TWILIO_ACCOUNT_SID=
export TWILIO_AUTH_TOKEN=
export TWILIO_FROM_NUMBER=
```

Optional AI vision analysis (for real model-based photo understanding):

```bash
export OPENAI_API_KEY=your_api_key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
```

A sample file is available at [.env.example](.env.example).

## Container deployment

You can run the app in a container with:

```bash
docker build -t online-market-listing-intelligence .
docker run --rm -p 8501:8501 --env-file .env.example online-market-listing-intelligence
```

The repository also includes a Streamlit configuration file at [streamlit_config.toml](streamlit_config.toml) and a Docker build definition at [Dockerfile](Dockerfile).

## Streamlit Cloud

For Streamlit Cloud, the app entry point is [streamlit_app.py](streamlit_app.py). Deploy the repository directly and add the following secrets in the Streamlit Cloud UI:

```toml
APP_USERNAME="admin"
APP_PASSWORD="change-me"
APP_AUDIT_LOG_PATH="./app_audit.log"
APP_AUTH_SALT="change-this-auth-salt"
DEMO_SHOW_VERIFICATION_CODES="false"
APP_GITHUB_REPO="danielmacharia172-dot/Online-market-listing-intelligence"
APP_BUILD_COMMIT="unknown"
VERIFICATION_EMAIL_FROM="no-reply@example.com"
SENDGRID_API_KEY=""
SMTP_HOST=""
SMTP_PORT="587"
SMTP_USERNAME=""
SMTP_PASSWORD=""
SMTP_USE_SSL="false"
TWILIO_ACCOUNT_SID=""
TWILIO_AUTH_TOKEN=""
TWILIO_FROM_NUMBER=""
OPENAI_API_KEY="your_api_key"
OPENAI_MODEL="gpt-4o-mini"
OPENAI_BASE_URL="https://api.openai.com/v1"
```

The repository includes the standard Streamlit configuration at [.streamlit/config.toml](.streamlit/config.toml).

## Azure App Service

Azure deployment assets are included in [azure.yaml](azure.yaml), [app.yaml](app.yaml), and [startup.sh](startup.sh). The app can be deployed with the Azure CLI or Azure Developer CLI.

The current implementation uses rule-based heuristics and a small local RAG-style context layer over sample fraud patterns so the app can run without external model credentials.

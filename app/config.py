from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FRAUD_PATTERNS_PATH = DATA_DIR / "fraud_patterns.json"
SAMPLE_LISTINGS_PATH = DATA_DIR / "sample_listings.csv"

DEFAULT_MODEL = "gpt-4o-mini"

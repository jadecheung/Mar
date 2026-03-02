import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "hormuz-tracker-dev-key")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hormuz2026")
    CRON_SECRET = os.environ.get("CRON_SECRET", "hormuz-cron-secret")
    GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
    FIRESTORE_COLLECTION_RATES = "premium_rates"
    FIRESTORE_COLLECTION_NEWS = "news_events"
    FIRESTORE_COLLECTION_RISK = "risk_assessment"
    FIRESTORE_COLLECTION_META = "app_meta"
    PORT = int(os.environ.get("PORT", "8080"))

    # Vessel reference values for cost estimation (USD)
    VESSEL_VALUES = {
        "Small Tanker (Aframax)": 45_000_000,
        "Medium Tanker (Suezmax)": 75_000_000,
        "Large Tanker (VLCC)": 120_000_000,
        "Container Ship (Mid-size)": 100_000_000,
        "Container Ship (Large)": 150_000_000,
        "LNG Carrier": 200_000_000,
        "Bulk Carrier": 35_000_000,
    }

import logging
from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from config import Config

logger = logging.getLogger(__name__)

_db_instance = None


def _get_db():
    global _db_instance
    if _db_instance is None:
        if Config.GCP_PROJECT_ID:
            _db_instance = firestore.Client(project=Config.GCP_PROJECT_ID)
        else:
            _db_instance = firestore.Client()
    return _db_instance


def _serialize_doc(doc) -> dict:
    """Convert a Firestore document to a JSON-safe dict."""
    d = doc.to_dict()
    d["id"] = doc.id
    for key, val in d.items():
        if hasattr(val, "isoformat"):
            d[key] = val.isoformat()
    return d


# --------------- Premium Rates ---------------

def add_rate(date_str: str, rate_percent: float, vessel_type: str = "standard",
             source: str = "", notes: str = ""):
    db = _get_db()
    doc_data = {
        "date": datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc),
        "rate_percent": rate_percent,
        "vessel_type": vessel_type,
        "source": source,
        "notes": notes,
        "created_at": firestore.SERVER_TIMESTAMP,
    }
    db.collection(Config.FIRESTORE_COLLECTION_RATES).add(doc_data)
    return doc_data


def get_rates(vessel_type: str = "standard", limit: int = 500):
    """Get rates - uses client-side sorting to avoid needing composite index."""
    db = _get_db()
    try:
        # Try composite index query first (fast)
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_RATES)
            .where("vessel_type", "==", vessel_type)
            .order_by("date", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )
        return [_serialize_doc(doc) for doc in query.stream()]
    except Exception:
        # Fallback: filter only, sort client-side
        logger.info("Composite index not ready, using client-side sort for get_rates")
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_RATES)
            .where("vessel_type", "==", vessel_type)
            .limit(limit)
        )
        results = [_serialize_doc(doc) for doc in query.stream()]
        results.sort(key=lambda r: r.get("date", ""))
        return results


def get_latest_rate(vessel_type: str = "standard"):
    """Get the most recent rate - falls back to client-side sort."""
    db = _get_db()
    try:
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_RATES)
            .where("vessel_type", "==", vessel_type)
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        for doc in query.stream():
            return _serialize_doc(doc)
    except Exception:
        logger.info("Composite index not ready, using client-side sort for get_latest_rate")
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_RATES)
            .where("vessel_type", "==", vessel_type)
        )
        results = [_serialize_doc(doc) for doc in query.stream()]
        if results:
            results.sort(key=lambda r: r.get("date", ""), reverse=True)
            return results[0]
    return None


def delete_rate(doc_id: str):
    db = _get_db()
    db.collection(Config.FIRESTORE_COLLECTION_RATES).document(doc_id).delete()


def rate_exists_for_date(date_str: str, vessel_type: str = "standard") -> bool:
    """Check if a rate exists near a given date (client-side date check)."""
    db = _get_db()
    target = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    window_start = target - timedelta(hours=12)
    window_end = target + timedelta(hours=12)
    try:
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_RATES)
            .where("vessel_type", "==", vessel_type)
        )
        for doc in query.stream():
            d = doc.to_dict()
            dt = d.get("date")
            if hasattr(dt, "timestamp") and window_start <= dt <= window_end:
                return True
    except Exception as e:
        logger.warning("rate_exists_for_date error: %s", e)
    return False


# --------------- News / Events ---------------

def add_news(title: str, source: str, url: str, summary: str,
             impact: str = "neutral", date_str: str = ""):
    db = _get_db()
    date = (datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
            if date_str else datetime.now(timezone.utc))
    doc_data = {
        "date": date,
        "title": title,
        "source": source,
        "url": url,
        "summary": summary,
        "impact": impact,
        "scraped_at": firestore.SERVER_TIMESTAMP,
    }
    db.collection(Config.FIRESTORE_COLLECTION_NEWS).add(doc_data)
    return doc_data


def get_news(limit: int = 50):
    """Get news sorted by date descending."""
    db = _get_db()
    try:
        query = (
            db.collection(Config.FIRESTORE_COLLECTION_NEWS)
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [_serialize_doc(doc) for doc in query.stream()]
    except Exception:
        logger.info("Using client-side sort for get_news")
        query = db.collection(Config.FIRESTORE_COLLECTION_NEWS).limit(limit)
        results = [_serialize_doc(doc) for doc in query.stream()]
        results.sort(key=lambda r: r.get("date", ""), reverse=True)
        return results


def news_url_exists(url: str) -> bool:
    if not url:
        return False
    db = _get_db()
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_NEWS)
        .where("url", "==", url)
        .limit(1)
    )
    return any(True for _ in query.stream())


def news_title_exists(title: str) -> bool:
    db = _get_db()
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_NEWS)
        .where("title", "==", title)
        .limit(1)
    )
    return any(True for _ in query.stream())


def count_recent_news_by_impact(days: int = 7) -> dict:
    """Count news by impact. Client-side date filter to avoid needing index."""
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    counts = {"negative": 0, "positive": 0, "neutral": 0}
    try:
        for doc in db.collection(Config.FIRESTORE_COLLECTION_NEWS).stream():
            d = doc.to_dict()
            dt = d.get("date")
            if hasattr(dt, "timestamp") and dt >= cutoff:
                impact = d.get("impact", "neutral")
                counts[impact] = counts.get(impact, 0) + 1
    except Exception as e:
        logger.warning("count_recent_news_by_impact error: %s", e)
    return counts


# --------------- Risk Assessment ---------------

def get_risk_level():
    db = _get_db()
    try:
        doc = db.collection(Config.FIRESTORE_COLLECTION_RISK).document("current").get()
        if doc.exists:
            return _serialize_doc(doc)
    except Exception as e:
        logger.warning("get_risk_level error: %s", e)
    return {
        "level": "high",
        "factors": [
            "Active military operations in Persian Gulf",
            "Insurance policy cancellation notices issued",
            "Elevated geopolitical tensions (Iran-Israel-US)",
        ],
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def set_risk_level(level: str, factors: list):
    db = _get_db()
    db.collection(Config.FIRESTORE_COLLECTION_RISK).document("current").set({
        "level": level,
        "factors": factors,
        "last_updated": firestore.SERVER_TIMESTAMP,
    })


# --------------- App Meta (seeding flag) ---------------

def is_seeded() -> bool:
    db = _get_db()
    try:
        doc = db.collection(Config.FIRESTORE_COLLECTION_META).document("seed_status").get()
        return doc.exists and doc.to_dict().get("seeded", False)
    except Exception:
        return False


def mark_seeded():
    db = _get_db()
    db.collection(Config.FIRESTORE_COLLECTION_META).document("seed_status").set({
        "seeded": True,
        "seeded_at": firestore.SERVER_TIMESTAMP,
    })


def is_db_empty() -> bool:
    db = _get_db()
    try:
        query = db.collection(Config.FIRESTORE_COLLECTION_RATES).limit(1)
        return not any(True for _ in query.stream())
    except Exception:
        return True

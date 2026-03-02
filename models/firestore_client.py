from datetime import datetime, timedelta, timezone

from google.cloud import firestore

from config import Config

_db_instance = None


def _get_db():
    global _db_instance
    if _db_instance is None:
        if Config.GCP_PROJECT_ID:
            _db_instance = firestore.Client(project=Config.GCP_PROJECT_ID)
        else:
            _db_instance = firestore.Client()
    return _db_instance


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
    db = _get_db()
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_RATES)
        .where("vessel_type", "==", vessel_type)
        .order_by("date", direction=firestore.Query.ASCENDING)
        .limit(limit)
    )
    results = []
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        if hasattr(d["date"], "isoformat"):
            d["date"] = d["date"].isoformat()
        results.append(d)
    return results


def get_latest_rate(vessel_type: str = "standard"):
    db = _get_db()
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_RATES)
        .where("vessel_type", "==", vessel_type)
        .order_by("date", direction=firestore.Query.DESCENDING)
        .limit(1)
    )
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        if hasattr(d["date"], "isoformat"):
            d["date"] = d["date"].isoformat()
        return d
    return None


def delete_rate(doc_id: str):
    db = _get_db()
    db.collection(Config.FIRESTORE_COLLECTION_RATES).document(doc_id).delete()


def rate_exists_for_date(date_str: str, vessel_type: str = "standard") -> bool:
    """Check if a rate already exists for a given date (to prevent duplicates)."""
    db = _get_db()
    target = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    window_start = target - timedelta(hours=12)
    window_end = target + timedelta(hours=12)
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_RATES)
        .where("vessel_type", "==", vessel_type)
        .where("date", ">=", window_start)
        .where("date", "<=", window_end)
        .limit(1)
    )
    return any(True for _ in query.stream())


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
    db = _get_db()
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_NEWS)
        .order_by("date", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    results = []
    for doc in query.stream():
        d = doc.to_dict()
        d["id"] = doc.id
        if hasattr(d["date"], "isoformat"):
            d["date"] = d["date"].isoformat()
        results.append(d)
    return results


def news_url_exists(url: str) -> bool:
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
    """Count news items by impact in the last N days."""
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = (
        db.collection(Config.FIRESTORE_COLLECTION_NEWS)
        .where("date", ">=", cutoff)
    )
    counts = {"negative": 0, "positive": 0, "neutral": 0}
    for doc in query.stream():
        impact = doc.to_dict().get("impact", "neutral")
        counts[impact] = counts.get(impact, 0) + 1
    return counts


# --------------- Risk Assessment ---------------

def get_risk_level():
    db = _get_db()
    doc = db.collection(Config.FIRESTORE_COLLECTION_RISK).document("current").get()
    if doc.exists:
        d = doc.to_dict()
        if hasattr(d.get("last_updated"), "isoformat"):
            d["last_updated"] = d["last_updated"].isoformat()
        return d
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
    doc = db.collection(Config.FIRESTORE_COLLECTION_META).document("seed_status").get()
    return doc.exists and doc.to_dict().get("seeded", False)


def mark_seeded():
    db = _get_db()
    db.collection(Config.FIRESTORE_COLLECTION_META).document("seed_status").set({
        "seeded": True,
        "seeded_at": firestore.SERVER_TIMESTAMP,
    })


def is_db_empty() -> bool:
    db = _get_db()
    query = db.collection(Config.FIRESTORE_COLLECTION_RATES).limit(1)
    return not any(True for _ in query.stream())

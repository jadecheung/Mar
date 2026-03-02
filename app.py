import logging
import threading
from functools import wraps

from flask import Flask, jsonify, render_template, request

from config import Config
from models import firestore_client as db
from scrapers.news_scraper import scrape_all_sources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)


# --------------- Auto-seed on startup ---------------

_seed_lock = threading.Lock()
_seed_done = False


def _auto_seed_if_needed():
    """Seed historical data on first startup if DB is empty."""
    global _seed_done
    if _seed_done:
        return
    with _seed_lock:
        if _seed_done:
            return
        try:
            if not db.is_seeded() and db.is_db_empty():
                logger.info("Empty database detected — auto-seeding historical data...")
                from seed_data import main as run_seed
                run_seed()
                db.mark_seeded()
                logger.info("Auto-seed complete.")
            else:
                logger.info("Database already seeded.")
        except Exception as e:
            logger.error("Auto-seed failed: %s", e)
        _seed_done = True


# Run auto-seed in a background thread so startup isn't blocked
threading.Thread(target=_auto_seed_if_needed, daemon=True).start()


# --------------- Auth helpers ---------------

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        password = request.headers.get("X-Admin-Password") or request.form.get("password")
        if password != app.config["ADMIN_PASSWORD"]:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def require_cron_or_admin(f):
    """Accept either the cron secret (from Cloud Scheduler) or admin password."""
    @wraps(f)
    def decorated(*args, **kwargs):
        cron_secret = request.headers.get("X-Cron-Secret")
        admin_pw = request.headers.get("X-Admin-Password") or request.form.get("password")
        if cron_secret == app.config["CRON_SECRET"]:
            return f(*args, **kwargs)
        if admin_pw == app.config["ADMIN_PASSWORD"]:
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 401
    return decorated


# --------------- Pages ---------------

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# --------------- API: Rates ---------------

@app.route("/api/rates")
def api_get_rates():
    vessel_type = request.args.get("vessel_type", "standard")
    limit = int(request.args.get("limit", "500"))
    rates = db.get_rates(vessel_type=vessel_type, limit=limit)
    return jsonify(rates)


@app.route("/api/rates/latest")
def api_get_latest_rate():
    vessel_type = request.args.get("vessel_type", "standard")
    rate = db.get_latest_rate(vessel_type=vessel_type)
    if rate:
        return jsonify(rate)
    return jsonify({"error": "No rates found"}), 404


@app.route("/api/rates", methods=["POST"])
@require_admin
def api_add_rate():
    data = request.get_json() or request.form
    required = ["date", "rate_percent"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    db.add_rate(
        date_str=data["date"],
        rate_percent=float(data["rate_percent"]),
        vessel_type=data.get("vessel_type", "standard"),
        source=data.get("source", ""),
        notes=data.get("notes", ""),
    )
    return jsonify({"status": "ok"})


@app.route("/api/rates/<doc_id>", methods=["DELETE"])
@require_admin
def api_delete_rate(doc_id):
    db.delete_rate(doc_id)
    return jsonify({"status": "ok"})


# --------------- API: News ---------------

@app.route("/api/news")
def api_get_news():
    limit = int(request.args.get("limit", "50"))
    news = db.get_news(limit=limit)
    return jsonify(news)


@app.route("/api/news", methods=["POST"])
@require_admin
def api_add_news():
    data = request.get_json() or request.form
    required = ["title", "source", "summary"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    db.add_news(
        title=data["title"],
        source=data["source"],
        url=data.get("url", ""),
        summary=data["summary"],
        impact=data.get("impact", "neutral"),
        date_str=data.get("date", ""),
    )
    return jsonify({"status": "ok"})


# --------------- API: Risk Level ---------------

@app.route("/api/risk")
def api_get_risk():
    return jsonify(db.get_risk_level())


@app.route("/api/risk", methods=["POST"])
@require_admin
def api_set_risk():
    data = request.get_json() or request.form
    level = data.get("level", "high")
    factors = data.get("factors", [])
    if isinstance(factors, str):
        factors = [f.strip() for f in factors.split("\n") if f.strip()]
    db.set_risk_level(level, factors)
    return jsonify({"status": "ok"})


# --------------- API: Transit cost estimates ---------------

@app.route("/api/costs")
def api_get_costs():
    rate_data = db.get_latest_rate(vessel_type="standard")
    rate = rate_data["rate_percent"] if rate_data else 0.5
    costs = []
    for name, value in Config.VESSEL_VALUES.items():
        premium_usd = value * (rate / 100)
        costs.append({
            "vessel_type": name,
            "hull_value_usd": value,
            "premium_rate_pct": rate,
            "premium_usd": round(premium_usd),
        })
    return jsonify(costs)


# --------------- Cron endpoints (Cloud Scheduler) ---------------

@app.route("/cron/scrape", methods=["POST"])
@require_cron_or_admin
def cron_scrape():
    """
    Automated scrape endpoint called by Cloud Scheduler every 4 hours.
    Full pipeline: scrape sources -> extract rates -> classify news -> update risk.
    """
    logger.info("Cron scrape triggered")
    result = scrape_all_sources()
    return jsonify(result)


@app.route("/cron/seed", methods=["POST"])
@require_cron_or_admin
def cron_seed():
    """Trigger seed manually or from deploy script."""
    _auto_seed_if_needed()
    return jsonify({"status": "ok", "seeded": db.is_seeded()})


# --------------- API: Manual scrape trigger (admin) ---------------

@app.route("/api/scrape", methods=["POST"])
@require_admin
def api_trigger_scrape():
    result = scrape_all_sources()
    return jsonify(result)


# --------------- Main ---------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=True)

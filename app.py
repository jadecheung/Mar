import logging
from functools import wraps

from flask import Flask, jsonify, render_template, request

from config import Config
from models import firestore_client as db
from scrapers.news_scraper import scrape_all_sources
from scrapers.strikes_scraper import scrape_strikes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

_seeded = False


def _ensure_seeded():
    """Seed on first request if DB is empty. Runs once."""
    global _seeded
    if _seeded:
        return
    _seeded = True
    try:
        if not db.is_seeded() and db.is_db_empty():
            logger.info("Empty database detected — auto-seeding...")
            from seed_data import main as run_seed
            run_seed()
            db.mark_seeded()
            logger.info("Auto-seed complete.")
    except Exception as e:
        logger.error("Auto-seed failed: %s", e)


@app.before_request
def before_request():
    _ensure_seeded()


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


@app.route("/strikes")
def strikes():
    return render_template("strikes.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# --------------- API: Rates ---------------

@app.route("/api/rates")
def api_get_rates():
    vessel_type = request.args.get("vessel_type", "standard")
    limit = int(request.args.get("limit", "500"))
    try:
        rates = db.get_rates(vessel_type=vessel_type, limit=limit)
        return jsonify(rates)
    except Exception as e:
        logger.error("api_get_rates error: %s", e)
        return jsonify([])


@app.route("/api/rates/latest")
def api_get_latest_rate():
    vessel_type = request.args.get("vessel_type", "standard")
    try:
        rate = db.get_latest_rate(vessel_type=vessel_type)
        if rate:
            return jsonify(rate)
    except Exception as e:
        logger.error("api_get_latest_rate error: %s", e)
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
    try:
        news = db.get_news(limit=limit)
        return jsonify(news)
    except Exception as e:
        logger.error("api_get_news error: %s", e)
        return jsonify([])


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
    try:
        return jsonify(db.get_risk_level())
    except Exception as e:
        logger.error("api_get_risk error: %s", e)
        return jsonify({"level": "high", "factors": ["Data loading..."]})


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
    try:
        rate_data = db.get_latest_rate(vessel_type="standard")
        rate = rate_data["rate_percent"] if rate_data else 0.5
    except Exception:
        rate = 0.5
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


# --------------- API: Iranian Strikes ---------------

@app.route("/api/strikes")
def api_get_strikes():
    weapon_type = request.args.get("weapon_type", "")
    limit = int(request.args.get("limit", "500"))
    try:
        if weapon_type:
            strikes = db.get_strikes_by_type(weapon_type=weapon_type, limit=limit)
        else:
            strikes = db.get_strikes(limit=limit)
        return jsonify(strikes)
    except Exception as e:
        logger.error("api_get_strikes error: %s", e)
        return jsonify([])


@app.route("/api/strikes/latest")
def api_get_latest_strikes():
    limit = int(request.args.get("limit", "10"))
    try:
        return jsonify(db.get_latest_strikes(limit=limit))
    except Exception as e:
        logger.error("api_get_latest_strikes error: %s", e)
        return jsonify([])


@app.route("/api/strikes/summary")
def api_get_strike_summary():
    try:
        return jsonify(db.get_strike_summary())
    except Exception as e:
        logger.error("api_get_strike_summary error: %s", e)
        return jsonify({"totals": {}, "by_type": {}, "total_events": 0})


@app.route("/api/strikes", methods=["POST"])
@require_admin
def api_add_strike():
    data = request.get_json() or request.form
    required = ["date", "weapon_type", "launched"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    launched = int(data["launched"])
    intercepted = int(data.get("intercepted", 0))
    hit = int(data.get("hit", max(0, launched - intercepted)))
    db.add_strike(
        date_str=data["date"],
        weapon_type=data["weapon_type"],
        launched=launched,
        intercepted=intercepted,
        hit=hit,
        target=data.get("target", ""),
        source=data.get("source", ""),
        notes=data.get("notes", ""),
        operation=data.get("operation", ""),
    )
    return jsonify({"status": "ok"})


@app.route("/api/strikes/<doc_id>", methods=["DELETE"])
@require_admin
def api_delete_strike(doc_id):
    db.delete_strike(doc_id)
    return jsonify({"status": "ok"})


# --------------- Cron endpoints (Cloud Scheduler) ---------------

@app.route("/cron/scrape", methods=["POST"])
@require_cron_or_admin
def cron_scrape():
    logger.info("Cron scrape triggered")
    result = scrape_all_sources()
    # Also run strikes scraper
    strikes_result = scrape_strikes()
    result["strikes"] = strikes_result
    return jsonify(result)


@app.route("/cron/scrape-strikes", methods=["POST"])
@require_cron_or_admin
def cron_scrape_strikes():
    logger.info("Cron strikes scrape triggered")
    result = scrape_strikes()
    return jsonify(result)


@app.route("/cron/seed", methods=["POST"])
@require_cron_or_admin
def cron_seed():
    _ensure_seeded()
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

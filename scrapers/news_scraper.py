import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from models import firestore_client as db

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 20

# --------------- Source Configuration ---------------

# Google News RSS queries - fully automated, no API key needed
GOOGLE_NEWS_QUERIES = [
    "Strait of Hormuz insurance premium",
    "Hormuz war risk shipping",
    "Persian Gulf marine insurance",
    "maritime war risk premium Middle East",
    "shipping insurance Gulf Hormuz",
]

# Direct HTML search sources
HTML_SOURCES = [
    {
        "name": "Maritime Executive",
        "url": "https://maritime-executive.com/search?q=hormuz+insurance",
    },
    {
        "name": "gCaptain",
        "url": "https://gcaptain.com/?s=hormuz+insurance+premium",
    },
    {
        "name": "The Loadstar",
        "url": "https://theloadstar.com/?s=hormuz+war+risk",
    },
    {
        "name": "Splash247",
        "url": "https://splash247.com/?s=hormuz+insurance",
    },
    {
        "name": "Marine Insight",
        "url": "https://www.marineinsight.com/?s=hormuz+war+risk+premium",
    },
    {
        "name": "Hellenic Shipping News",
        "url": "https://www.hellenicshippingnews.com/?s=hormuz+insurance",
    },
    {
        "name": "FreightWaves",
        "url": "https://www.freightwaves.com/news?q=hormuz+insurance",
    },
]

# RSS feeds for maritime / shipping news
RSS_FEEDS = [
    {
        "name": "gCaptain RSS",
        "url": "https://gcaptain.com/feed/",
    },
    {
        "name": "Splash247 RSS",
        "url": "https://splash247.com/feed/",
    },
    {
        "name": "Hellenic Shipping RSS",
        "url": "https://www.hellenicshippingnews.com/feed/",
    },
    {
        "name": "Marine Insight RSS",
        "url": "https://www.marineinsight.com/feed/",
    },
]

# Relevance keywords - article must match at least one
RELEVANCE_KEYWORDS = [
    "hormuz", "war risk", "insurance premium", "persian gulf",
    "gulf of oman", "marine war", "shipping risk", "war insurance",
    "hull and machinery", "p&i", "marine insurance", "strait",
    "underwriter", "lloyd's", "jwc", "joint war committee",
]

# Patterns to extract premium rate percentages from article text
RATE_PATTERNS = [
    # "0.5% of hull value" / "0.25% of vessel value"
    re.compile(
        r"(\d+\.?\d*)\s*(?:%|per\s*cent)\s*(?:of\s+)?(?:hull|vessel|ship|insured)\s*(?:value|&\s*machinery)?",
        re.I,
    ),
    # "premiums rose to 0.5%" / "premium of 0.25%"
    re.compile(
        r"premium[s]?\s*(?:of|at|to|rose\s+to|jumped\s+to|increased\s+to|reached|hit|climbed\s+to|surged\s+to)\s*(\d+\.?\d*)\s*%",
        re.I,
    ),
    # "war risk rate of 0.5%" / "war risk premium at 0.25%"
    re.compile(
        r"war[\s-]*risk\s*(?:premium|rate|insurance)[s]?\s*(?:of|at|to|rose\s+to|reached|hit)?\s*(\d+\.?\d*)\s*%",
        re.I,
    ),
    # "rate rose from 0.25% to 0.5%" - captures the 'to' value
    re.compile(
        r"(?:from\s+\d+\.?\d*\s*%\s*to|to\s+)(\d+\.?\d*)\s*%\s*(?:of\s+)?(?:hull|vessel|insured)?",
        re.I,
    ),
    # "additional premium of 0.5%"
    re.compile(
        r"additional\s*premium\s*(?:of|at)\s*(\d+\.?\d*)\s*%",
        re.I,
    ),
]

# Impact classification keywords with weights
NEGATIVE_KEYWORDS = {
    "surge": 2, "jump": 2, "spike": 2, "soar": 2, "double": 3, "triple": 3,
    "rise": 1, "increase": 1, "climb": 1, "escalat": 2,
    "attack": 2, "strike": 2, "bomb": 3, "missile": 3, "drone": 2,
    "threat": 1, "cancel": 2, "suspend": 2, "halt": 2,
    "war": 1, "conflict": 1, "tension": 1, "crisis": 2,
    "sanction": 1, "blockade": 3, "mine": 2, "seize": 2,
}

POSITIVE_KEYWORDS = {
    "ease": 2, "fall": 2, "drop": 2, "decline": 2, "soften": 2, "lower": 2,
    "ceasefire": 3, "peace": 3, "truce": 3, "diplomacy": 2, "diplomatic": 2,
    "negotiate": 2, "agreement": 2, "deal": 2,
    "resume": 1, "stabiliz": 1, "calm": 2, "normal": 2, "reopen": 2,
    "de-escalat": 3, "withdraw": 2,
}


# --------------- Fetching Helpers ---------------

def _fetch_page(url: str) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def _fetch_rss(url: str) -> list[dict]:
    """Parse an RSS feed and return entries."""
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception as e:
        logger.warning("Failed to parse RSS %s: %s", url, e)
        return []


# --------------- Article Extraction ---------------

def _is_relevant(title: str, summary: str = "") -> bool:
    """Check if an article is relevant to Hormuz insurance."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def _extract_articles_from_html(html: str, source_name: str) -> list[dict]:
    """Extract article links from a search results page."""
    soup = BeautifulSoup(html, "lxml")
    articles = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        title = a_tag.get_text(strip=True)
        href = a_tag["href"]

        if not title or len(title) < 20 or not href.startswith("http"):
            continue
        if href in seen_urls:
            continue
        if not _is_relevant(title):
            continue

        seen_urls.add(href)
        articles.append({
            "title": title[:200],
            "url": href,
            "source": source_name,
        })

    return articles[:10]


def _extract_full_text(url: str) -> tuple[str, str]:
    """Fetch article and return (summary, full_text) for rate extraction."""
    html = _fetch_page(url)
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "lxml")

    # Remove script/style tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Summary from meta description
    summary = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        summary = meta["content"].strip()[:500]

    # Full text from article body
    article = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|post|entry"))
    target = article if article else soup.body
    if not target:
        return summary, ""

    paragraphs = target.find_all("p")
    full_text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

    if not summary and full_text:
        summary = full_text[:500]

    return summary, full_text


# --------------- Rate Extraction ---------------

def extract_rates_from_text(text: str) -> list[float]:
    """Extract premium rate percentages from text. Returns deduplicated sorted list."""
    rates = []
    for pattern in RATE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                rate = float(match.group(1))
                # War risk premiums realistically range from 0.01% to 2%
                if 0.01 <= rate <= 2.0:
                    rates.append(round(rate, 4))
            except (ValueError, IndexError):
                continue
    return sorted(set(rates))


def _auto_add_rate(rates: list[float], source: str, article_title: str):
    """Automatically add the highest extracted rate to DB if no rate exists for today."""
    if not rates:
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Use the highest rate mentioned (most likely the current/peak rate being reported)
    rate = max(rates)

    if not db.rate_exists_for_date(today, vessel_type="standard"):
        db.add_rate(
            date_str=today,
            rate_percent=rate,
            vessel_type="standard",
            source=source,
            notes=f"Auto-extracted from: {article_title[:100]}",
        )
        logger.info("  Auto-added rate: %.3f%% from %s", rate, source)
        return 1

    return 0


# --------------- Impact Classification ---------------

def _classify_impact(title: str, summary: str) -> str:
    """Weighted keyword-based impact classification."""
    text = (title + " " + summary).lower()
    neg_score = sum(w for kw, w in NEGATIVE_KEYWORDS.items() if kw in text)
    pos_score = sum(w for kw, w in POSITIVE_KEYWORDS.items() if kw in text)

    if neg_score > pos_score + 1:
        return "negative"
    if pos_score > neg_score + 1:
        return "positive"
    return "neutral"


# --------------- Risk Level Auto-Computation ---------------

def auto_update_risk_level():
    """Automatically compute and update risk level from recent news and current rates."""
    counts = db.count_recent_news_by_impact(days=14)
    total = sum(counts.values())

    latest = db.get_latest_rate(vessel_type="standard")
    current_rate = latest["rate_percent"] if latest else 0.1

    # Risk score: rate component (0-100) + news component (0-40)
    rate_score = current_rate * 100
    if total > 0:
        neg_ratio = counts["negative"] / total
        news_score = neg_ratio * 40
    else:
        news_score = 15

    risk_score = rate_score + news_score

    if risk_score >= 55:
        level = "extreme"
    elif risk_score >= 35:
        level = "high"
    elif risk_score >= 20:
        level = "moderate"
    else:
        level = "low"

    factors = []
    if current_rate >= 0.4:
        factors.append(f"War risk premiums at {current_rate:.2f}%+ of hull value")
    elif current_rate >= 0.2:
        factors.append(f"Elevated war risk premiums at {current_rate:.2f}% of hull value")
    elif current_rate >= 0.1:
        factors.append(f"War risk premiums moderately elevated at {current_rate:.2f}%")

    if counts["negative"] > 3:
        factors.append(f"{counts['negative']} negative events reported in the past 14 days")
    if counts["positive"] > 2:
        factors.append(f"{counts['positive']} positive developments in the past 14 days")

    if current_rate >= 0.5:
        factors.append("VLCC single-transit premium exceeds $600,000")
        factors.append("Some underwriters declining new Gulf cover")
    elif current_rate >= 0.25:
        factors.append("Transit costs significantly above baseline")
    if current_rate >= 0.3:
        factors.append("Insurance policy cancellation notices active")

    if not factors:
        factors.append("Monitoring geopolitical developments")

    db.set_risk_level(level, factors)
    logger.info("Auto-updated risk level to: %s (score=%.1f)", level, risk_score)
    return {"level": level, "score": round(risk_score, 1), "factors": factors}


# --------------- Main Scrape Pipeline ---------------

def _scrape_google_news() -> list[dict]:
    """Scrape Google News RSS for Hormuz insurance articles."""
    articles = []
    seen_urls = set()

    for query in GOOGLE_NEWS_QUERIES:
        rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        entries = _fetch_rss(rss_url)

        for entry in entries[:5]:
            title = entry.get("title", "")
            link = entry.get("link", "")

            if not title or not link or link in seen_urls:
                continue
            if not _is_relevant(title):
                continue

            seen_urls.add(link)
            articles.append({
                "title": title[:200],
                "url": link,
                "source": "Google News",
            })

    return articles


def _scrape_rss_feeds() -> list[dict]:
    """Scrape configured RSS feeds for relevant articles."""
    articles = []
    seen_urls = set()

    for feed_cfg in RSS_FEEDS:
        entries = _fetch_rss(feed_cfg["url"])

        for entry in entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")

            if not title or not link or link in seen_urls:
                continue
            if not _is_relevant(title, summary):
                continue

            seen_urls.add(link)
            articles.append({
                "title": title[:200],
                "url": link,
                "source": feed_cfg["name"],
            })

    return articles


def _scrape_html_sources() -> list[dict]:
    """Scrape HTML search pages for relevant articles."""
    articles = []

    for source in HTML_SOURCES:
        logger.info("Scraping %s ...", source["name"])
        html = _fetch_page(source["url"])
        if not html:
            continue
        articles.extend(_extract_articles_from_html(html, source["name"]))

    return articles


def scrape_all_sources() -> dict:
    """
    Full automated pipeline:
    1. Scrape Google News RSS + RSS feeds + HTML search pages
    2. Fetch each new article's full text
    3. Extract premium rates from article text and auto-add to DB
    4. Classify impact and store news
    5. Auto-update risk level based on all accumulated data
    """
    total_found = 0
    total_new = 0
    rates_added = 0

    # Collect articles from all sources
    all_articles = []
    all_articles.extend(_scrape_google_news())
    all_articles.extend(_scrape_rss_feeds())
    all_articles.extend(_scrape_html_sources())

    # Deduplicate across all sources
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    total_found = len(unique_articles)
    logger.info("Found %d unique relevant articles across all sources", total_found)

    for article in unique_articles:
        if db.news_url_exists(article["url"]):
            continue

        # Fetch full text for rate extraction
        summary, full_text = _extract_full_text(article["url"])
        impact = _classify_impact(article["title"], summary + " " + full_text[:1000])

        db.add_news(
            title=article["title"],
            source=article["source"],
            url=article["url"],
            summary=summary or article["title"],
            impact=impact,
        )
        total_new += 1
        logger.info("  Added: [%s] %s", impact, article["title"][:80])

        # Auto-extract and store premium rates from article text
        combined_text = article["title"] + " " + summary + " " + full_text
        rates = extract_rates_from_text(combined_text)
        if rates:
            logger.info("    Extracted rates: %s", rates)
            rates_added += _auto_add_rate(rates, article["source"], article["title"])

    # Auto-update risk level from all accumulated data
    risk_result = auto_update_risk_level()

    result = {
        "total_found": total_found,
        "new_added": total_new,
        "rates_extracted": rates_added,
        "risk_level": risk_result["level"],
        "risk_score": risk_result["score"],
    }
    logger.info("Scrape pipeline complete: %s", result)
    return result

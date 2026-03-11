"""
Iranian Strikes Scraper — scrapes news sources for reports of Iranian missile
and drone strikes, extracts launch counts, interception numbers and hit data.

Designed to run daily via Cloud Scheduler.
"""

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

GOOGLE_NEWS_QUERIES = [
    "Iran missile strike launched intercepted",
    "Iran drone attack hit rate",
    "Iranian ballistic missile strike Israel",
    "Iran cruise missile attack",
    "IRGC missile launch strike",
    "Iran retaliatory strike missiles drones",
]

RSS_FEEDS = [
    {"name": "Reuters World RSS", "url": "https://feeds.reuters.com/Reuters/worldNews"},
    {"name": "Al Jazeera RSS", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "BBC News RSS", "url": "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml"},
]

HTML_SOURCES = [
    {
        "name": "Times of Israel",
        "url": "https://www.timesofisrael.com/?s=iran+missile+strike",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/search/iran%20missile%20strike",
    },
    {
        "name": "Reuters",
        "url": "https://www.reuters.com/site-search/?query=iran+missile+strike",
    },
    {
        "name": "Defense News",
        "url": "https://www.defensenews.com/?s=iran+missile+strike",
    },
]

# Keywords for relevance filtering
RELEVANCE_KEYWORDS = [
    "iran", "iranian", "irgc", "islamic republic",
    "missile", "ballistic", "cruise missile", "drone", "uav", "shahed",
    "strike", "attack", "launch", "fire", "retaliat",
    "intercept", "iron dome", "arrow", "david's sling", "patriot",
    "hit", "impact", "damage", "casualt",
]

# Weapon type classification keywords
WEAPON_CLASSIFIERS = {
    "ballistic_missile": [
        "ballistic missile", "emad", "ghadr", "shahab", "fattah",
        "kheibar", "sejjil", "dezful", "haj qasem",
    ],
    "cruise_missile": [
        "cruise missile", "paveh", "hoveyzeh", "soumar", "ya ali",
    ],
    "drone": [
        "drone", "uav", "shahed", "ababil", "mohajer", "karrar",
        "unmanned aerial", "loitering munition", "one-way attack drone",
    ],
    "hypersonic": [
        "hypersonic", "fattah-2", "fattah 2",
    ],
}

# Patterns to extract numeric counts from article text
LAUNCH_PATTERNS = [
    re.compile(
        r"(?:launch|fire|sent|deploy|dispatch)\w*\s+(?:(?:more\s+than|over|about|approximately|nearly|around|some|up\s+to)\s+)?(\d+)\s*(?:ballistic\s+)?(?:missile|rocket|drone|uav|projectile|munition)",
        re.I,
    ),
    re.compile(
        r"(\d+)\s*(?:ballistic\s+)?(?:missile|rocket|drone|uav|projectile|munition)s?\s*(?:were\s+)?(?:launch|fire|sent|deploy|dispatch)",
        re.I,
    ),
    re.compile(
        r"(?:barrage|salvo|volley|wave)\s+of\s+(\d+)\s*(?:ballistic\s+)?(?:missile|drone|rocket|uav)",
        re.I,
    ),
    re.compile(
        r"(\d+)\s*(?:ballistic\s+)?(?:missile|drone|rocket)s?\s+(?:toward|at|against|aimed\s+at)",
        re.I,
    ),
]

INTERCEPT_PATTERNS = [
    re.compile(
        r"(?:intercept|shoot\s+down|shot\s+down|destroy|neutralize|down)\w*\s+(?:(?:more\s+than|over|about|approximately|nearly|around|some|up\s+to)\s+)?(\d+)\s*(?:of\s+the\s+)?(?:ballistic\s+)?(?:missile|rocket|drone|uav|projectile|incoming)",
        re.I,
    ),
    re.compile(
        r"(\d+)\s*(?:of\s+the\s+)?(?:ballistic\s+)?(?:missile|rocket|drone|uav|projectile)s?\s*(?:were\s+)?(?:intercept|shoot|shot|destroy|neutralize|down)",
        re.I,
    ),
    re.compile(
        r"(?:intercept|shot\s+down)\w*\s+(\d+)\s*(?:percent|%)\s*(?:of)?",
        re.I,
    ),
]

HIT_PATTERNS = [
    re.compile(
        r"(\d+)\s*(?:missile|rocket|drone|uav|projectile)s?\s*(?:hit|struck|impact|reached|got\s+through|penetrat)",
        re.I,
    ),
    re.compile(
        r"(?:hit|struck|impact|penetrat)\w*\s+(?:(?:by|with)\s+)?(\d+)\s*(?:missile|rocket|drone|uav)",
        re.I,
    ),
]


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
    try:
        feed = feedparser.parse(url)
        return feed.entries or []
    except Exception as e:
        logger.warning("Failed to parse RSS %s: %s", url, e)
        return []


# --------------- Article Processing ---------------

def _is_relevant(title: str, summary: str = "") -> bool:
    text = (title + " " + summary).lower()
    has_iran = any(kw in text for kw in ["iran", "irgc", "islamic republic", "tehran"])
    has_weapon = any(kw in text for kw in ["missile", "drone", "uav", "strike", "attack", "launch", "ballistic"])
    return has_iran and has_weapon


def _classify_weapon_type(text: str) -> str:
    text_lower = text.lower()
    scores = {}
    for wtype, keywords in WEAPON_CLASSIFIERS.items():
        scores[wtype] = sum(1 for kw in keywords if kw in text_lower)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "missile"


def _extract_full_text(url: str) -> tuple[str, str]:
    html = _fetch_page(url)
    if not html:
        return "", ""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    summary = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        summary = meta["content"].strip()[:500]

    article = soup.find("article") or soup.find("div", class_=re.compile(r"article|content|post|entry"))
    target = article if article else soup.body
    if not target:
        return summary, ""

    paragraphs = target.find_all("p")
    full_text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)

    if not summary and full_text:
        summary = full_text[:500]

    return summary, full_text


def _extract_number(patterns: list[re.Pattern], text: str) -> int | None:
    """Extract the first matching number from text using given patterns."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            try:
                val = int(match.group(1))
                if 1 <= val <= 5000:
                    return val
            except (ValueError, IndexError):
                continue
    return None


def _extract_strike_data(title: str, summary: str, full_text: str) -> dict | None:
    """Extract strike launch/intercept/hit data from article text."""
    combined = title + " " + summary + " " + full_text

    launched = _extract_number(LAUNCH_PATTERNS, combined)
    if not launched:
        return None

    intercepted = _extract_number(INTERCEPT_PATTERNS, combined)
    hit = _extract_number(HIT_PATTERNS, combined)

    # If we have launched and intercepted but no explicit hit count, compute it
    if intercepted is not None and hit is None:
        hit = max(0, launched - intercepted)
    # If we have hit but no intercept count
    elif hit is not None and intercepted is None:
        intercepted = max(0, launched - hit)
    # If neither, assume we can't determine
    elif intercepted is None and hit is None:
        intercepted = 0
        hit = 0

    weapon_type = _classify_weapon_type(combined)

    return {
        "launched": launched,
        "intercepted": intercepted,
        "hit": hit,
        "weapon_type": weapon_type,
    }


# --------------- Scrape Sources ---------------

def _scrape_google_news() -> list[dict]:
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
    articles = []

    for source in HTML_SOURCES:
        logger.info("Strikes scraper: scraping %s ...", source["name"])
        html = _fetch_page(source["url"])
        if not html:
            continue

        soup = BeautifulSoup(html, "lxml")
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
                "source": source["name"],
            })

    return articles[:30]


# --------------- Main Pipeline ---------------

def scrape_strikes() -> dict:
    """
    Full automated pipeline for Iranian strike data:
    1. Scrape Google News RSS + RSS feeds + HTML search pages
    2. Fetch each new article's full text
    3. Extract launch/intercept/hit data
    4. Store new strike records in Firestore
    """
    total_found = 0
    total_new = 0
    strikes_added = 0

    all_articles = []
    all_articles.extend(_scrape_google_news())
    all_articles.extend(_scrape_rss_feeds())
    all_articles.extend(_scrape_html_sources())

    # Deduplicate
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    total_found = len(unique_articles)
    logger.info("Strikes scraper: found %d unique relevant articles", total_found)

    for article in unique_articles:
        # Also store as news if not already present
        if db.news_url_exists(article["url"]):
            continue

        summary, full_text = _extract_full_text(article["url"])
        total_new += 1

        # Try to extract strike data
        strike_data = _extract_strike_data(article["title"], summary, full_text)
        if strike_data and strike_data["launched"] > 0:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            if not db.strike_exists_for_date(today, strike_data["weapon_type"]):
                db.add_strike(
                    date_str=today,
                    weapon_type=strike_data["weapon_type"],
                    launched=strike_data["launched"],
                    intercepted=strike_data["intercepted"],
                    hit=strike_data["hit"],
                    target="",
                    source=article["source"],
                    notes=f"Auto-extracted from: {article['title'][:100]}",
                )
                strikes_added += 1
                logger.info(
                    "  Strike recorded: %s — %d launched, %d intercepted, %d hit",
                    strike_data["weapon_type"],
                    strike_data["launched"],
                    strike_data["intercepted"],
                    strike_data["hit"],
                )

        # Store as news event too
        db.add_news(
            title=article["title"],
            source=article["source"],
            url=article["url"],
            summary=summary or article["title"],
            impact="negative",
        )
        logger.info("  Added strike news: %s", article["title"][:80])

    result = {
        "total_found": total_found,
        "articles_processed": total_new,
        "strikes_added": strikes_added,
    }
    logger.info("Strikes scrape pipeline complete: %s", result)
    return result

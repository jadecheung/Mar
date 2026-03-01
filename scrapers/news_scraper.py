import logging
import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from models import firestore_client as db

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = 15

# RSS / news sources focused on maritime insurance and Hormuz
SOURCES = [
    {
        "name": "Maritime Executive",
        "url": "https://maritime-executive.com/search?q=hormuz+insurance",
        "type": "html",
    },
    {
        "name": "gCaptain",
        "url": "https://gcaptain.com/?s=hormuz+insurance+premium",
        "type": "html",
    },
    {
        "name": "The Loadstar",
        "url": "https://theloadstar.com/?s=hormuz+war+risk",
        "type": "html",
    },
    {
        "name": "Splash247",
        "url": "https://splash247.com/?s=hormuz+insurance",
        "type": "html",
    },
]

# Patterns to identify premium rate mentions in article text
RATE_PATTERNS = [
    re.compile(r"(\d+\.?\d*)\s*%\s*(?:of\s+)?(?:hull|vessel|ship|insured)\s*(?:value)?", re.I),
    re.compile(r"premium[s]?\s*(?:of|at|to|rose to|jumped to|increased to|reached)\s*(\d+\.?\d*)\s*%", re.I),
    re.compile(r"war\s*risk\s*(?:premium|rate)[s]?\s*(?:of|at|to|rose to)?\s*(\d+\.?\d*)\s*%", re.I),
]


def _fetch_page(url: str) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def _extract_articles_generic(html: str, source_name: str, source_url: str) -> list[dict]:
    """Extract article links and titles from a search results page."""
    soup = BeautifulSoup(html, "lxml")
    articles = []

    # Look for common article link patterns
    for a_tag in soup.find_all("a", href=True):
        title = a_tag.get_text(strip=True)
        href = a_tag["href"]

        if not title or len(title) < 20:
            continue
        if not href.startswith("http"):
            continue

        # Filter for relevant articles
        keywords = ["hormuz", "war risk", "insurance", "premium", "persian gulf",
                     "gulf of oman", "strait", "marine war", "shipping risk"]
        title_lower = title.lower()
        if not any(kw in title_lower for kw in keywords):
            continue

        articles.append({
            "title": title[:200],
            "url": href,
            "source": source_name,
        })

    # Deduplicate by URL
    seen = set()
    unique = []
    for a in articles:
        if a["url"] not in seen:
            seen.add(a["url"])
            unique.append(a)
    return unique[:10]


def _extract_article_summary(url: str) -> str:
    """Fetch an article page and extract a brief summary."""
    html = _fetch_page(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")

    # Try meta description first
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        return meta["content"].strip()[:500]

    # Fall back to first few paragraphs
    paragraphs = soup.find_all("p")
    text_parts = []
    for p in paragraphs[:5]:
        text = p.get_text(strip=True)
        if len(text) > 40:
            text_parts.append(text)
    return " ".join(text_parts)[:500]


def _classify_impact(title: str, summary: str) -> str:
    """Simple keyword-based impact classification."""
    text = (title + " " + summary).lower()
    negative_kw = ["surge", "jump", "spike", "soar", "rise", "increase",
                    "attack", "strike", "threat", "cancel", "suspend", "double", "triple"]
    positive_kw = ["ease", "fall", "drop", "decline", "ceasefire", "peace",
                    "resume", "stabiliz", "soften", "lower", "calm"]
    neg_score = sum(1 for kw in negative_kw if kw in text)
    pos_score = sum(1 for kw in positive_kw if kw in text)
    if neg_score > pos_score:
        return "negative"
    if pos_score > neg_score:
        return "positive"
    return "neutral"


def scrape_all_sources() -> dict:
    """Scrape all configured news sources. Returns summary of results."""
    total_found = 0
    total_new = 0

    for source in SOURCES:
        logger.info("Scraping %s ...", source["name"])
        html = _fetch_page(source["url"])
        if not html:
            continue

        articles = _extract_articles_generic(html, source["name"], source["url"])
        total_found += len(articles)

        for article in articles:
            if db.news_url_exists(article["url"]):
                continue

            summary = _extract_article_summary(article["url"])
            impact = _classify_impact(article["title"], summary)

            db.add_news(
                title=article["title"],
                source=article["source"],
                url=article["url"],
                summary=summary or article["title"],
                impact=impact,
            )
            total_new += 1
            logger.info("  Added: %s", article["title"][:80])

    return {"total_found": total_found, "new_added": total_new}


def extract_rates_from_text(text: str) -> list[float]:
    """Extract premium rate percentages from article text."""
    rates = []
    for pattern in RATE_PATTERNS:
        for match in pattern.finditer(text):
            rate = float(match.group(1))
            if 0.01 <= rate <= 5.0:  # Sanity check: war risk premiums range
                rates.append(rate)
    return list(set(rates))

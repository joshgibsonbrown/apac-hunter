"""
M&A regulatory early warning scraper.

Combines three sub-sources:
- FTC Hart-Scott-Rodino (HSR) early termination notices
- UK CMA merger inquiry tracker
- EU Merger Control notifications

Falls back to news search when direct scraping is unavailable.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apac_hunter.regions import get_current_year

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research tool)", "Accept": "text/html,application/json"}


def fetch_ma_regulatory(days_back=30):
    """Fetch M&A regulatory filings from HSR, CMA, and EU sources."""
    results = []
    seen = set()

    print("  Fetching HSR early termination notices...")
    results.extend(_fetch_hsr(days_back, seen))

    print("  Fetching CMA merger inquiries...")
    results.extend(_fetch_cma(days_back, seen))

    print("  Fetching EU merger notifications...")
    results.extend(_fetch_eu_mergers(days_back, seen))

    print(f"  → {len(results)} M&A regulatory items found")
    return results


# ---------------------------------------------------------------------------
# HSR — FTC Early Termination Notices
# ---------------------------------------------------------------------------

def _fetch_hsr(days_back, seen):
    """Fetch FTC HSR early termination notices."""
    results = []

    # Try direct FTC page
    try:
        resp = requests.get(
            "https://www.ftc.gov/enforcement/premerger-notification-program/early-termination-notices",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            for row in soup.find_all(["tr", "div", "article"], limit=30):
                text = row.get_text(strip=True)
                if len(text) < 20:
                    continue

                text_lower = text.lower()
                if not any(kw in text_lower for kw in [
                    "early termination", "granted", "transaction", "acquiring"
                ]):
                    continue

                key = text[:80]
                if key in seen:
                    continue
                seen.add(key)

                link = row.find("a")
                url = ""
                if link and link.get("href"):
                    href = link["href"]
                    url = href if href.startswith("http") else f"https://www.ftc.gov{href}"

                results.append({
                    "source": "FTC HSR",
                    "company": _extract_company_from_text(text),
                    "title": f"HSR early termination: {text[:120]}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url or "https://www.ftc.gov/enforcement/premerger-notification-program/early-termination-notices",
                    "category": "hsr_notice",
                    "content": f"FTC HSR early termination notice: {text[:500]}",
                })

            if results:
                return results[:15]

    except Exception as e:
        print(f"    FTC direct scrape error: {e}")

    # Fallback: news search
    return _news_search(
        queries=[f"FTC early termination notice merger {get_current_year()}",
                 f"Hart-Scott-Rodino antitrust filing {get_current_year()}"],
        source_name="FTC HSR",
        category="hsr_notice",
        seen=seen,
        gl="us",
    )


# ---------------------------------------------------------------------------
# CMA — UK Competition and Markets Authority
# ---------------------------------------------------------------------------

def _fetch_cma(days_back, seen):
    """Fetch CMA merger inquiry cases."""
    results = []

    try:
        resp = requests.get(
            "https://www.gov.uk/cma-cases?case_type%5B%5D=mergers",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            for item in soup.find_all(["li", "div", "article"], class_=lambda c: c and "case" in str(c).lower(), limit=30):
                text = item.get_text(strip=True)
                if len(text) < 15:
                    continue

                key = text[:80]
                if key in seen:
                    continue
                seen.add(key)

                link = item.find("a")
                url = ""
                title_text = text[:150]
                if link:
                    url = link.get("href", "")
                    if url and not url.startswith("http"):
                        url = f"https://www.gov.uk{url}"
                    title_text = link.get_text(strip=True) or title_text

                results.append({
                    "source": "UK CMA",
                    "company": _extract_company_from_text(title_text),
                    "title": f"CMA merger inquiry: {title_text[:120]}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url or "https://www.gov.uk/cma-cases?case_type%5B%5D=mergers",
                    "category": "cma_inquiry",
                    "content": f"UK CMA merger inquiry: {text[:500]}",
                })

            if results:
                return results[:10]

    except Exception as e:
        print(f"    CMA direct scrape error: {e}")

    return _news_search(
        queries=[f"UK CMA merger inquiry {get_current_year()}",
                 f"Competition Markets Authority merger decision {get_current_year()}"],
        source_name="UK CMA",
        category="cma_inquiry",
        seen=seen,
        gl="gb",
    )


# ---------------------------------------------------------------------------
# EU Merger Control
# ---------------------------------------------------------------------------

def _fetch_eu_mergers(days_back, seen):
    """Fetch EU merger control notifications."""
    results = []

    try:
        resp = requests.get(
            "https://ec.europa.eu/competition/mergers/cases/",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            for row in soup.find_all(["tr", "div", "li"], limit=30):
                text = row.get_text(strip=True)
                if len(text) < 20:
                    continue

                text_lower = text.lower()
                if not any(kw in text_lower for kw in [
                    "notification", "decision", "merger", "acquisition",
                    "concentration", "phase",
                ]):
                    continue

                key = text[:80]
                if key in seen:
                    continue
                seen.add(key)

                link = row.find("a")
                url = ""
                if link and link.get("href"):
                    href = link["href"]
                    url = href if href.startswith("http") else f"https://ec.europa.eu{href}"

                results.append({
                    "source": "EU Merger Control",
                    "company": _extract_company_from_text(text),
                    "title": f"EU merger notification: {text[:120]}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url or "https://ec.europa.eu/competition/mergers/cases/",
                    "category": "eu_merger",
                    "content": f"EU merger control notification: {text[:500]}",
                })

            if results:
                return results[:10]

    except Exception as e:
        print(f"    EU merger direct scrape error: {e}")

    return _news_search(
        queries=[f"European Commission merger approval {get_current_year()}",
                 f"EU merger control notification {get_current_year()}"],
        source_name="EU Merger Control",
        category="eu_merger",
        seen=seen,
        gl="gb",
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _news_search(queries, source_name, category, seen, gl="us"):
    """SerpApi news fallback used by all sub-scrapers."""
    results = []
    if not SERPAPI_KEY:
        return results

    for query in queries[:3]:
        try:
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 5, "hl": "en", "gl": gl,
            }
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code != 200:
                continue

            for item in resp.json().get("news_results", []):
                url = item.get("link", "")
                if url in seen:
                    continue
                seen.add(url)

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                if not title:
                    continue

                news_source = (
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else "News"
                )

                results.append({
                    "source": f"{source_name} ({news_source})",
                    "company": _extract_company_from_text(f"{title} {snippet}"),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": category,
                    "content": f"{title}. {snippet}",
                })
        except Exception:
            continue

    return results[:10]


def _extract_company_from_text(text):
    """Best-effort company extraction."""
    known = [
        "Microsoft", "Google", "Amazon", "Apple", "Meta", "Nvidia",
        "Adobe", "Broadcom", "VMware", "Activision", "Figma",
        "ASML", "ARM", "Vodafone", "BHP", "Rio Tinto", "Shell",
        "Unilever", "Siemens", "Bayer", "BASF", "SAP",
        "Grab", "Sea Limited", "GoTo", "Tencent", "Alibaba",
    ]
    for c in known:
        if c.lower() in text.lower():
            return c
    return "Unknown — see filing"

"""
LSE Regulatory News Service (RNS) scraper via Investegate.

Investegate (www.investegate.co.uk) is a free public mirror of the London Stock
Exchange Regulatory News Service. The `category` filter parameter is ignored
server-side, so we fetch all recent RNS announcements and apply keyword
pre-filtering to keep only wealth-trigger-relevant items.
"""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research tool)",
    "Accept": "text/html,application/xhtml+xml",
}

BASE_URL = "https://www.investegate.co.uk/Index.aspx"

# Items to fetch per request (Investegate max appears to be 100)
PAGE_SIZE = 100

# Keywords that indicate the announcement is relevant to wealth trigger detection.
# The classifier will do the real work; this is just a coarse pre-filter to
# avoid sending thousands of irrelevant announcements downstream.
RELEVANT_KEYWORDS = [
    # Director / insider dealings
    "director", "pdmr", "person discharging", "notifiable transaction",
    "transaction in own shares",
    # Major shareholder
    "major shareholder", "substantial shareholder", "voting rights",
    "major holding", "transparency", "shareholding",
    # Corporate events (wealth triggers)
    "acquisition", "recommended offer", "scheme of arrangement",
    "takeover", "merger", "disposal", "significant transaction",
    "block trade", "secondary placing", "accelerated bookbuild",
    "share buyback", "tender offer",
    # IPO / listing
    "admission to trading", "ipo", "flotation", "listing",
    # Family / succession
    "family", "succession", "estate",
]


def fetch_rns_announcements(days_back: int = 7) -> list[dict]:
    """
    Fetch recent LSE RNS announcements from Investegate.

    Returns a list of dicts matching the standard scraper schema:
      source, company, title, date, url, category, content
    """
    cutoff = datetime.now() - timedelta(days=days_back)
    raw_items = _fetch_page(cutoff)

    # Keyword pre-filter
    results = [item for item in raw_items if _is_relevant(item)]

    print(f"  → {len(results)} RNS items fetched (last {days_back} days, "
          f"{len(raw_items)} raw before filter)")
    return results


def _fetch_page(cutoff: datetime) -> list[dict]:
    """Fetch the Investegate all-RNS page and parse the results table."""
    params = {
        "searchtype": "AllRNS",
        "pagesize": PAGE_SIZE,
    }
    try:
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  RNS: HTTP {resp.status_code}")
            return []
        return _parse_table(resp.text, cutoff)
    except Exception as exc:
        print(f"  RNS fetch error: {exc}")
        return []


def _parse_table(html: str, cutoff: datetime) -> list[dict]:
    """Parse the Investegate results HTML table into standard dicts."""
    soup = BeautifulSoup(html, "html.parser")

    table = (
        soup.find("table", class_="table-investegate")
        or soup.find("table", class_=re.compile(r"table", re.I))
    )
    if table is None:
        for t in soup.find_all("table"):
            if len(t.find_all("tr")) > 5:
                table = t
                break

    if table is None:
        return []

    results: list[dict] = []

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        # Column layout: [date+time, source/feed, company(ticker), headline+link]
        raw_date = cells[0].get_text(strip=True)
        company_cell = cells[2] if len(cells) >= 4 else cells[1]
        headline_cell = cells[3] if len(cells) >= 4 else cells[2]

        item_date = _parse_date(raw_date)
        if item_date is None or item_date < cutoff:
            continue

        raw_company = company_cell.get_text(strip=True)
        company_name, ticker = _extract_company_ticker(raw_company)

        link_tag = headline_cell.find("a", href=True)
        headline = link_tag.get_text(strip=True) if link_tag else headline_cell.get_text(strip=True)
        if not headline:
            continue

        article_url = _build_url(link_tag["href"] if link_tag else "")
        date_str = item_date.strftime("%Y-%m-%d")

        results.append({
            "source": "RNS",
            "company": company_name or raw_company,
            "title": f"{headline} — {company_name or raw_company}",
            "date": date_str,
            "url": article_url,
            "category": "RNS Regulatory Announcement",
            "content": (
                f"LSE RNS ANNOUNCEMENT: {headline}. "
                f"Company: {company_name or raw_company}"
                + (f" ({ticker})" if ticker else "")
                + f". Date: {date_str}."
            ),
        })

    return results


def _is_relevant(item: dict) -> bool:
    """Return True if the announcement headline/category suggests wealth trigger relevance."""
    text = (item.get("title", "") + " " + item.get("content", "")).lower()
    return any(kw in text for kw in RELEVANT_KEYWORDS)


# ── Helpers ───────────────────────────────────────────────────────────────────

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(raw: str) -> datetime | None:
    """
    Parse Investegate date strings.
    Formats seen: '09 Apr 2026 06:25 PM', '09 Apr 2026', '2026-04-09', '09/04/2026'
    """
    raw = raw.strip()
    if not raw:
        return None
    # ISO format
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d")
    except ValueError:
        pass
    # "DD Mon YYYY ..." (may have trailing time)
    parts = raw.split()
    if len(parts) >= 3:
        try:
            day = int(parts[0])
            month = _MONTHS.get(parts[1][:3].lower())
            year = int(parts[2])
            if month:
                return datetime(year, month, day)
        except (ValueError, TypeError):
            pass
    # "DD/MM/YYYY"
    try:
        return datetime.strptime(raw[:10], "%d/%m/%Y")
    except ValueError:
        pass
    return None


_TICKER_RE = re.compile(r"\(([A-Z0-9]{2,5})\)\s*$")


def _extract_company_ticker(raw: str) -> tuple[str, str]:
    """
    Extract company name and ticker from 'Legal & General Group Plc  (LGEN)'.
    Returns (company_name, ticker) — either may be empty string.
    """
    m = _TICKER_RE.search(raw)
    if m:
        ticker = m.group(1)
        name = raw[: m.start()].strip()
        return name, ticker
    return raw.strip(), ""


def _build_url(href: str) -> str:
    """Resolve a relative Investegate href to an absolute URL."""
    if not href:
        return "https://www.investegate.co.uk"
    if href.startswith("http"):
        return href
    return "https://www.investegate.co.uk" + ("" if href.startswith("/") else "/") + href

"""
HKEX new listing applications and recently listed companies monitor.

Attempts to scrape the HKEX IPO page. Falls back to SerpApi news
search if the page structure is too complex or unavailable.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apac_hunter.regions import get_current_year

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research tool)", "Accept": "text/html,application/json"}

HKEX_IPO_URL = "https://www.hkex.com.hk/Mutual-Market/Stock-Connect/Getting-Started/Information-Booklet-and-FAQ/IPO-Related?sc_lang=en"


def fetch_hkex_listings(days_back=30):
    """Fetch recent HKEX IPO applications and new listings."""
    results = []
    seen = set()

    # Try scraping HKEX directly
    results.extend(_scrape_hkex(days_back, seen))

    # Always supplement with news search for broader coverage
    results.extend(_news_fallback(days_back, seen))

    print(f"  → {len(results)} HKEX listing items found")
    return results


def _scrape_hkex(days_back, seen):
    """Attempt to scrape HKEX IPO page."""
    results = []
    try:
        resp = requests.get(HKEX_IPO_URL, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  HKEX returned {resp.status_code} — using news fallback")
            return results

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        for row in soup.find_all(["tr", "div", "li"], limit=50):
            text = row.get_text(strip=True)
            if not text or len(text) < 20:
                continue

            # Look for IPO-related content
            text_lower = text.lower()
            if not any(kw in text_lower for kw in ["listing", "ipo", "applicant", "prospectus", "offer"]):
                continue

            link = row.find("a")
            url = ""
            if link and link.get("href"):
                href = link["href"]
                url = href if href.startswith("http") else f"https://www.hkex.com.hk{href}"

            if text[:60] in seen:
                continue
            seen.add(text[:60])

            company = _extract_company_name(text)
            results.append({
                "source": "HKEX",
                "company": company,
                "title": f"HKEX listing activity: {company}",
                "date": datetime.now().strftime("%Y-%m-%d"),
                "url": url or "https://www.hkex.com.hk/Companies/IPO",
                "category": "ipo_application",
                "content": f"HKEX listing activity detected: {text[:500]}",
            })

    except Exception as e:
        print(f"  HKEX scrape error: {e}")

    return results[:15]


def _news_fallback(days_back, seen):
    """Search Google News for HKEX IPO activity."""
    results = []
    if not SERPAPI_KEY:
        return results

    year = get_current_year()
    queries = [
        f"HKEX IPO new listing {year}",
        f"Hong Kong IPO listing application {year}",
        f"Hong Kong stock exchange new listing founder {year}",
    ]

    for query in queries:
        try:
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 5, "hl": "en", "gl": "hk",
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

                source_name = (
                    item.get("source", {}).get("name", "HKEX News")
                    if isinstance(item.get("source"), dict)
                    else "HKEX News"
                )

                results.append({
                    "source": f"HKEX News ({source_name})",
                    "company": _extract_company_name(f"{title} {snippet}"),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "ipo_application",
                    "content": f"{title}. {snippet}",
                })
        except Exception as e:
            print(f"  HKEX news error: {e}")
            continue

    return results[:10]


def _extract_company_name(text):
    """Best-effort company extraction."""
    known = [
        "Alibaba", "JD.com", "Meituan", "Tencent", "Xiaomi", "BYD",
        "NIO", "Li Auto", "XPeng", "Bilibili", "NetEase", "Baidu",
        "SenseTime", "WuXi", "Kuaishou", "Zhihu", "Ke Holdings",
    ]
    for c in known:
        if c.lower() in text.lower():
            return c
    return "Unknown — see article"

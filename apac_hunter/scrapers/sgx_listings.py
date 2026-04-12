"""
SGX new listing applications and recently listed companies monitor.

Scrapes SGX's new listings section or falls back to news search.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apac_hunter.regions import get_current_year

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research tool)", "Accept": "application/json,text/html"}

SGX_LISTINGS_URL = "https://api.sgx.com/announcements/v1.0"


def fetch_sgx_listings(days_back=30):
    """Fetch recent SGX new listing applications and IPOs."""
    results = []
    seen = set()

    # Try SGX API for listing-related announcements
    results.extend(_fetch_sgx_api(days_back, seen))

    # Supplement with news search
    results.extend(_news_fallback(days_back, seen))

    print(f"  → {len(results)} SGX listing items found")
    return results


def _fetch_sgx_api(days_back, seen):
    """Query SGX announcements API for IPO/listing-related items."""
    results = []
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        params = {
            "periodstart": start_date.strftime("%Y%m%d") + "_000000",
            "periodend": end_date.strftime("%Y%m%d") + "_235959",
            "category": "all",
            "page": 1,
            "perpage": 50,
            "orderby": "datetime",
            "orderbydir": "desc",
        }

        resp = requests.get(SGX_LISTINGS_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return results

        text = resp.text
        if text.startswith("{}&&"):
            text = text[4:]

        import json
        data = json.loads(text) if text.startswith("{") or text.startswith("[") else resp.json()
        items = data.get("items", [])

        listing_keywords = [
            "new listing", "ipo", "listing application", "prospectus",
            "offer document", "introductory document", "catalist",
            "mainboard listing", "admission",
        ]

        for ann in items:
            title = ann.get("headline", "") or ann.get("title", "")
            category = ann.get("category", "")
            company = ann.get("issuerOrSecurityName", "") or ann.get("companyName", "")
            date_str = ann.get("announcementDate", "")
            ann_id = ann.get("id", "")

            combined = f"{title} {category}".lower()
            if not any(kw in combined for kw in listing_keywords):
                continue

            key = f"sgx-{ann_id}-{title[:40]}"
            if key in seen:
                continue
            seen.add(key)

            url = (
                f"https://www.sgx.com/securities/company-announcements/{ann_id}"
                if ann_id
                else "https://www.sgx.com/securities/company-announcements"
            )

            results.append({
                "source": "SGX Listings",
                "company": company or "Unknown",
                "title": f"SGX listing activity: {title[:100]}",
                "date": date_str[:10] if date_str else datetime.now().strftime("%Y-%m-%d"),
                "url": url,
                "category": "ipo_application",
                "content": f"SGX listing activity: {title}. Company: {company}. Category: {category}.",
            })

    except Exception as e:
        print(f"  SGX listings API error: {e}")

    return results[:15]


def _news_fallback(days_back, seen):
    """News search fallback for SGX listings."""
    results = []
    if not SERPAPI_KEY:
        return results

    year = get_current_year()
    queries = [
        f"SGX new listing IPO Singapore {year}",
        f"Singapore stock exchange IPO founder {year}",
        f"Catalist mainboard listing Singapore {year}",
    ]

    for query in queries:
        try:
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 5, "hl": "en", "gl": "sg",
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
                    item.get("source", {}).get("name", "SGX News")
                    if isinstance(item.get("source"), dict)
                    else "SGX News"
                )

                results.append({
                    "source": f"SGX Listings ({source_name})",
                    "company": _extract_company(f"{title} {snippet}"),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "ipo_application",
                    "content": f"{title}. {snippet}",
                })
        except Exception as e:
            print(f"  SGX listings news error: {e}")

    return results[:10]


def _extract_company(text):
    known = [
        "Grab", "Sea Limited", "PropertyGuru", "CapitaLand", "Mapletree",
        "Nanofilm", "Seatrium", "Sembcorp", "Keppel", "Wilmar",
    ]
    for c in known:
        if c.lower() in text.lower():
            return c
    return "Unknown — see article"

"""
Private company intelligence scraper.

Three sub-modules:
1. Late-stage funding round tracking (Series C+ at $100M+)
2. Unicorn watchlist with exit signal detection
3. Exit prediction signals (CFO hires, banker engagements, confidential S-1)
"""

import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from apac_hunter.regions import get_current_year

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# Rotation index for unicorn watchlist queries
_unicorn_rotation_index = 0

# Unicorn watchlist: company -> {founder, region, valuation_note}
UNICORN_WATCHLIST = {
    # APAC
    "ByteDance": {"founder": "Zhang Yiming", "region": "apac", "note": "TikTok parent, $225B+"},
    "Canva": {"founder": "Melanie Perkins", "region": "apac", "note": "Design platform, $40B"},
    "J&T Express": {"founder": "Jet Lee", "region": "apac", "note": "SE Asia logistics, $20B"},
    "Xendit": {"founder": "Moses Lo", "region": "apac", "note": "SE Asia payments"},
    "Advance Intelligence": {"founder": "Jefferson Chen", "region": "apac", "note": "AI fintech Singapore"},
    "Kredivo": {"founder": "Akshay Garg", "region": "apac", "note": "Indonesia BNPL"},
    "Coda Payments": {"founder": "Neil Davidson", "region": "apac", "note": "Digital payments"},
    "Nium": {"founder": "Prajit Nanu", "region": "apac", "note": "Global payments infra"},
    "PhonePe": {"founder": "Sameer Nigam", "region": "apac", "note": "India payments, $12B"},
    "Razorpay": {"founder": "Harshil Mathur", "region": "apac", "note": "India payments"},
    # Europe
    "Revolut": {"founder": "Nik Storonsky", "region": "europe", "note": "UK neobank, $45B"},
    "Klarna": {"founder": "Sebastian Siemiatkowski", "region": "europe", "note": "BNPL, $14.6B"},
    "Checkout.com": {"founder": "Guillaume Pousaz", "region": "europe", "note": "Payments, $40B peak"},
    "Personio": {"founder": "Hanno Renner", "region": "europe", "note": "HR platform Germany"},
    "Celonis": {"founder": "Alexander Rinke", "region": "europe", "note": "Process mining Germany, $13B"},
    "Bolt": {"founder": "Markus Villig", "region": "europe", "note": "Ride-hailing Estonia"},
    "Monzo": {"founder": "Tom Blomfield", "region": "europe", "note": "UK neobank"},
    "N26": {"founder": "Valentin Stalf", "region": "europe", "note": "German neobank"},
    "Sumup": {"founder": "Daniel Klein", "region": "europe", "note": "Payments, UK/Germany"},
    "Alan": {"founder": "Jean-Charles Samuelian", "region": "europe", "note": "Health insurance France"},
    # Global (relevant to both)
    "SpaceX": {"founder": "Elon Musk", "region": "global", "note": "$350B+, secondary active"},
    "Databricks": {"founder": "Ali Ghodsi", "region": "global", "note": "Data/AI, $62B"},
    "Discord": {"founder": "Jason Citron", "region": "global", "note": "Social platform"},
    "Ripple": {"founder": "Brad Garlinghouse", "region": "global", "note": "Crypto/blockchain"},
    "Stripe": {"founder": "Patrick Collison", "region": "global", "note": "Payments, $91B"},
    "OpenAI": {"founder": "Sam Altman", "region": "global", "note": "AI, $157B"},
    "Anthropic": {"founder": "Dario Amodei", "region": "global", "note": "AI safety"},
    "Shein": {"founder": "Sky Xu", "region": "global", "note": "Fast fashion, $66B"},
    "Chime": {"founder": "Chris Britt", "region": "global", "note": "US neobank, $25B"},
    "Plaid": {"founder": "Zach Perret", "region": "global", "note": "Fintech infra"},
}


def fetch_private_companies(days_back=14, region_config=None):
    """Fetch private company intelligence across all three sub-modules."""
    results = []
    seen = set()

    region_id = region_config.get("id", "global") if region_config else "global"

    # 1. Late-stage funding rounds
    results.extend(_fetch_funding_rounds(days_back, seen, region_id))

    # 2. Unicorn watchlist exit signals
    results.extend(_fetch_unicorn_signals(days_back, seen, region_id))

    # 3. Exit prediction signals
    results.extend(_fetch_exit_signals(days_back, seen))

    print(f"  → {len(results)} private company items found")
    return results


# ---------------------------------------------------------------------------
# 1. Late-stage funding round tracking
# ---------------------------------------------------------------------------

def _fetch_funding_rounds(days_back, seen, region_id):
    """Search for recent large funding rounds."""
    results = []
    if not SERPAPI_KEY:
        return results

    year = get_current_year()

    base_queries = [
        f"Series C funding round {year} $100 million",
        f"Series D funding {year} billion",
        f"late stage funding round unicorn {year}",
        f"pre-IPO funding round {year}",
    ]

    region_queries = {
        "apac": [
            f"Singapore startup funding Series C {year}",
            f"India startup funding round billion {year}",
            f"Southeast Asia startup funding {year}",
        ],
        "europe": [
            f"UK startup funding Series C {year}",
            f"European startup funding round {year}",
            f"German startup funding round {year}",
        ],
    }

    queries = base_queries + region_queries.get(region_id, [])

    for query in queries[:8]:  # Cap at 8 queries
        try:
            gl = {"apac": "sg", "europe": "gb"}.get(region_id, "us")
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 3, "hl": "en", "gl": gl,
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
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else "News"
                )

                results.append({
                    "source": f"Funding News ({source_name})",
                    "company": _extract_company(f"{title} {snippet}"),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "funding_round",
                    "content": f"{title}. {snippet}",
                })

            time.sleep(0.3)
        except Exception as e:
            print(f"  Funding search error: {e}")

    return results


# ---------------------------------------------------------------------------
# 2. Unicorn watchlist exit signals
# ---------------------------------------------------------------------------

def _fetch_unicorn_signals(days_back, seen, region_id):
    """Search for exit signals on watched unicorns."""
    results = []
    if not SERPAPI_KEY:
        return results

    # Filter to relevant unicorns for this region
    relevant = {}
    for company, info in UNICORN_WATCHLIST.items():
        if info["region"] == region_id or info["region"] == "global":
            relevant[company] = info

    # Rotate through unicorns — only query 5 per scan
    relevant_list = list(relevant.items())
    batch_size = 5
    global _unicorn_rotation_index
    start = _unicorn_rotation_index % max(len(relevant_list), 1)
    batch = relevant_list[start:start + batch_size]
    if len(batch) < batch_size:
        batch += relevant_list[:batch_size - len(batch)]
    _unicorn_rotation_index = (start + batch_size) % max(len(relevant_list), 1)

    print(f"    Querying {len(batch)} unicorns (rotation {start}-{start + batch_size})")

    for company, info in batch:
        try:
            query = f"{company} IPO OR acquisition OR secondary OR liquidity OR valuation"
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 2, "hl": "en", "gl": "us",
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
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else "News"
                )

                results.append({
                    "source": f"Unicorn Watch ({source_name})",
                    "company": company,
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "unicorn_signal",
                    "content": (
                        f"{title}. {snippet} "
                        f"[Unicorn watchlist: {company}, founder: {info['founder']}, "
                        f"{info['note']}]"
                    ),
                })

            time.sleep(0.3)
        except Exception as e:
            print(f"  Unicorn search error for {company}: {e}")

    return results


# ---------------------------------------------------------------------------
# 3. Exit prediction signals
# ---------------------------------------------------------------------------

def _fetch_exit_signals(days_back, seen):
    """Search for signals that private companies are approaching exit."""
    results = []
    if not SERPAPI_KEY:
        return results

    year = get_current_year()
    queries = [
        f"private company hires CFO IPO {year}",
        f"confidential S-1 filing {year}",
        f"company selects IPO underwriter {year}",
        f"hired Goldman Morgan Stanley IPO {year}",
        f"startup appoints CFO ahead IPO {year}",
    ]

    for query in queries[:5]:
        try:
            params = {
                "engine": "google_news", "q": query,
                "api_key": SERPAPI_KEY, "num": 3, "hl": "en", "gl": "us",
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
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else "News"
                )

                results.append({
                    "source": f"Exit Signal ({source_name})",
                    "company": _extract_company(f"{title} {snippet}"),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "exit_signal",
                    "content": f"{title}. {snippet}",
                })

            time.sleep(0.3)
        except Exception as e:
            print(f"  Exit signal search error: {e}")

    return results


def _extract_company(text):
    """Best-effort company extraction."""
    # Check watchlist first
    for company in UNICORN_WATCHLIST:
        if company.lower() in text.lower():
            return company

    known = [
        "Grab", "Sea Limited", "GoTo", "Tencent", "Alibaba",
        "ASML", "Spotify", "Wise", "Adyen", "Ferrari",
        "Airbnb", "Uber", "DoorDash", "Instacart", "Reddit",
    ]
    for c in known:
        if c.lower() in text.lower():
            return c

    return "Unknown — see article"

"""
Secondary market intelligence scraper.

Monitors publicly available data from secondary market platforms
(Forge Global, EquityZen) and searches news for tender offers,
employee liquidity programs, and secondary block trades.

Gracefully returns empty lists if endpoints are unavailable.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research tool)",
    "Accept": "text/html,application/json",
}

# Targeted secondary market news queries
SECONDARY_NEWS_QUERIES = [
    "tender offer secondary private company 2026",
    "employee liquidity program startup 2026",
    "secondary share sale unicorn private 2026",
    "Forge Global private shares trading 2026",
    "pre-IPO secondary market block trade 2026",
    "employee stock buyback private company 2026",
    "secondary transaction late stage startup 2026",
]


def fetch_secondary_market(days_back=14, region_config=None):
    """
    Fetch secondary market intelligence from multiple sources.

    Returns results in the standard scraper format with categories:
    secondary_trade, tender_offer, employee_liquidity.
    """
    results = []
    seen_urls = set()

    # 1. Forge Global public market data
    results.extend(_fetch_forge_global(days_back, seen_urls))

    # 2. EquityZen listings
    results.extend(_fetch_equityzen(days_back, seen_urls))

    # 3. News-based secondary market intelligence
    results.extend(_fetch_secondary_news(days_back, seen_urls, region_config))

    print(f"  → {len(results)} secondary market items found")
    return results


def _fetch_forge_global(days_back, seen_urls):
    """Attempt to scrape Forge Global's public market data."""
    results = []
    try:
        # Forge's market data page — try to get publicly listed companies
        resp = requests.get(
            "https://forgeglobal.com/market-data/",
            headers=HEADERS,
            timeout=15,
        )

        if resp.status_code != 200:
            print(f"  Forge Global returned {resp.status_code}")
            return results

        # Parse HTML for company listings
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for company cards/rows in the market data page
        # Forge's structure changes — try common patterns
        for card in soup.find_all(["div", "tr", "a"], class_=lambda c: c and (
            "company" in str(c).lower() or "listing" in str(c).lower()
            or "market" in str(c).lower()
        )):
            try:
                name_el = card.find(["h3", "h4", "td", "span", "a"])
                if not name_el:
                    continue

                company_name = name_el.get_text(strip=True)
                if not company_name or len(company_name) < 2 or len(company_name) > 100:
                    continue

                link = card.get("href", "") or ""
                if not link and card.find("a"):
                    link = card.find("a").get("href", "")

                url = f"https://forgeglobal.com{link}" if link.startswith("/") else (
                    link or "https://forgeglobal.com/market-data/"
                )

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                results.append({
                    "source": "Forge Global",
                    "company": company_name,
                    "title": f"Secondary market activity: {company_name}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "secondary_trade",
                    "content": (
                        f"Active secondary market trading detected for {company_name} "
                        f"on Forge Global's marketplace. This indicates demand for "
                        f"pre-IPO shares and potential founder/employee liquidity activity."
                    ),
                })
            except Exception:
                continue

    except Exception as e:
        print(f"  Forge Global scrape error: {e}")

    return results


def _fetch_equityzen(days_back, seen_urls):
    """Attempt to scrape EquityZen's publicly listed investment opportunities."""
    results = []
    try:
        resp = requests.get(
            "https://equityzen.com/companies/",
            headers=HEADERS,
            timeout=15,
        )

        if resp.status_code != 200:
            print(f"  EquityZen returned {resp.status_code}")
            return results

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # EquityZen lists companies with investment opportunities
        for card in soup.find_all(["div", "a"], class_=lambda c: c and (
            "company" in str(c).lower() or "card" in str(c).lower()
            or "listing" in str(c).lower()
        )):
            try:
                name_el = card.find(["h2", "h3", "h4", "span", "a"])
                if not name_el:
                    continue

                company_name = name_el.get_text(strip=True)
                if not company_name or len(company_name) < 2 or len(company_name) > 100:
                    continue

                link = card.get("href", "") or ""
                if not link and card.find("a"):
                    link = card.find("a").get("href", "")

                url = f"https://equityzen.com{link}" if link.startswith("/") else (
                    link or "https://equityzen.com/companies/"
                )

                if url in seen_urls:
                    continue
                seen_urls.add(url)

                results.append({
                    "source": "EquityZen",
                    "company": company_name,
                    "title": f"Secondary offering available: {company_name}",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "secondary_trade",
                    "content": (
                        f"Secondary market investment opportunity listed for "
                        f"{company_name} on EquityZen. This indicates employee "
                        f"or early investor shares are being offered for sale, "
                        f"suggesting active liquidity-seeking behavior."
                    ),
                })
            except Exception:
                continue

    except Exception as e:
        print(f"  EquityZen scrape error: {e}")

    return results


def _fetch_secondary_news(days_back, seen_urls, region_config=None):
    """Search Google News for secondary market events via SerpApi."""
    results = []

    if not SERPAPI_KEY:
        print("  SerpApi key not set — skipping secondary market news")
        return results

    gl_code = "us"
    if region_config:
        gl_code = {"apac": "sg", "europe": "gb"}.get(
            region_config.get("id", ""), "us"
        )

    for query in SECONDARY_NEWS_QUERIES:
        try:
            params = {
                "engine": "google_news",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 5,
                "hl": "en",
                "gl": gl_code,
            }

            resp = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=15,
            )

            if resp.status_code != 200:
                continue

            data = resp.json()
            for item in data.get("news_results", []):
                url = item.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                source_name = (
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else item.get("source", "News")
                )

                if not title:
                    continue

                # Categorize based on content
                content_lower = f"{title} {snippet}".lower()
                if "tender offer" in content_lower or "buyback" in content_lower:
                    category = "tender_offer"
                elif "employee" in content_lower and ("liquidity" in content_lower or "stock" in content_lower):
                    category = "employee_liquidity"
                else:
                    category = "secondary_trade"

                results.append({
                    "source": f"Secondary News ({source_name})",
                    "company": _extract_company(title, snippet),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": category,
                    "content": f"{title}. {snippet}",
                })

        except Exception as e:
            print(f"  Secondary news error for '{query}': {e}")
            continue

    return results


def _extract_company(title, snippet):
    """Best-effort company extraction from secondary market news."""
    combined = f"{title} {snippet}"

    known = [
        "SpaceX", "Stripe", "Databricks", "Canva", "Discord",
        "Instacart", "Klarna", "Revolut", "Plaid", "Figma",
        "OpenAI", "Anthropic", "Shein", "ByteDance", "Reddit",
        "Chime", "Ripple", "Kraken", "Blockchain.com",
        "Checkout.com", "Wise", "N26", "Monzo", "Nubank",
    ]

    for company in known:
        if company.lower() in combined.lower():
            return company

    return "Unknown — see article"

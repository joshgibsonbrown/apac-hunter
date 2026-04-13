import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def fetch_news(days_back=7, max_results_per_query=5, region_config=None):
    """Fetch founder wealth events from Google News via SerpApi.

    If *region_config* is provided its ``news_queries`` list is used;
    otherwise the function falls back to a minimal default query set so
    existing call-sites that don't pass a config still work.
    """
    if region_config is not None:
        search_queries = region_config["news_queries"]
        gl_code = _gl_for_region(region_config.get("id", ""))
    else:
        # Backwards-compat: bare minimum APAC queries
        search_queries = [
            "APAC founder acquisition merger deal 2026 Singapore Hong Kong",
            "Southeast Asia founder IPO listing 2026",
        ]
        gl_code = "sg"

    # Dynamically replace hardcoded years so queries don't go stale
    from apac_hunter.regions import get_current_year
    current_year = get_current_year()
    search_queries = [
        q.replace("2026", current_year).replace("2025", current_year)
        for q in search_queries
    ]

    results = []
    seen_urls = set()
    cutoff = datetime.now() - timedelta(days=days_back)

    for query in search_queries:
        try:
            params = {
                "engine": "google_news",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": max_results_per_query,
                "hl": "en",
                "gl": gl_code,
            }

            response = requests.get(
                "https://serpapi.com/search",
                params=params,
                timeout=15,
            )

            if response.status_code != 200:
                print(f"  SerpApi error for '{query}': {response.status_code}")
                continue

            data = response.json()
            news_results = data.get("news_results", [])

            for item in news_results:
                url = item.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                date_str = item.get("date", "")
                article_date = parse_news_date(date_str)
                if article_date and article_date < cutoff:
                    continue

                title = item.get("title", "")
                snippet = item.get("snippet", "")
                source = (
                    item.get("source", {}).get("name", "News")
                    if isinstance(item.get("source"), dict)
                    else item.get("source", "News")
                )

                content = f"{title}. {snippet}"

                if not title:
                    continue

                results.append({
                    "source": f"News ({source})",
                    "company": extract_company_from_news(title, snippet),
                    "title": title,
                    "date": (
                        article_date.strftime("%Y-%m-%d")
                        if article_date
                        else datetime.now().strftime("%Y-%m-%d")
                    ),
                    "url": url,
                    "category": "news",
                    "content": content,
                })

        except Exception as e:
            print(f"  News fetch error for '{query}': {e}")
            continue

    print(f"  → {len(results)} unique news items fetched")
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gl_for_region(region_id: str) -> str:
    """Return a Google geolocation code appropriate for the region."""
    return {
        "apac": "sg",
        "europe": "gb",
    }.get(region_id, "us")


def parse_news_date(date_str):
    """Parse various date formats from news results."""
    if not date_str:
        return None
    try:
        if "ago" in date_str.lower():
            if "hour" in date_str.lower() or "minute" in date_str.lower():
                return datetime.now()
            elif "day" in date_str.lower():
                days = int("".join(filter(str.isdigit, date_str)) or 1)
                return datetime.now() - timedelta(days=days)
            elif "week" in date_str.lower():
                weeks = int("".join(filter(str.isdigit, date_str)) or 1)
                return datetime.now() - timedelta(weeks=weeks)
            elif "month" in date_str.lower():
                months = int("".join(filter(str.isdigit, date_str)) or 1)
                return datetime.now() - timedelta(days=months * 30)
            elif "year" in date_str.lower():
                years = int("".join(filter(str.isdigit, date_str)) or 1)
                return datetime.now() - timedelta(days=years * 365)
        for fmt in ["%Y-%m-%d", "%b %d, %Y", "%d %b %Y", "%m/%d/%Y"]:
            try:
                return datetime.strptime(date_str[: len(fmt) + 2].strip(), fmt)
            except Exception:
                continue
    except Exception:
        pass
    return datetime.now()


def extract_company_from_news(title, snippet):
    """Best-effort company extraction from news title/snippet."""
    combined = f"{title} {snippet}"

    known_companies = [
        "Grab", "Sea Limited", "Shopee", "Gojek", "GoTo", "Tokopedia",
        "Razer", "Lazada", "Carousell", "PropertyGuru", "Kredivo",
        "Bukalapak", "OVO", "Dana", "LinkAja", "Xendit", "Akulaku",
        "Tencent", "Alibaba", "ByteDance", "Ant Group", "JD.com",
        "Meituan", "Didi", "Pinduoduo", "Kuaishou", "Bilibili",
        "CapitaLand", "DBS", "OCBC", "UOB", "Wilmar", "Jardine",
        "Ayala", "SM Group", "Jollibee", "ICTSI",
        "Central Group", "PTT", "Charoen Pokphand",
        "Sime Darby", "YTL", "Genting", "IOI Group", "Kuok Group",
        # Europe
        "ASML", "Spotify", "Wise", "Flutter", "Unilever", "SAP",
        "Novo Nordisk", "AstraZeneca", "GSK", "Ferrari", "Arm Holdings",
        "Birkenstock", "Criteo", "Endava", "Adyen", "Klarna", "Revolut",
        "Deliveroo", "Cazoo", "N26", "Zalando", "AUTO1", "Personio",
    ]

    for company in known_companies:
        if company.lower() in combined.lower():
            return company

    return "Unknown — see article"


def fetch_sgx_targeted_news(days_back=7, max_results_per_query=5):
    """Targeted SGX filing searches via Google News as fallback for direct API."""
    results = []
    seen_urls = set()

    sgx_queries = [
        "SGX substantial shareholder change Singapore listed 2026",
        "SGX director interest disposal acquisition Singapore 2026",
        "SGX EGM voting rights dual class shares Singapore 2026",
        "Singapore listed company major shareholder block trade 2026",
    ]

    for query in sgx_queries:
        try:
            params = {
                "engine": "google_news",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": max_results_per_query,
                "hl": "en",
                "gl": "sg",
            }
            response = requests.get(
                "https://serpapi.com/search", params=params, timeout=15
            )
            if response.status_code != 200:
                continue
            data = response.json()
            for item in data.get("news_results", []):
                url = item.get("link", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                source = (
                    item.get("source", {}).get("name", "SGX News")
                    if isinstance(item.get("source"), dict)
                    else "SGX News"
                )
                if not title:
                    continue
                results.append({
                    "source": f"SGX News ({source})",
                    "company": extract_company_from_news(title, snippet),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": "sgx_news",
                    "content": f"{title}. {snippet}",
                })
        except Exception as e:
            print(f"  SGX news error: {e}")
            continue

    print(f"  → {len(results)} SGX news items fetched")
    return results

"""
PE firm and advisory bank deal announcement monitor.

Uses a mix of RSS feeds and SerpApi news search to track deal
announcements, portfolio exits, and IPO sponsorships from major
PE firms and advisory banks.
"""

import os
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apac_hunter.regions import get_current_year

load_dotenv()

SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# PE firms and advisors with their press/news RSS feeds (where available)
PE_FIRMS = [
    {"name": "KKR", "rss": "https://media.kkr.com/rss/news.xml", "queries": ["KKR portfolio exit sale", "KKR acquisition deal"]},
    {"name": "Blackstone", "rss": "https://www.blackstone.com/press-releases/feed/", "queries": ["Blackstone portfolio exit", "Blackstone acquisition"]},
    {"name": "Apollo", "rss": None, "queries": ["Apollo Global Management deal", "Apollo portfolio exit sale"]},
    {"name": "CVC Capital", "rss": None, "queries": ["CVC Capital Partners deal exit", "CVC acquisition"]},
    {"name": "EQT", "rss": "https://eqtgroup.com/feed/", "queries": ["EQT Partners exit sale", "EQT acquisition deal"]},
    {"name": "Warburg Pincus", "rss": None, "queries": ["Warburg Pincus exit sale", "Warburg Pincus investment deal"]},
    {"name": "TPG", "rss": None, "queries": ["TPG Capital exit sale IPO", "TPG acquisition deal"]},
    {"name": "Carlyle", "rss": "https://www.carlyle.com/media-room/rss.xml", "queries": ["Carlyle Group exit sale", "Carlyle acquisition"]},
    {"name": "Advent International", "rss": None, "queries": ["Advent International exit sale", "Advent International deal"]},
    {"name": "Permira", "rss": None, "queries": ["Permira exit sale IPO", "Permira acquisition deal"]},
]

ADVISORY_FIRMS = [
    {"name": "Goldman Sachs", "queries": ["Goldman Sachs advises merger acquisition", "Goldman Sachs IPO underwriter"]},
    {"name": "Morgan Stanley", "queries": ["Morgan Stanley advises merger", "Morgan Stanley IPO lead"]},
    {"name": "Lazard", "queries": ["Lazard advises merger acquisition deal"]},
    {"name": "Rothschild", "queries": ["Rothschild advises merger acquisition"]},
    {"name": "Evercore", "queries": ["Evercore advises merger acquisition deal"]},
]


def fetch_pe_deal_feeds(days_back=14):
    """Fetch PE and advisory deal announcements."""
    results = []
    seen = set()

    # PE firms — try RSS first, fall back to news
    for firm in PE_FIRMS:
        if firm.get("rss"):
            rss_results = _try_rss(firm["name"], firm["rss"], days_back, seen)
            if rss_results:
                results.extend(rss_results)
                continue

        results.extend(_search_firm(firm["name"], firm["queries"], seen, "pe_exit"))

    # Advisory firms — news search only
    for firm in ADVISORY_FIRMS:
        results.extend(_search_firm(firm["name"], firm["queries"], seen, "advisory_deal"))

    print(f"  → {len(results)} PE/advisory deal items found")
    return results


def _try_rss(firm_name, rss_url, days_back, seen):
    """Try fetching a firm's RSS feed."""
    results = []
    try:
        import feedparser
        feed = feedparser.parse(rss_url)

        if feed.bozo and not feed.entries:
            return results

        cutoff = datetime.now() - timedelta(days=days_back)

        for entry in feed.entries[:10]:
            url = entry.get("link", "")
            if url in seen:
                continue
            seen.add(url)

            title = entry.get("title", "").strip()
            if not title:
                continue

            # Parse date
            pub_date = None
            for field in ("published_parsed", "updated_parsed"):
                parsed = entry.get(field)
                if parsed:
                    try:
                        pub_date = datetime(*parsed[:6])
                    except Exception:
                        pass
                    break

            if pub_date and pub_date < cutoff:
                continue

            summary = entry.get("summary", entry.get("description", ""))
            if summary:
                import re
                summary = re.sub(r"<[^>]+>", " ", summary)
                summary = re.sub(r"\s+", " ", summary).strip()[:400]

            # Categorize
            combined = f"{title} {summary}".lower()
            if any(kw in combined for kw in ["exit", "sale", "divest", "sold"]):
                category = "pe_exit"
            elif any(kw in combined for kw in ["acquir", "bought", "invest"]):
                category = "pe_acquisition"
            elif any(kw in combined for kw in ["ipo", "listing", "public"]):
                category = "pe_exit"
            else:
                category = "pe_acquisition"

            results.append({
                "source": f"{firm_name} (Press)",
                "company": _extract_deal_company(title, summary or ""),
                "title": title,
                "date": pub_date.strftime("%Y-%m-%d") if pub_date else datetime.now().strftime("%Y-%m-%d"),
                "url": url,
                "category": category,
                "content": f"{title}. {summary}" if summary else title,
            })

    except ImportError:
        print(f"  feedparser not available for {firm_name} RSS")
    except Exception as e:
        print(f"  RSS error for {firm_name}: {e}")

    return results


def _search_firm(firm_name, queries, seen, default_category):
    """Search news for a specific firm's deal activity."""
    results = []
    if not SERPAPI_KEY:
        return results

    year = get_current_year()

    for query in queries[:2]:  # Max 2 queries per firm
        try:
            full_query = f"{query} {year}"
            params = {
                "engine": "google_news", "q": full_query,
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

                combined = f"{title} {snippet}".lower()
                if "exit" in combined or "sale" in combined or "sold" in combined:
                    category = "pe_exit"
                elif "ipo" in combined:
                    category = "pe_exit"
                else:
                    category = default_category

                results.append({
                    "source": f"{firm_name} ({source_name})",
                    "company": _extract_deal_company(title, snippet),
                    "title": title,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "url": url,
                    "category": category,
                    "content": f"{title}. {snippet}",
                })

            time.sleep(0.3)

        except Exception as e:
            print(f"  PE search error for {firm_name}: {e}")

    return results


def _extract_deal_company(title, snippet):
    """Extract company name from deal announcement text."""
    combined = f"{title} {snippet}"
    known = [
        "Airbnb", "Uber", "Stripe", "SpaceX", "Databricks", "Discord",
        "Klarna", "Revolut", "Checkout.com", "Wise", "N26",
        "Grab", "GoTo", "Sea Limited", "Flipkart", "Swiggy",
        "ASML", "ARM", "Spotify", "Deliveroo", "Personio",
        "Medline", "Refinitiv", "Citrix", "Zendesk", "Worldline",
    ]
    for c in known:
        if c.lower() in combined.lower():
            return c
    return "Unknown — see article"

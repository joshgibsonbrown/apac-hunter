"""
RSS feed monitoring scraper.

Fetches and parses curated business news RSS feeds organized by region.
Filters to articles from the last N days and returns in standard format.

Requires the `feedparser` library.
"""

import time
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ICONIQ research tool)",
}

# Curated RSS feeds by region
RSS_FEEDS = {
    "apac": [
        {
            "name": "Nikkei Asia Business",
            "url": "https://asia.nikkei.com/rss/feed/nar",
        },
        {
            "name": "Business Times Singapore",
            "url": "https://www.businesstimes.com.sg/rss/companies-markets",
        },
        {
            "name": "DealStreetAsia",
            "url": "https://www.dealstreetasia.com/feed/",
        },
        {
            "name": "The Edge Singapore",
            "url": "https://www.theedgesingapore.com/rss.xml",
        },
        {
            "name": "South China Morning Post Business",
            "url": "https://www.scmp.com/rss/91/feed",
        },
    ],
    "europe": [
        {
            "name": "Reuters UK Business",
            "url": "https://feeds.reuters.com/reuters/UKBusinessNews",
        },
        {
            "name": "Financial Times Companies",
            "url": "https://www.ft.com/companies?format=rss",
        },
        {
            "name": "TechCrunch Europe",
            "url": "https://techcrunch.com/europe/feed/",
        },
    ],
    "global": [
        {
            "name": "Reuters M&A",
            "url": "https://feeds.reuters.com/reuters/mergersNews",
        },
        {
            "name": "TechCrunch Funding",
            "url": "https://techcrunch.com/category/fundraising/feed/",
        },
        {
            "name": "PitchBook News",
            "url": "https://pitchbook.com/news/feed",
        },
    ],
}


def fetch_rss_feeds(days_back=7, region_config=None):
    """
    Fetch articles from curated RSS feeds for the given region.

    Parameters
    ----------
    days_back : int
        Only include articles published in the last N days.
    region_config : dict | None
        If provided, uses region ID to select feeds. Also always
        includes global feeds.

    Returns standard scraper format list.
    """
    try:
        import feedparser
    except ImportError:
        print("  ⚠ feedparser not installed — run: pip install feedparser")
        return []

    region_id = region_config.get("id", "global") if region_config else "global"

    # Collect feeds for this region + global
    feeds_to_check = list(RSS_FEEDS.get(region_id, []))
    if region_id != "global":
        feeds_to_check.extend(RSS_FEEDS.get("global", []))

    results = []
    seen_urls = set()
    cutoff = datetime.now() - timedelta(days=days_back)

    for feed_info in feeds_to_check:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]

        try:
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                print(f"  RSS error for {feed_name}: feed unavailable")
                continue

            for entry in feed.entries[:15]:  # Cap per feed
                try:
                    url = entry.get("link", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = entry.get("title", "").strip()
                    if not title:
                        continue

                    # Parse date
                    pub_date = _parse_feed_date(entry)
                    if pub_date and pub_date < cutoff:
                        continue

                    summary = entry.get("summary", entry.get("description", ""))
                    # Strip HTML from summary
                    if summary:
                        import re
                        summary = re.sub(r"<[^>]+>", " ", summary)
                        summary = re.sub(r"\s+", " ", summary).strip()[:500]

                    results.append({
                        "source": f"RSS ({feed_name})",
                        "company": _extract_company_from_rss(title, summary),
                        "title": title,
                        "date": (
                            pub_date.strftime("%Y-%m-%d")
                            if pub_date
                            else datetime.now().strftime("%Y-%m-%d")
                        ),
                        "url": url,
                        "category": "news",
                        "content": f"{title}. {summary}" if summary else title,
                    })

                except Exception:
                    continue

            # Small delay between feeds
            time.sleep(0.5)

        except Exception as e:
            print(f"  RSS error for {feed_name}: {e}")
            continue

    print(f"  → {len(results)} RSS items fetched")
    return results


def _parse_feed_date(entry):
    """Parse the publication date from an RSS entry."""
    # feedparser provides parsed time tuples
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except Exception:
                continue

    # Fallback: try string parsing
    for field in ("published", "updated", "created"):
        date_str = entry.get(field, "")
        if date_str:
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%SZ",
                "%a, %d %b %Y %H:%M:%S GMT",
            ]:
                try:
                    return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=None)
                except ValueError:
                    continue

    return None


def _extract_company_from_rss(title, summary):
    """Best-effort company extraction from RSS content."""
    combined = f"{title} {summary}"

    known = [
        "Grab", "Sea Limited", "GoTo", "Tencent", "Alibaba", "ByteDance",
        "ASML", "Spotify", "Wise", "Revolut", "Klarna", "Adyen",
        "Stripe", "SpaceX", "OpenAI", "Databricks", "Canva",
        "DBS", "OCBC", "UOB", "HSBC", "Barclays",
        "Samsung", "Sony", "SoftBank", "Reliance",
        "Unilever", "SAP", "Siemens", "Ferrari", "LVMH",
    ]

    for company in known:
        if company.lower() in combined.lower():
            return company

    return "Unknown — see article"

"""
SEC EDGAR S-1 / F-1 IPO pipeline monitor.

Queries EDGAR full-text search for recent S-1, F-1, S-1/A, and F-1/A
filings to detect companies in the IPO pipeline before they price.
Attempts to parse lock-up periods from prospectus text.
"""

import re
import requests
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "ICONIQ Capital research@iconiqcapital.com"}

EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"

# Geographic and structural keywords that suggest relevance
GEO_KEYWORDS_APAC = [
    "singapore", "hong kong", "china", "cayman islands", "british virgin",
    "taiwan", "japan", "korea", "india", "indonesia", "malaysia",
    "thailand", "vietnam", "philippines", "australia",
]

GEO_KEYWORDS_EUROPE = [
    "united kingdom", "ireland", "netherlands", "germany", "france",
    "switzerland", "sweden", "norway", "denmark", "finland", "luxembourg",
    "jersey", "guernsey", "isle of man", "belgium", "spain", "italy",
]

STRUCTURAL_KEYWORDS = ["holdings", "group", "limited", "plc", "nv", "se"]


def fetch_ipo_pipeline(days_back=30, region_config=None):
    """
    Search EDGAR for recent S-1, F-1, S-1/A, F-1/A filings.

    Returns results in the standard scraper format with category
    'ipo_filing'. When a lock-up period is found it is included
    in the content string and as a structured field.
    """
    results = []
    cutoff = datetime.now() - timedelta(days=days_back)
    start_date = cutoff.strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")

    # Build ticker set from region config for relevance filtering
    known_tickers = set()
    known_companies = set()
    if region_config and "edgar_tickers" in region_config:
        known_tickers = set(region_config["edgar_tickers"].keys())
        known_companies = {
            v.lower() for v in region_config["edgar_tickers"].values()
        }

    form_types = ["S-1", "F-1", "S-1/A", "F-1/A"]

    for form_type in form_types:
        try:
            _fetch_form_type(
                form_type, start_date, end_date,
                known_tickers, known_companies, region_config,
                results,
            )
        except Exception as e:
            print(f"  IPO pipeline error for {form_type}: {e}")
            continue

    print(f"  → {len(results)} IPO pipeline filings found")
    return results


def _fetch_form_type(form_type, start_date, end_date,
                     known_tickers, known_companies, region_config, results):
    """Fetch a single form type from EDGAR full-text search."""
    try:
        url = (
            f"https://efts.sec.gov/LATEST/search-index"
            f"?q=%22{form_type.replace('/', '%2F')}%22"
            f"&dateRange=custom"
            f"&startdt={start_date}"
            f"&enddt={end_date}"
            f"&forms={form_type.replace('/', '%2F')}"
        )

        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code != 200:
            # Fallback: try the EDGAR full-text search API
            url = (
                f"https://efts.sec.gov/LATEST/search-index"
                f"?forms={form_type.replace('/', '%2F')}"
                f"&dateRange=custom"
                f"&startdt={start_date}"
                f"&enddt={end_date}"
            )
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                # Second fallback: EDGAR submissions search
                _fetch_form_type_via_submissions(
                    form_type, start_date, end_date,
                    known_tickers, known_companies, region_config, results
                )
                return

        data = response.json()
        hits = data.get("hits", {}).get("hits", [])

        for hit in hits[:50]:  # Cap at 50 per form type
            try:
                source_data = hit.get("_source", {})
                company_name = source_data.get("display_names", [""])[0] if source_data.get("display_names") else source_data.get("entity_name", "")
                filing_date = source_data.get("file_date", "")
                file_num = source_data.get("file_num", "")
                accession = source_data.get("accession_no", "")

                if not company_name:
                    continue

                # Relevance filter
                if not _is_relevant(company_name, known_tickers, known_companies, region_config):
                    continue

                # Build URL
                accession_clean = accession.replace("-", "") if accession else ""
                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{accession_clean}/"
                    if accession_clean
                    else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type={form_type}&dateb=&owner=include&count=40"
                )

                # Try to extract lock-up period
                lock_up_days = _try_extract_lockup(accession, accession_clean)

                content = (
                    f"{form_type} filing by {company_name}. "
                    f"Filing date: {filing_date}. "
                    f"This indicates the company is in the IPO pipeline "
                    f"{'(amendment to existing filing)' if '/A' in form_type else '(initial filing)'}."
                )
                if lock_up_days:
                    content += f" Lock-up period: {lock_up_days} days."

                results.append({
                    "source": "SEC EDGAR IPO Pipeline",
                    "company": company_name,
                    "title": f"{form_type} filing — {company_name}",
                    "date": filing_date,
                    "url": filing_url,
                    "category": "ipo_filing",
                    "content": content,
                    "lock_up_days": lock_up_days,
                    "form_type": form_type,
                })

            except Exception:
                continue

    except Exception as e:
        # Use submissions-based fallback
        _fetch_form_type_via_submissions(
            form_type, start_date, end_date,
            known_tickers, known_companies, region_config, results
        )


def _fetch_form_type_via_submissions(form_type, start_date, end_date,
                                      known_tickers, known_companies,
                                      region_config, results):
    """Fallback: search for IPO filings via the per-company submissions API
    using our known ticker list."""
    if not known_tickers:
        return

    from apac_hunter.scrapers.edgar import get_cik_for_ticker

    for ticker in list(known_tickers)[:15]:
        try:
            cik = get_cik_for_ticker(ticker)
            if not cik:
                continue

            url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            company_name = data.get("name", ticker)
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])

            for i, form in enumerate(forms):
                if form != form_type:
                    continue
                if dates[i] < start_date:
                    continue

                accession = accessions[i] if i < len(accessions) else ""
                accession_clean = accession.replace("-", "")

                lock_up_days = _try_extract_lockup(accession, accession_clean)

                content = (
                    f"{form_type} filing by {company_name} ({ticker}). "
                    f"Filing date: {dates[i]}. "
                    f"IPO pipeline {'amendment' if '/A' in form_type else 'initial filing'}."
                )
                if lock_up_days:
                    content += f" Lock-up period: {lock_up_days} days."

                results.append({
                    "source": "SEC EDGAR IPO Pipeline",
                    "company": company_name,
                    "ticker": ticker,
                    "title": f"{form_type} filing — {company_name} ({ticker})",
                    "date": dates[i],
                    "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}&dateb=&owner=include&count=10",
                    "category": "ipo_filing",
                    "content": content,
                    "lock_up_days": lock_up_days,
                    "form_type": form_type,
                })

        except Exception as e:
            print(f"  IPO submissions fallback error for {ticker}: {e}")
            continue


def _is_relevant(company_name, known_tickers, known_companies, region_config):
    """Check if a company from an IPO filing is relevant to our mandate."""
    name_lower = company_name.lower()

    # Check against known company names
    for known in known_companies:
        if known in name_lower or name_lower in known:
            return True

    # Check geographic keywords
    geo_keywords = GEO_KEYWORDS_APAC + GEO_KEYWORDS_EUROPE
    if region_config:
        rid = region_config.get("id", "")
        if rid == "apac":
            geo_keywords = GEO_KEYWORDS_APAC
        elif rid == "europe":
            geo_keywords = GEO_KEYWORDS_EUROPE

    for kw in geo_keywords:
        if kw in name_lower:
            return True

    # Check structural keywords (broad filter)
    for kw in STRUCTURAL_KEYWORDS:
        if kw in name_lower:
            return True

    return False


def _try_extract_lockup(accession, accession_clean):
    """Attempt to parse lock-up period from the prospectus text."""
    if not accession_clean:
        return None

    try:
        # Fetch the filing index to find the prospectus document
        index_url = f"https://www.sec.gov/Archives/edgar/data/{accession_clean}/{accession}-index.htm"
        resp = requests.get(index_url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return None

        # Look for lock-up mentions in the index page itself
        text = resp.text.lower()
        lock_up_days = _parse_lockup_from_text(text)
        if lock_up_days:
            return lock_up_days

    except Exception:
        pass

    return None


def _parse_lockup_from_text(text):
    """Extract lock-up period in days from prospectus text."""
    # Common patterns: "180-day lock-up", "lock-up period of 180 days",
    # "lock up period of 90 days", "180 day lock-up agreement"
    patterns = [
        r"(\d{2,3})[\s-]*day\s*lock[\s-]*up",
        r"lock[\s-]*up\s*(?:period|agreement)\s*of\s*(\d{2,3})\s*days",
        r"lock[\s-]*up\s*(?:period|agreement)\s*(?:of|for)\s*(\d{2,3})\s*days",
        r"(\d{2,3})\s*days?\s*(?:after|following)\s*(?:the|this)\s*(?:offering|ipo)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            days = int(match.group(1))
            if 30 <= days <= 365:  # Sanity check
                return days

    return None

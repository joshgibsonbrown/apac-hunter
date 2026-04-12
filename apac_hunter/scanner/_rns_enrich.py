"""
RNS enrichment — fetches PDMR/director dealing article pages from Investegate
and saves structured transaction records to the insider_transactions table.

Called after collect_filings() when RNS filings are present.
Only processes Director/PDMR Shareholding announcements that contain a
proper UK MAR notification (not AGMs, results, or other RNS categories that
slip through the keyword filter).
"""

from __future__ import annotations

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime

from apac_hunter.intelligence.insider_tracker import save_insider_transaction

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research tool)"}

# Titles that indicate a proper PDMR transaction notification
_PDMR_TITLE_KEYWORDS = [
    "director/pdmr shareholding",
    "pdmr shareholding",
    "director shareholding",
    "notification of transaction",
    "transaction in own shares",  # company buybacks — parse separately
    "director dealing",
]

# Titles that look like PDMR but aren't individual transactions
_SKIP_TITLE_KEYWORDS = [
    "result of agm",
    "agm result",
    "directorate change",
    "board change",
    "appointment",
    "resignation",
]

# Months for date parsing
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def enrich_rns_filings(rns_filings: list[dict]) -> int:
    """
    Process RNS filings that represent PDMR/director dealings.
    Fetches article content, parses structured transactions, saves to DB.

    Returns the number of transactions saved.
    """
    candidates = _filter_pdmr_candidates(rns_filings)
    if not candidates:
        return 0

    print(f"  RNS enrichment: {len(candidates)} PDMR filing(s) to process")
    saved_count = 0

    for filing in candidates:
        url = filing.get("url", "")
        if not url or "investegate.co.uk" not in url:
            continue

        try:
            text = _fetch_article_text(url)
            if not text:
                continue

            transactions = _parse_pdmr_notification(
                text=text,
                company_hint=filing.get("company", ""),
                ticker_hint=filing.get("ticker", ""),
                url=url,
            )

            for tx in transactions:
                save_insider_transaction(
                    individual_name=tx["individual_name"],
                    company=tx["company"],
                    ticker=tx["ticker"],
                    transaction_date=tx["transaction_date"],
                    transaction_code=tx["transaction_code"],
                    shares=tx["shares"],
                    price_per_share=tx["price_per_share"],
                    total_value=tx["total_value"],
                    shares_remaining=tx.get("shares_remaining", 0),
                    filing_url=url,
                    region="europe",
                )
                saved_count += 1

            if transactions:
                print(f"    ✓ {len(transactions)} tx(s) saved — {transactions[0]['individual_name']} / {transactions[0]['company']}")

            # Be polite to Investegate
            time.sleep(0.5)

        except Exception as exc:
            print(f"    ⚠ RNS enrichment error for {url}: {exc}")
            continue

    print(f"  RNS enrichment complete: {saved_count} transaction(s) saved")
    return saved_count


# ── Filtering ─────────────────────────────────────────────────────────────────

def _filter_pdmr_candidates(filings: list[dict]) -> list[dict]:
    """Keep only filings whose titles suggest PDMR/director dealing content."""
    results = []
    for f in filings:
        title_lower = f.get("title", "").lower()
        if any(kw in title_lower for kw in _SKIP_TITLE_KEYWORDS):
            continue
        if any(kw in title_lower for kw in _PDMR_TITLE_KEYWORDS):
            results.append(f)
    return results


# ── Article fetching ──────────────────────────────────────────────────────────

def _fetch_article_text(url: str) -> str:
    """Fetch an Investegate article and return the plain text body."""
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    # Remove nav, header, footer cruft
    for tag in soup(["nav", "header", "footer", "script", "style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


# ── PDMR notification parser ──────────────────────────────────────────────────

def _parse_pdmr_notification(
    text: str,
    company_hint: str = "",
    ticker_hint: str = "",
    url: str = "",
) -> list[dict]:
    """
    Parse a UK MAR PDMR notification from plain article text.

    Returns a list of transaction dicts (may be empty if not a proper MAR form).
    """
    # Must contain UK MAR structural markers to be worth parsing
    if "Details of the person discharging" not in text and "Nature of transaction" not in text:
        # Try company buyback format as fallback
        return _parse_buyback_notification(text, company_hint, ticker_hint)

    individual_name = _extract_individual_name(text)
    if not individual_name:
        return []

    company = _extract_company_name(text) or company_hint
    ticker = ticker_hint  # RNS filing already has ticker from scraper

    date_str = _extract_transaction_date(text)
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    transactions = _extract_transactions(text, individual_name, company, ticker, date_str)
    return transactions


def _extract_individual_name(text: str) -> str:
    """Extract person name from UK MAR section 1a."""
    # Pattern: "Details of the person discharging..." then "a)\nName\n{name}"
    # or simply "Name\n{name}" near the top
    patterns = [
        r"Details of the person discharging[^\n]*\n(?:[^\n]*\n){0,5}a\)\s*\nName\s*\n([^\n]+)",
        r"(?:^|\n)Name\s*\n([A-Z][^\n]{2,60})\n",
        r"Details of the person[^\n]*\n[^\n]*\n([A-Z][A-Za-z\s,.\-']+)\n",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            name = m.group(1).strip()
            # Sanity check — reject if it looks like a company name
            if len(name) > 2 and not any(x in name.lower() for x in ["plc", "ltd", "inc", "group plc"]):
                return name
    return ""


def _extract_company_name(text: str) -> str:
    """Extract issuer/company name from UK MAR section 3a."""
    patterns = [
        r"Details of the issuer[^\n]*\n(?:[^\n]*\n){0,5}a\)\s*\nName\s*\n([^\n]+)",
        # Fallback: company name appears early in text before the notification body
        r"^([A-Z][A-Za-z0-9 &,.\-']+(?:PLC|Plc|Limited|Ltd|Group|SE|NV|AG|SA))\s*\n",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def _extract_transaction_date(text: str) -> str:
    """Extract transaction date from UK MAR section 4e."""
    patterns = [
        # "Date of the transaction\n8 April 2026"
        r"Date of the transaction\s*\n([^\n]+)",
        # "Date of purchase:\n10 April 2026"
        r"Date of purchase[:\s]*\n([^\n]+)",
        # Inline: "on 8 April 2026" or "on 2026-04-08"
        r"on\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        r"on\s+(\d{4}-\d{2}-\d{2})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            parsed = _parse_date_str(raw)
            if parsed:
                return parsed
    return ""


def _extract_transactions(
    text: str,
    individual_name: str,
    company: str,
    ticker: str,
    date_str: str,
) -> list[dict]:
    """
    Extract individual transaction records from the price/volume/nature sections.
    """
    results = []

    # Strategy: find "Nature of transaction" block and scan for sale/purchase lines
    # Also look for explicit aggregated totals

    nature_block = _extract_section(text, "Nature of transaction", next_section="Price")
    price_block = _extract_section(text, r"Price\(s\).*?Volume\(s\)", next_section="Aggregated")
    agg_block = _extract_section(text, "Aggregated information", next_section="Date of the transaction")

    # Parse nature to find which sub-transactions are sales vs vests
    nature_lines = (nature_block or "").split("\n")

    # Try to build transaction list from aggregated totals (most reliable)
    agg_transactions = _parse_aggregated_section(agg_block or "")

    if agg_transactions:
        for agg in agg_transactions:
            code = _classify_transaction(agg.get("nature", ""), nature_block or "")
            results.append({
                "individual_name": individual_name,
                "company": company,
                "ticker": ticker,
                "transaction_date": date_str,
                "transaction_code": code,
                "shares": agg.get("volume", 0.0),
                "price_per_share": agg.get("price", 0.0),
                "total_value": agg.get("total", 0.0),
                "shares_remaining": 0.0,
            })
    else:
        # Fallback: scan full text for sale/purchase sentences
        fallback = _parse_fallback_transactions(text, individual_name, company, ticker, date_str)
        results.extend(fallback)

    # Filter out zero-value, zero-share records and purely vesting transactions
    results = [
        r for r in results
        if (r["shares"] > 0 or r["total_value"] > 0)
        and r["transaction_code"] != "skip"
    ]

    return results


def _parse_aggregated_section(agg_text: str) -> list[dict]:
    """
    Parse the aggregated info table from UK MAR PDMR notifications.

    Actual format (each value on its own line, same index prefix repeated):
      1.  Price
      1.  Volume
      1.  Total
      1. Nil          <- price value
      1.              <- bare prefix; volume follows on next line
      35,555          <- volume value
      1. Nil          <- total value
      2.  Price
      ...
      2. £2.633
      2.
      16,757
      2. £44,116.44
    """
    results = []
    lines = [ln.strip() for ln in agg_text.replace("\xa0", " ").split("\n") if ln.strip()]

    # Collect all (index, value) pairs, skipping header labels
    # A header label line looks like "2.  Price" or "2.  Volume" etc.
    _LABEL_WORDS = {"price", "volume", "total", "aggregated"}
    indexed: list[tuple[int, str]] = []  # (index, raw_value)
    prev_was_bare = False
    prev_index = -1

    for i, line in enumerate(lines):
        m = re.match(r"^(\d+)\.\s*(.*)", line)
        if not m:
            # Might be a volume value following a bare "N." line
            if prev_was_bare and line and not re.match(r"^\d+\.", line):
                indexed.append((prev_index, line))
            prev_was_bare = False
            continue

        idx = int(m.group(1))
        val = m.group(2).strip()

        # Skip header label lines
        if val.lower() in _LABEL_WORDS or not val:
            if not val:  # bare "N." — volume follows on next line
                prev_was_bare = True
                prev_index = idx
            else:
                prev_was_bare = False
            continue

        indexed.append((idx, val))
        prev_was_bare = False

    # Group by index: every group of 3 values = (price, volume, total)
    from collections import defaultdict
    by_index: dict[int, list[str]] = defaultdict(list)
    for idx, val in indexed:
        by_index[idx].append(val)

    for idx in sorted(by_index.keys()):
        vals = by_index[idx]
        if len(vals) < 2:
            continue
        # vals order: price, volume, total (some may be Nil)
        price = _parse_currency(vals[0]) if len(vals) > 0 else 0.0
        volume = _safe_float(vals[1]) if len(vals) > 1 else 0.0
        total = _parse_currency(vals[2]) if len(vals) > 2 else 0.0

        if not total and price and volume:
            total = price * volume

        if volume > 0 and (price > 0 or total > 0):
            results.append({"price": price, "volume": volume, "total": total, "nature": ""})

    return results


def _parse_fallback_transactions(
    text: str, individual_name: str, company: str, ticker: str, date_str: str
) -> list[dict]:
    """Simple sentence-level fallback for non-standard formats."""
    results = []

    # "Sale of 16,757 shares ... £2.633 each ... £44,116"
    sale_pat = re.compile(
        r"[Ss]ale of\s*([\d,]+)\s*shares?\s*(?:at\s*)?([\d,£€$.p]+)?(?:\s*each)?[^\n]*?([\d,£€$]+(?:\.\d+)?)\s*(?:total|in total)?",
        re.IGNORECASE,
    )
    for m in sale_pat.finditer(text):
        shares = _safe_float(m.group(1))
        price = _parse_currency(m.group(2) or "0")
        total = _parse_currency(m.group(3) or "0")
        if not total and shares and price:
            total = shares * price
        if shares > 0:
            results.append({
                "individual_name": individual_name, "company": company,
                "ticker": ticker, "transaction_date": date_str,
                "transaction_code": "S",
                "shares": shares, "price_per_share": price,
                "total_value": total, "shares_remaining": 0.0,
            })

    # "purchased N shares at P pence"
    buy_pat = re.compile(
        r"purchased\s*([\d,]+)\s*(?:ordinary\s*)?shares?\s*(?:at\s*([\d,.]+))?\s*(?:pence|p\b)?",
        re.IGNORECASE,
    )
    for m in buy_pat.finditer(text):
        shares = _safe_float(m.group(1))
        price_raw = m.group(2) or "0"
        price = _safe_float(price_raw) / 100 if price_raw else 0  # pence → £
        if shares > 0:
            results.append({
                "individual_name": individual_name, "company": company,
                "ticker": ticker, "transaction_date": date_str,
                "transaction_code": "P",
                "shares": shares, "price_per_share": price,
                "total_value": shares * price, "shares_remaining": 0.0,
            })

    return results


def _parse_buyback_notification(text: str, company: str, ticker: str) -> list[dict]:
    """
    Parse a company 'Transaction in Own Shares' (buyback) announcement.
    These don't have an individual — we record the company as the buyer.
    """
    # "Number of ordinary shares purchased: 547,996"
    shares_m = re.search(r"Number of ordinary shares purchased[:\s]*([\d,]+)", text, re.IGNORECASE)
    if not shares_m:
        return []

    shares = _safe_float(shares_m.group(1))

    # "Volume weighted average price paid per share: 821.3000"
    vwap_m = re.search(r"[Vv]olume weighted average price[^:]*[:\s]*([\d.]+)", text)
    vwap = _safe_float(vwap_m.group(1)) / 100 if vwap_m else 0  # pence → £

    # Date of purchase
    date_m = re.search(r"Date of purchase[:\s]*\n?([^\n]+)", text, re.IGNORECASE)
    date_str = ""
    if date_m:
        date_str = _parse_date_str(date_m.group(1).strip()) or ""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    total = shares * vwap if vwap else 0

    return [{
        "individual_name": company or "Company (Buyback)",
        "company": company,
        "ticker": ticker,
        "transaction_date": date_str,
        "transaction_code": "B",  # custom code for buyback
        "shares": shares,
        "price_per_share": vwap,
        "total_value": total,
        "shares_remaining": 0.0,
    }]


# ── Section extraction ────────────────────────────────────────────────────────

def _extract_section(text: str, start_marker: str, next_section: str = "") -> str | None:
    """Extract text between two section markers."""
    m = re.search(start_marker, text, re.IGNORECASE)
    if not m:
        return None
    start = m.end()
    if next_section:
        m2 = re.search(next_section, text[start:], re.IGNORECASE)
        end = start + m2.start() if m2 else start + 1000
    else:
        end = start + 1000
    return text[start:end]


# ── Classification ─────────────────────────────────────────────────────────────

def _classify_transaction(nature_hint: str, full_nature_block: str) -> str:
    """Map a transaction description to a Form 4–style code."""
    combined = (nature_hint + " " + full_nature_block).lower()
    if any(w in combined for w in ["sale", "sold", "disposal", "disposed"]):
        return "S"
    if any(w in combined for w in ["purchase", "purchased", "bought", "acquisition", "acquired"]):
        return "P"
    if any(w in combined for w in ["vest", "vesting", "award", "grant", "release"]):
        return "A"
    if any(w in combined for w in ["exercise", "option"]):
        return "M"
    if any(w in combined for w in ["tax", "withholding"]):
        return "F"
    return "X"


# ── Helpers ───────────────────────────────────────────────────────────────────

_CURRENCY_STRIP = re.compile(r"[£€$,\s]")

def _parse_currency(raw: str) -> float:
    """Parse a currency string like '£44,116.44' or '2.633' or 'Nil' → float."""
    if not raw or raw.strip().lower() in ("nil", "n/a", "-", ""):
        return 0.0
    # Handle pence: trailing 'p' without decimal means pence
    raw = raw.strip()
    is_pence = raw.endswith("p") and "." not in raw
    cleaned = _CURRENCY_STRIP.sub("", raw).rstrip("p")
    try:
        val = float(cleaned)
        return val / 100 if is_pence else val
    except (ValueError, TypeError):
        return 0.0


def _safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("£", "").replace("€", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_date_str(raw: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    raw = raw.strip()
    # ISO
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    # "8 April 2026" or "8 Apr 2026"
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if m:
        month = _MONTHS.get(m.group(2).lower()[:3])
        if month:
            return f"{m.group(3)}-{month:02d}-{int(m.group(1)):02d}"
    # "10/04/2026"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return ""

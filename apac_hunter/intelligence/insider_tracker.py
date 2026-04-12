"""
Insider selling pattern analysis.

Persists Form 4 transaction data to Supabase and provides analytics:
- Selling acceleration detection (compare recent velocity to baseline)
- Cumulative sales tracking with threshold alerts
- 10b5-1 plan detection from filing footnotes
- SC 13D/G ownership change tracking

Degrades gracefully if the table does not yet exist.
"""

import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

_supabase = None


def _get_supabase():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        _supabase = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        )
    return _supabase


# ---------------------------------------------------------------------------
# Persistence — insider transactions
# ---------------------------------------------------------------------------

def save_insider_transaction(
    individual_name, company, ticker, transaction_date, transaction_code,
    shares, price_per_share, total_value, shares_remaining,
    filing_url="", region="apac",
):
    """Save a single insider transaction row."""
    try:
        sb = _get_supabase()
        tx_date = transaction_date or datetime.now().strftime("%Y-%m-%d")
        tv = _safe_float(total_value)

        # Idempotency check — skip if identical record already exists
        existing = (
            sb.table("insider_transactions")
            .select("id")
            .ilike("individual_name", individual_name or "")
            .eq("transaction_date", tx_date)
            .eq("total_value", tv)
            .limit(1)
            .execute()
        )
        if existing.data:
            return  # already saved

        record = {
            "individual_name": individual_name or "",
            "company": company or "",
            "ticker": ticker or "",
            "transaction_date": tx_date,
            "transaction_code": transaction_code or "",
            "shares": _safe_float(shares),
            "price_per_share": _safe_float(price_per_share),
            "total_value": tv,
            "shares_remaining": _safe_float(shares_remaining),
            "filing_url": filing_url or "",
            "region": region or "apac",
        }
        sb.table("insider_transactions").insert(record).execute()
    except Exception as e:
        err_msg = str(e)
        if "insider_transactions" in err_msg and ("schema cache" in err_msg or "relation" in err_msg):
            print(f"    ⚠ insider_transactions table not found — run SCHEMA_MIGRATIONS.md SQL. Skipping.")
        else:
            print(f"    ⚠ Insider transaction save error: {e}")


def save_form4_transactions(filing_content, company, ticker, filing_url, region):
    """
    Parse a Form 4 content string (as produced by edgar.py's
    parse_form4_xml) and save each transaction individually.

    Returns a list of saved transaction dicts for downstream analysis.
    """
    saved = []

    if not filing_content or "Form 4" not in filing_content:
        return saved

    # Extract reporting owner — format: "Reporting owner: John Smith."
    owner_match = re.search(r"Reporting owner:\s*(.+?)\.\s", filing_content)
    owner = owner_match.group(1).strip() if owner_match else ""

    if not owner:
        return saved

    # --- Primary parser ---
    # Match lines like:
    #   "Open market sale: 50000.0000 shares at $25.50/share $1,275,000 total value on 2026-04-01. Shares owned after transaction: 500000.0000 (Direct ownership)."
    #   "Tax withholding: 1234 shares on 2026-04-01."
    tx_pattern = re.compile(
        r"([A-Za-z][A-Za-z /]+?):\s*"           # 1: type (e.g. "Open market sale")
        r"([\d,.]+)\s*shares?\s*"                 # 2: shares (handles decimals)
        r"(?:at\s*\$?([\d,.]+)/share\s*)?"        # 3: price per share (optional)
        r"(?:\$?([\d,.]+)\s*total value\s*)?"      # 4: total value (optional)
        r"on\s*([\d-]+)\."                         # 5: date
        r"(?:\s*Shares owned after transaction:\s*([\d,.]+))?"  # 6: remaining (optional)
    )

    for m in tx_pattern.finditer(filing_content):
        tx_type_str = m.group(1).strip()
        shares_str = m.group(2)
        price_str = m.group(3) or ""
        total_str = m.group(4) or ""
        date_str = m.group(5)
        remaining_str = m.group(6) or ""

        # Skip if this matched a non-transaction line
        if tx_type_str.lower() in ("form 4", "reporting owner", "issuer"):
            continue

        code = _description_to_code(tx_type_str)
        shares = _safe_float(shares_str)
        price = _safe_float(price_str)
        total = _safe_float(total_str)
        remaining = _safe_float(remaining_str)

        if not total and shares and price:
            total = shares * price

        save_insider_transaction(
            individual_name=owner,
            company=company,
            ticker=ticker,
            transaction_date=date_str,
            transaction_code=code,
            shares=shares,
            price_per_share=price,
            total_value=total,
            shares_remaining=remaining,
            filing_url=filing_url,
            region=region,
        )

        saved.append({
            "individual_name": owner,
            "company": company,
            "ticker": ticker,
            "transaction_date": date_str,
            "transaction_code": code,
            "shares": shares,
            "price_per_share": price,
            "total_value": total,
            "shares_remaining": remaining,
        })

    # --- Fallback lenient parser ---
    # If primary parser found nothing but content has transaction keywords
    if not saved and owner and _has_transaction_keywords(filing_content):
        print(f"    ℹ Primary parser found 0 txns for {owner} — trying lenient parser")
        saved = _lenient_parse(filing_content, owner, company, ticker, filing_url, region)

    if saved:
        print(f"    ✓ {len(saved)} insider transaction(s) parsed for {owner}")

    return saved


def _has_transaction_keywords(content):
    """Check if content likely contains transaction data."""
    keywords = ["shares", "sale", "purchase", "exercise", "grant", "disposition"]
    content_lower = content.lower()
    return any(kw in content_lower for kw in keywords)


def _lenient_parse(content, owner, company, ticker, filing_url, region):
    """Fallback parser that handles more content variations."""
    saved = []

    # Try to find any line with shares + date pattern
    # Matches: "anything: NUMBER shares ... on YYYY-MM-DD"
    lenient_pattern = re.compile(
        r"([^:\n]+?):\s*([\d,.]+)\s*shares?.*?on\s*(\d{4}-\d{2}-\d{2})",
        re.IGNORECASE,
    )

    for m in lenient_pattern.finditer(content):
        tx_type_str = m.group(1).strip()
        shares_str = m.group(2)
        date_str = m.group(3)

        if tx_type_str.lower() in ("form 4", "reporting owner", "issuer"):
            continue

        code = _description_to_code(tx_type_str)
        shares = _safe_float(shares_str)

        # Try to extract price from surrounding text
        price = 0.0
        price_match = re.search(r"\$?([\d,.]+)/share", m.group(0))
        if price_match:
            price = _safe_float(price_match.group(1))

        total = 0.0
        total_match = re.search(r"\$?([\d,.]+)\s*total value", m.group(0))
        if total_match:
            total = _safe_float(total_match.group(1))

        if not total and shares and price:
            total = shares * price

        save_insider_transaction(
            individual_name=owner,
            company=company,
            ticker=ticker,
            transaction_date=date_str,
            transaction_code=code,
            shares=shares,
            price_per_share=price,
            total_value=total,
            shares_remaining=0.0,
            filing_url=filing_url,
            region=region,
        )

        saved.append({
            "individual_name": owner,
            "company": company,
            "ticker": ticker,
            "transaction_date": date_str,
            "transaction_code": code,
            "shares": shares,
            "price_per_share": price,
            "total_value": total,
            "shares_remaining": 0.0,
        })

    return saved


# ---------------------------------------------------------------------------
# Persistence — ownership changes (SC 13D/G)
# ---------------------------------------------------------------------------

def save_ownership_change(
    individual_name, company, ticker, filing_type, filing_date,
    ownership_pct, previous_pct, change_direction,
    filing_url="", region="apac",
):
    """Save an ownership change from SC 13D/G filings."""
    try:
        sb = _get_supabase()
        record = {
            "individual_name": individual_name or "",
            "company": company or "",
            "ticker": ticker or "",
            "filing_type": filing_type or "",
            "filing_date": filing_date or "",
            "ownership_pct": _safe_float(ownership_pct),
            "previous_pct": _safe_float(previous_pct),
            "change_direction": change_direction or "unknown",
            "filing_url": filing_url or "",
            "region": region or "apac",
        }
        sb.table("ownership_changes").insert(record).execute()
    except Exception as e:
        err_msg = str(e)
        if "ownership_changes" in err_msg and ("schema cache" in err_msg or "relation" in err_msg):
            print(f"    ⚠ ownership_changes table not found — run SCHEMA_MIGRATIONS.md SQL. Skipping.")
        else:
            print(f"    ⚠ Ownership change save error: {e}")


def parse_ownership_pct(filing_content):
    """
    Extract ownership percentage from SC 13D/G filing content.
    Returns (pct: float, holder_name: str) or (None, None).
    """
    if not filing_content:
        return None, None

    # Common patterns in 13D/G filings
    pct_patterns = [
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of|of the)\s*(?:outstanding|common|class)",
        r"percent(?:age)?\s*(?:of\s*class)?[:\s]*(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:beneficially owned|of shares)",
        r"aggregate\s*(?:percentage|amount)[:\s]*(\d{1,3}(?:\.\d+)?)\s*%",
    ]

    pct = None
    for pattern in pct_patterns:
        match = re.search(pattern, filing_content, re.IGNORECASE)
        if match:
            try:
                pct = float(match.group(1))
                if 0 < pct <= 100:
                    break
                pct = None
            except (ValueError, IndexError):
                continue

    # Try to extract holder name
    holder = None
    holder_patterns = [
        r"(?:filed by|reporting person)[:\s]*([A-Z][A-Za-z\s,.]+?)(?:\.|$|\n)",
        r"(?:name of reporting)[:\s]*([A-Z][A-Za-z\s,.]+?)(?:\.|$|\n)",
    ]
    for pattern in holder_patterns:
        match = re.search(pattern, filing_content, re.IGNORECASE)
        if match:
            holder = match.group(1).strip()
            break

    return pct, holder


def get_recent_insider_transactions(days=30, limit=20):
    """Return recent insider transactions for dashboard display, deduplicated."""
    try:
        sb = _get_supabase()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        # Fetch more than needed so dedup doesn't shrink below limit
        result = (
            sb.table("insider_transactions")
            .select("*")
            .gte("transaction_date", cutoff)
            .order("total_value", desc=True)
            .limit(limit * 5)
            .execute()
        )
        rows = result.data or []

        # Deduplicate by (individual_name, transaction_date, total_value)
        seen: set = set()
        deduped: list = []
        for row in rows:
            key = (
                row.get("individual_name", "").lower(),
                row.get("transaction_date", ""),
                row.get("total_value", 0),
            )
            if key not in seen:
                seen.add(key)
                deduped.append(row)
            if len(deduped) >= limit:
                break

        return deduped
    except Exception:
        return []


def get_insider_transaction_count(days=30):
    """Return count of insider transactions in the given window."""
    try:
        sb = _get_supabase()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        result = (
            sb.table("insider_transactions")
            .select("id", count="exact")
            .gte("transaction_date", cutoff)
            .execute()
        )
        return result.count or 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def detect_selling_acceleration(individual_name, days_window=90):
    """
    Compare recent selling velocity to historical baseline.

    Returns a dict with:
    - acceleration_factor: float (e.g. 5.0 = selling 5x faster than baseline)
    - recent_total: float ($ sold in recent window)
    - baseline_rate: float ($/day historical average)
    """
    try:
        sb = _get_supabase()
        now = datetime.now()
        window_start = (now - timedelta(days=days_window)).strftime("%Y-%m-%d")
        history_start = (now - timedelta(days=365)).strftime("%Y-%m-%d")

        all_sales = (
            sb.table("insider_transactions")
            .select("transaction_date, total_value, transaction_code")
            .eq("individual_name", individual_name)
            .eq("transaction_code", "S")
            .gte("transaction_date", history_start)
            .execute()
        )

        if not all_sales.data:
            return {"acceleration_factor": 0.0, "recent_total": 0.0, "baseline_rate": 0.0}

        recent_total = 0.0
        older_total = 0.0

        for row in all_sales.data:
            val = _safe_float(row.get("total_value", 0))
            tx_date = row.get("transaction_date", "")
            if tx_date >= window_start:
                recent_total += val
            else:
                older_total += val

        total_history_days = 365 - days_window
        baseline_rate = older_total / max(total_history_days, 1)
        recent_rate = recent_total / max(days_window, 1)

        if baseline_rate <= 0:
            acceleration = 0.0 if recent_total == 0 else 999.0
        else:
            acceleration = recent_rate / baseline_rate

        return {
            "acceleration_factor": round(acceleration, 2),
            "recent_total": recent_total,
            "baseline_rate": round(baseline_rate, 2),
        }

    except Exception as e:
        err_msg = str(e)
        if "insider_transactions" in err_msg and ("schema cache" in err_msg or "relation" in err_msg):
            pass
        else:
            print(f"    ⚠ Acceleration detection error: {e}")
        return {"acceleration_factor": 0.0, "recent_total": 0.0, "baseline_rate": 0.0}


def get_cumulative_sales(individual_name, days=365):
    """Return total $ value of open-market sales in the given window."""
    try:
        sb = _get_supabase()
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        result = (
            sb.table("insider_transactions")
            .select("total_value")
            .eq("individual_name", individual_name)
            .eq("transaction_code", "S")
            .gte("transaction_date", cutoff)
            .execute()
        )

        if not result.data:
            return 0.0

        return sum(_safe_float(r.get("total_value", 0)) for r in result.data)

    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 10b5-1 plan detection
# ---------------------------------------------------------------------------

def detect_10b5_1_plan(filing_content):
    """
    Search Form 4 filing content (including footnotes) for references
    to Rule 10b5-1 trading plans.

    Returns (is_10b5_1: bool, matched_text: str).
    """
    if not filing_content:
        return False, ""

    patterns = [
        r"10b5[\s-]*1",
        r"rule\s*10b[\s-]*5[\s-]*1",
        r"pre[\s-]*arranged\s*trading\s*plan",
        r"trading\s*plan\s*(?:adopted|established|entered)",
        r"automatic\s*(?:stock|share)\s*(?:sale|selling|disposition)\s*plan",
    ]

    for pattern in patterns:
        match = re.search(pattern, filing_content, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 100)
            end = min(len(filing_content), match.end() + 100)
            context = filing_content[start:end].strip()
            return True, context

    return False, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(val):
    """Convert a string or number to float, returning 0.0 on failure."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _description_to_code(desc):
    """Map a transaction description back to its Form 4 code letter."""
    desc_lower = desc.lower().strip()
    mapping = {
        "open market sale": "S",
        "open market purchase": "P",
        "grant": "A",
        "award": "A",
        "disposition to issuer": "D",
        "tax withholding": "F",
        "gift": "G",
        "option exercise": "M",
        "conversion": "C",
        "will": "W",
        "inheritance": "W",
    }
    for key, code in mapping.items():
        if key in desc_lower:
            return code
    return "X"

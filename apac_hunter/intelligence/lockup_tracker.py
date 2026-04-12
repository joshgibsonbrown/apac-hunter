"""
Lock-up expiry calendar tracker.

Maintains a Supabase table of IPO lock-up expiry dates and provides
helpers to save new lock-ups and query upcoming expiries. Degrades
gracefully if the table does not yet exist.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

_supabase = None


def _get_supabase():
    """Lazy-init Supabase client."""
    global _supabase
    if _supabase is None:
        from supabase import create_client
        _supabase = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
        )
    return _supabase


def save_lockup(company, ticker, ipo_date, lockup_days, region, source_url=""):
    """
    Save or update a lock-up calendar entry.

    Parameters
    ----------
    company : str
    ticker : str
    ipo_date : str   – "YYYY-MM-DD"
    lockup_days : int
    region : str     – region ID
    source_url : str
    """
    try:
        sb = _get_supabase()
        ipo_dt = datetime.strptime(ipo_date[:10], "%Y-%m-%d")
        expiry_dt = ipo_dt + timedelta(days=lockup_days)
        today = datetime.now()
        status = "upcoming" if expiry_dt > today else "expired"

        record = {
            "company": company,
            "ticker": ticker or "",
            "ipo_date": ipo_date[:10],
            "lockup_days": lockup_days,
            "lockup_expiry_date": expiry_dt.strftime("%Y-%m-%d"),
            "region": region,
            "source_url": source_url,
            "status": status,
        }

        # Upsert: update if same company+ticker exists
        existing = (
            sb.table("lockup_calendar")
            .select("id")
            .eq("company", company)
            .eq("ticker", ticker or "")
            .execute()
        )
        if existing.data:
            sb.table("lockup_calendar").update(record).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            sb.table("lockup_calendar").insert(record).execute()

        print(f"    ✓ Lock-up saved: {company} expires {expiry_dt.strftime('%Y-%m-%d')}")

    except Exception as e:
        err_msg = str(e)
        if "lockup_calendar" in err_msg and ("schema cache" in err_msg or "relation" in err_msg):
            print(f"    ⚠ lockup_calendar table not found — run SCHEMA_MIGRATIONS.md SQL. Skipping lock-up save.")
        else:
            print(f"    ⚠ Lock-up save error: {e}")


def get_upcoming_lockups(days_ahead=30):
    """
    Return lock-ups expiring within *days_ahead* days.

    Returns a list of dicts or an empty list if the table doesn't exist.
    """
    try:
        sb = _get_supabase()
        today = datetime.now().strftime("%Y-%m-%d")
        future = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        result = (
            sb.table("lockup_calendar")
            .select("*")
            .gte("lockup_expiry_date", today)
            .lte("lockup_expiry_date", future)
            .order("lockup_expiry_date", desc=False)
            .execute()
        )
        return result.data or []

    except Exception as e:
        err_msg = str(e)
        if "lockup_calendar" in err_msg and ("schema cache" in err_msg or "relation" in err_msg):
            print("  ⚠ lockup_calendar table not found — run SCHEMA_MIGRATIONS.md SQL")
        else:
            print(f"  ⚠ Lock-up query error: {e}")
        return []


def get_all_lockups():
    """Return all lock-up entries, sorted by expiry date."""
    try:
        sb = _get_supabase()
        result = (
            sb.table("lockup_calendar")
            .select("*")
            .order("lockup_expiry_date", desc=False)
            .execute()
        )
        return result.data or []
    except Exception:
        return []

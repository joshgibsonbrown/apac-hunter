from __future__ import annotations
import logging
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


# ── Individuals ───────────────────────────────────────────────────────────────

def get_or_create_individual(name, company=None, country=None):
    result = supabase.table("individuals").select("*").ilike("name", name).execute()
    if result.data:
        return result.data[0]
    new = supabase.table("individuals").insert({
        "name": name, "company": company, "country": country
    }).execute()
    return new.data[0]


# ── Trigger events ────────────────────────────────────────────────────────────

def save_trigger_event(event: dict):
    return supabase.table("trigger_events").insert(event).execute()


# ── Briefs ────────────────────────────────────────────────────────────────────

def save_brief(brief: dict):
    brief.pop("updated_at", None)

    existing = supabase.table("briefs").select("id").eq(
        "individual_name", brief["individual_name"]
    ).execute()

    if existing.data:
        brief_id = existing.data[0]["id"]
        return supabase.table("briefs").update(brief).eq("id", brief_id).execute()

    return supabase.table("briefs").insert(brief).execute()


def get_all_briefs():
    return supabase.table("briefs").select("*").order("updated_at", desc=True).execute().data


def get_brief_by_id(brief_id):
    return supabase.table("briefs").select("*").eq("id", brief_id).execute().data


def get_recent_events(limit=50):
    return (
        supabase.table("trigger_events")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )


WORKFLOW_STATUSES = ("New", "Triage", "Priority", "Monitor", "Handoff", "Discarded")


def get_briefs(
    region_id: str | None = None,
    status_filter: str | None = None,
    trigger_filter: str | None = None,
    sort_by: str = "newest",
) -> list:
    """
    Return briefs with optional region, workflow_status, and trigger_type filters.

    sort_by: "newest" (default) | "status"
    """
    try:
        q = supabase.table("briefs").select("*")
        if region_id:
            q = q.eq("region", region_id)
        if status_filter and status_filter in WORKFLOW_STATUSES:
            q = q.eq("workflow_status", status_filter)
        if trigger_filter:
            q = q.eq("last_trigger_type", trigger_filter)
        if sort_by == "status":
            q = q.order("workflow_status").order("updated_at", desc=True)
        else:
            q = q.order("updated_at", desc=True)
        return q.execute().data
    except Exception:
        return get_all_briefs()


def find_recent_brief(individual_name: str, trigger_type: str, days: int = 14) -> dict | None:
    """
    Return an existing brief for the same individual + trigger type within
    the given window. Used for lightweight duplicate suppression.
    """
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    try:
        result = (
            supabase.table("briefs")
            .select("id, individual_name, last_trigger_type, updated_at")
            .ilike("individual_name", individual_name)
            .eq("last_trigger_type", trigger_type)
            .gte("updated_at", cutoff)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        log.warning("Duplicate brief check failed: %s", exc)
        return None


def get_briefs_by_region(region_id):
    """Return briefs filtered by region. Falls back gracefully if column missing."""
    try:
        return (
            supabase.table("briefs")
            .select("*")
            .eq("region", region_id)
            .order("updated_at", desc=True)
            .execute()
            .data
        )
    except Exception:
        return get_all_briefs()


def update_brief_status(brief_id: str, status: str) -> bool:
    """Update the workflow_status of a brief. Returns True on success."""
    if status not in WORKFLOW_STATUSES:
        return False
    try:
        supabase.table("briefs").update({"workflow_status": status}).eq("id", brief_id).execute()
        return True
    except Exception as exc:
        log.warning("Failed to update brief status %s: %s", brief_id, exc)
        return False


# ── Scan jobs ─────────────────────────────────────────────────────────────────

def save_scan_job(params: dict) -> str | None:
    """Create a new scan job record. Returns the new job ID or None on error."""
    try:
        result = supabase.table("scan_jobs").insert({
            "status": "pending",
            "progress": 0,
            "params": params,
        }).execute()
        return result.data[0]["id"]
    except Exception as exc:
        log.error("Failed to create scan job: %s", exc)
        return None


def update_scan_job(job_id: str, fields: dict) -> None:
    """Merge fields into an existing scan job row. Silently logs on failure."""
    try:
        supabase.table("scan_jobs").update(fields).eq("id", job_id).execute()
    except Exception as exc:
        log.warning("Failed to update scan job %s: %s", job_id, exc)


def get_scan_job(job_id: str) -> dict | None:
    """Return a single scan job by ID, or None."""
    try:
        result = supabase.table("scan_jobs").select("*").eq("id", job_id).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        log.warning("Failed to fetch scan job %s: %s", job_id, exc)
        return None


def get_latest_scan_job() -> dict | None:
    """Return the most recently created scan job, or None."""
    try:
        result = (
            supabase.table("scan_jobs")
            .select("*")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as exc:
        log.warning("Failed to fetch latest scan job: %s", exc)
        return None

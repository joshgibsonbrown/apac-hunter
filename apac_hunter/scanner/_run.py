from __future__ import annotations
"""
Scan orchestration — coordinates source fetching, enrichment, classification,
and brief generation. Exposes run_scan() and get_last_scan_stats().
"""
import logging
from collections.abc import Callable
from datetime import datetime

from apac_hunter.regions import get_region_config
from apac_hunter.intelligence.classifier import classify_batch
from apac_hunter.intelligence.brief_generator import generate_brief
from apac_hunter.intelligence.normaliser import normalise_name
from apac_hunter.intelligence.researcher import research_individual
from apac_hunter.intelligence.pre_filter import pre_filter
from apac_hunter.database import save_trigger_event, save_brief, get_or_create_individual, find_recent_brief
from apac_hunter.scanner._sources import collect_filings
from apac_hunter.scanner._edgar import enrich_edgar_filings
from apac_hunter.scanner._rns_enrich import enrich_rns_filings

log = logging.getLogger(__name__)

# Sources included in Quick Scan mode
QUICK_SOURCES = {
    "sgx", "edgar", "news", "ipo_pipeline",
    "companies_house", "euronext", "rns",
}

CLASSIFY_BATCH_SIZE = 8

ProgressCallback = Callable[[int, str], None]


def _noop_progress(progress: int, status: str) -> None:
    pass


def run_scan(
    days_back: int = 7,
    sources: list | None = None,
    regions: list | None = None,
    scan_mode: str = "quick",
    progress_callback: ProgressCallback = _noop_progress,
) -> list:
    """
    Run a full intelligence scan.

    Args:
        days_back: How many days of history to fetch.
        sources: Optional explicit source filter (overrides region defaults).
        regions: Region IDs to scan (default: ["apac"]).
        scan_mode: "quick" (core sources, ~5 min) or "deep" (all sources, ~15 min).
        progress_callback: Called with (progress_pct, status_message) at key milestones.

    Returns:
        List of generated brief dicts.
    """
    if regions is None:
        regions = ["apac"]

    active_configs = []
    for rid in regions:
        try:
            active_configs.append(get_region_config(rid))
        except KeyError as exc:
            print(f"  ⚠ {exc} — skipping")

    if not active_configs:
        print("No valid regions selected.")
        return []

    # Build merged source list across regions, then apply mode/manual filters
    merged_sources: list = []
    seen: set = set()
    for cfg in active_configs:
        for src in cfg["sources"]:
            if src not in seen:
                seen.add(src)
                merged_sources.append(src)

    if sources is not None:
        merged_sources = [s for s in merged_sources if s in sources]
    if scan_mode == "quick":
        merged_sources = [s for s in merged_sources if s in QUICK_SOURCES]

    region_labels = ", ".join(c["label"] for c in active_configs)
    mode_label = "QUICK" if scan_mode == "quick" else "DEEP"

    print(f"\n{'='*50}")
    print(f"APAC HUNTER — {mode_label} SCAN")
    print(f"Regions: {region_labels}")
    print(f"Sources: {len(merged_sources)} active")
    print(f"Looking back: {days_back} days")
    print(f"{'='*50}\n")

    progress_callback(5, f"Starting {scan_mode} scan — fetching sources...")

    # ── Fetch raw filings ──────────────────────────────────────────────────────
    all_filings, filing_region_map, edgar_filings, ipo_filings = collect_filings(
        active_configs, merged_sources, days_back
    )

    # ── RNS enrichment (UK PDMR / director dealings → insider_transactions) ──
    rns_filings = [f for f in all_filings if f.get("source") == "RNS"]
    if rns_filings:
        print(f"Enriching {len(rns_filings)} RNS filing(s) for insider transactions...")
        enrich_rns_filings(rns_filings)

    # ── EDGAR enrichment (insider tracking, lock-up calendar) ─────────────────
    if edgar_filings or ipo_filings:
        enrich_edgar_filings(
            edgar_filings=edgar_filings,
            ipo_filings=ipo_filings,
            active_configs=active_configs,
            all_filings=all_filings,
            filing_region_map=filing_region_map,
        )

    # ── Deduplicate by title ───────────────────────────────────────────────────
    seen_titles: set = set()
    deduped: list = []
    for f in all_filings:
        title = f.get("title", "").strip().lower()[:80]
        company = f.get("company", "").strip().lower()[:40]
        key = f"{title}|{company}"
        if title and key not in seen_titles:
            seen_titles.add(key)
            deduped.append(f)
    all_filings = deduped
    total_fetched = len(all_filings)

    print(f"\nTotal unique items fetched: {total_fetched}")
    progress_callback(35, f"Fetched {total_fetched} items — pre-filtering...")

    # ── Pre-filter ─────────────────────────────────────────────────────────────
    all_filings = pre_filter(all_filings)
    items_after_filter = len(all_filings)

    # ── Batch classify ─────────────────────────────────────────────────────────
    triggers_found: list = []
    print(f"\nClassifying {len(all_filings)} items in batches of {CLASSIFY_BATCH_SIZE}...")
    progress_callback(40, f"Classifying {items_after_filter} items...")

    # Group filings into batches, keeping region consistent within each batch
    batches: list = []
    current_batch: list = []
    current_region: str | None = None

    for filing in all_filings:
        region_cfg = filing_region_map.get(id(filing))
        region_id = region_cfg["id"] if region_cfg else "apac"

        if current_region != region_id and current_batch:
            batches.append((current_batch, current_region))
            current_batch = []

        current_batch.append(filing)
        current_region = region_id

        if len(current_batch) >= CLASSIFY_BATCH_SIZE:
            batches.append((current_batch, current_region))
            current_batch = []

    if current_batch:
        batches.append((current_batch, current_region))

    for batch_num, (batch_filings, region_id) in enumerate(batches, start=1):
        print(f"  Batch {batch_num}/{len(batches)} ({len(batch_filings)} items, {region_id.upper()})...")
        progress_callback(
            min(40 + int(batch_num / max(len(batches), 1) * 15), 55),
            f"Classifying batch {batch_num}/{len(batches)}...",
        )

        try:
            region_cfg = get_region_config(region_id)
        except KeyError:
            region_cfg = active_configs[0] if active_configs else None

        results = classify_batch(batch_filings, region_config=region_cfg)

        region_countries_lower = [c.lower() for c in (region_cfg or {}).get("countries", [])]

        for result in results:
            if not result:
                continue
            raw_name = result.get("individual_name", "")
            clean_name = normalise_name(raw_name)
            if not clean_name:
                print(f"    — Skipping: name unclear ('{raw_name}')")
                continue

            # Geography validation — reject if classifier placed the individual
            # in a country that doesn't belong to the active region
            result_country = (result.get("country") or "").lower().strip()
            if result_country and region_countries_lower:
                in_region = any(
                    result_country in c or c in result_country
                    for c in region_countries_lower
                )
                if not in_region:
                    print(f"    — Skipping geography mismatch: {clean_name} "
                          f"({result.get('country')}) not in {region_id.upper()} region")
                    continue

            result["individual_name"] = clean_name
            result["region"] = region_id
            print(f"    ✓ TRIGGER: {result.get('trigger_type')} — {clean_name} [{region_id.upper()}]")
            triggers_found.append(result)

    print(f"\nTriggers found: {len(triggers_found)}")
    progress_callback(55, f"Triggers found: {len(triggers_found)} — generating briefs...")

    if not triggers_found:
        print("No qualifying trigger events detected in this scan.")
        _update_scan_stats(scan_mode, total_fetched, items_after_filter, 0, 0)
        return []

    # ── Generate briefs ────────────────────────────────────────────────────────
    briefs_generated: list = []
    print("\nGenerating briefs...")

    for i, trigger in enumerate(triggers_found, start=1):
        name = trigger.get("individual_name", "").strip()
        company = trigger.get("company")
        print(f"\n  Processing: {name} ({company}) [{trigger.get('region', '').upper()}]")

        progress_callback(
            min(55 + int(i / max(len(triggers_found), 1) * 40), 95),
            f"Generating brief {i}/{len(triggers_found)}: {name}...",
        )

        # Lightweight duplicate suppression — skip if a brief for the same
        # person + trigger type was generated within the last 14 days.
        existing = find_recent_brief(name, trigger.get("trigger_type", ""), days=14)
        if existing:
            print(f"    ↩ Skipping duplicate: {name} / {trigger.get('trigger_type')} "
                  f"— brief already exists from {existing.get('updated_at', '')[:10]}")
            continue

        individual = get_or_create_individual(
            name=name, company=company, country=trigger.get("country")
        )

        event_record = {
            "individual_id": individual["id"],
            "individual_name": name,
            "company": company,
            "trigger_type": trigger.get("trigger_type"),
            "tier": trigger.get("tier"),
            "source": trigger.get("source"),
            "source_url": trigger.get("source_url"),
            "event_date": trigger.get("event_date") or None,
            "headline": trigger.get("headline"),
            "raw_content": trigger.get("raw_content", "")[:2000],
            "significance": trigger.get("significance"),
            "urgency_score": trigger.get("urgency_score"),
            "wealth_score": trigger.get("wealth_score"),
            "confidence": trigger.get("confidence"),
            "region": trigger.get("region"),
        }
        save_trigger_event(event_record)
        print(f"    ✓ Trigger event saved")

        print(f"    Running deep research...")
        research = research_individual(
            name=name, company=company,
            trigger_type=trigger.get("trigger_type", ""),
            country=trigger.get("country"),
        )
        print(f"    Generating strategic brief...")
        brief = generate_brief(trigger, research)

        if brief:
            brief["individual_id"] = individual["id"]
            brief["region"] = trigger.get("region")
            save_brief(brief)
            briefs_generated.append(brief)
            print(f"    ✓ Brief saved for {name}")

    print(f"\n{'='*50}")
    print(f"SCAN COMPLETE")
    print(f"Triggers detected: {len(triggers_found)}")
    print(f"Briefs generated: {len(briefs_generated)}")
    print(f"{'='*50}\n")

    _update_scan_stats(scan_mode, total_fetched, items_after_filter,
                       len(triggers_found), len(briefs_generated))

    return briefs_generated


# ── Scan stats ────────────────────────────────────────────────────────────────
# Kept as a module-level fallback for when the DB scan_jobs table is not yet
# provisioned. The app layer prefers get_latest_scan_job() from database.py.

_last_scan_stats: dict = {}


def _update_scan_stats(mode, fetched, filtered, triggers, briefs) -> None:
    global _last_scan_stats
    _last_scan_stats = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": mode,
        "items_fetched": fetched,
        "items_after_filter": filtered,
        "triggers_found": triggers,
        "briefs_generated": briefs,
    }


def get_last_scan_stats() -> dict:
    """
    Return stats from the most recent scan. Prefers the DB-backed scan_jobs
    table; falls back to module-level in-memory stats if the table is absent.
    """
    try:
        from apac_hunter.database import get_latest_scan_job
        job = get_latest_scan_job()
        if job and job.get("status") in ("complete", "failed"):
            params = job.get("params") or {}
            return {
                "timestamp": (job.get("finished_at") or job.get("created_at") or "")[:16].replace("T", " "),
                "mode": params.get("scan_mode", "unknown"),
                "items_fetched": job.get("items_fetched", "—"),
                "items_after_filter": job.get("items_after_filter", "—"),
                "triggers_found": job.get("triggers_found", "—"),
                "briefs_generated": job.get("briefs_generated", "—"),
            }
    except Exception:
        pass
    return _last_scan_stats

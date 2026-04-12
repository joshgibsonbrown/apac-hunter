from __future__ import annotations
"""
EDGAR enrichment layer — processes Form 4 (insider transactions) and
SC 13D/G (ownership changes) filings, and seeds the lock-up calendar.

Mutates all_filings (appending synthetic trigger items) and filing_region_map
in place, so callers see the enriched results.
"""
# Must match the days_window default in detect_selling_acceleration()
_SELLING_WINDOW_DAYS = 90
from apac_hunter.regions import get_region_config
from apac_hunter.intelligence.lockup_tracker import save_lockup, get_upcoming_lockups
from apac_hunter.intelligence.insider_tracker import (
    save_form4_transactions, detect_selling_acceleration,
    get_cumulative_sales, detect_10b5_1_plan,
    save_ownership_change, parse_ownership_pct,
)


def enrich_edgar_filings(
    edgar_filings: list,
    ipo_filings: list,
    active_configs: list,
    all_filings: list,
    filing_region_map: dict,
) -> None:
    """
    Process EDGAR Form 4 and SC 13D/G filings:
      - Detect accelerated insider selling and cumulative $50M+ sales.
      - Track ownership changes.
      - Seed lock-up calendar from IPO filings.
      - Append synthetic trigger items for significant patterns.

    Modifies all_filings and filing_region_map in place.
    """
    print("Analyzing insider selling patterns...")
    for f in edgar_filings:
        rcfg = _region_for_ticker(f.get("ticker", ""), active_configs)
        region_id = rcfg["id"] if rcfg else "apac"

        if f.get("category") == "4":
            content = f.get("content", "")
            is_10b5_1, plan_text = detect_10b5_1_plan(content)
            if is_10b5_1:
                f["content"] = content + f"\n\n[10b5-1 PLAN DETECTED]: {plan_text}"

            saved_txns = save_form4_transactions(
                filing_content=content,
                company=f.get("company", ""),
                ticker=f.get("ticker", ""),
                filing_url=f.get("url", ""),
                region=region_id,
            )
            for txn in saved_txns:
                name = txn.get("individual_name", "")
                if not name or txn.get("transaction_code") != "S":
                    continue

                accel = detect_selling_acceleration(name)
                factor = accel.get("acceleration_factor", 0.0)
                recent_total = accel.get("recent_total", 0.0)
                baseline_rate = accel.get("baseline_rate", 0.0)

                if factor > 3.0:
                    if baseline_rate <= 0:
                        # Sentinel 999: no prior selling history — use neutral language,
                        # never include a meaningless multiplier in the brief.
                        title = f"First-time significant insider selling — {name}"
                        content = (
                            f"FIRST-TIME SELLING DETECTED: {name} has no prior "
                            f"open-market selling history on record at this company. "
                            f"Recent sales total: ${recent_total:,.0f} over the last "
                            f"{_SELLING_WINDOW_DAYS} days. "
                            f"No historical baseline available — rate comparison not applicable."
                        )
                    else:
                        recent_rate = recent_total / max(_SELLING_WINDOW_DAYS, 1)
                        history_days = 365 - _SELLING_WINDOW_DAYS
                        title = f"Accelerated insider selling — {name}"
                        content = (
                            f"ACCELERATED SELLING: {name} at {factor:.1f}x baseline rate. "
                            f"Recent selling rate: ${recent_rate:,.0f}/day over the last "
                            f"{_SELLING_WINDOW_DAYS} days (total: ${recent_total:,.0f}). "
                            f"Historical baseline rate: ${baseline_rate:,.0f}/day "
                            f"(prior {history_days} days of data). "
                            f"Calculation: {factor:.1f}x = "
                            f"${recent_rate:,.0f}/day ÷ ${baseline_rate:,.0f}/day."
                        )
                    syn = _synthetic(
                        "Insider Pattern Analysis", f.get("company", ""),
                        title,
                        txn.get("transaction_date", ""), f.get("url", ""),
                        "insider_pattern",
                        content,
                    )
                    filing_region_map[id(syn)] = rcfg
                    all_filings.append(syn)

                cumulative = get_cumulative_sales(name, days=365)
                if cumulative >= 50_000_000:
                    syn = _synthetic(
                        "Insider Pattern Analysis", f.get("company", ""),
                        f"$50M+ cumulative sales — {name}",
                        txn.get("transaction_date", ""), f.get("url", ""),
                        "insider_pattern",
                        f"CUMULATIVE: {name} sold ${cumulative:,.0f} in 365 days.",
                    )
                    filing_region_map[id(syn)] = rcfg
                    all_filings.append(syn)

        elif f.get("category") in ("SC 13D/A", "SC 13G/A", "SC 13D", "SC 13G"):
            content = f.get("content", "")
            pct, holder = parse_ownership_pct(content)
            if pct is not None:
                is_amendment = "/A" in f.get("category", "")
                save_ownership_change(
                    individual_name=holder or "",
                    company=f.get("company", ""),
                    ticker=f.get("ticker", ""),
                    filing_type=f.get("category", ""),
                    filing_date=f.get("date", ""),
                    ownership_pct=pct,
                    previous_pct=0,
                    change_direction="decreased" if is_amendment else "new",
                    filing_url=f.get("url", ""),
                    region=region_id,
                )

    # Seed lock-up calendar from IPO filings
    print("Checking upcoming lock-up expiries...")
    for f in ipo_filings:
        rcfg = _region_for_ticker(f.get("ticker", ""), active_configs) or active_configs[0]
        lock_up_days = f.get("lock_up_days")
        if lock_up_days:
            save_lockup(
                company=f.get("company", ""),
                ticker=f.get("ticker", ""),
                ipo_date=f.get("date", ""),
                lockup_days=lock_up_days,
                region=rcfg["id"] if rcfg else "apac",
                source_url=f.get("url", ""),
            )

    for lockup in get_upcoming_lockups(days_ahead=14):
        syn = _synthetic(
            "Lock-Up Expiry Calendar", lockup.get("company", ""),
            f"Lock-up expiry — {lockup.get('company', '')}",
            lockup.get("lockup_expiry_date", ""), lockup.get("source_url", ""),
            "lockup_expiry",
            f"LOCK-UP EXPIRY: {lockup.get('company', '')} on {lockup.get('lockup_expiry_date', '')}.",
        )
        try:
            rcfg = get_region_config(lockup.get("region", "apac"))
        except KeyError:
            rcfg = active_configs[0]
        filing_region_map[id(syn)] = rcfg
        all_filings.append(syn)


def _region_for_ticker(ticker: str, configs: list) -> dict | None:
    for cfg in configs:
        if ticker in cfg.get("edgar_tickers", {}):
            return cfg
    return configs[0] if configs else None


def _synthetic(source, company, title, date, url, category, content) -> dict:
    return {
        "source": source, "company": company, "title": title,
        "date": date, "url": url, "category": category, "content": content,
    }

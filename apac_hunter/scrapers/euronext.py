"""
European exchange regulatory disclosure scraper.

Sources:
  1. ESMA Transparency Register — pan-European major holdings notifications
     (Article 9 of the Transparency Directive, publicly searchable)
  2. Euronext live feed — attempted opportunistically; gracefully skipped if
     the internal AJAX endpoints are unavailable (they require a browser session)

Note: The Euronext live.euronext.com AJAX endpoints used in the original
implementation require a live browser session and return HTTP 4xx for plain
HTTP clients. ESMA's public register is the authoritative free alternative.
"""

from __future__ import annotations

import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research tool)",
    "Accept": "text/html,application/xhtml+xml,*/*",
}

# ESMA transparency register — major holdings notifications
# Publicly accessible, no auth required, returns HTML table
ESMA_URL = "https://registers.esma.europa.eu/publication/searchRegister"

# Euronext live endpoints — kept for opportunistic use only
_EURONEXT_DISCLOSURE_URL = "https://live.euronext.com/en/ajax/getHolderDisclosureListContent"
_EURONEXT_INSIDER_URL = "https://live.euronext.com/en/ajax/getInsiderTradingContent"


def fetch_euronext(days_back: int = 14) -> list[dict]:
    """
    Fetch recent European regulatory disclosures.

    Tries ESMA first (reliable), then attempts Euronext live endpoints
    opportunistically. Always returns a clean list; never raises.
    """
    results: list[dict] = []
    cutoff = datetime.now() - timedelta(days=days_back)

    results.extend(_fetch_esma_major_holdings(cutoff))
    results.extend(_try_euronext_live(cutoff))

    print(f"  → {len(results)} European regulatory items found")
    return results


# ── ESMA transparency register ────────────────────────────────────────────────

def _fetch_esma_major_holdings(cutoff: datetime) -> list[dict]:
    """
    Query the ESMA transparency register for recent major holdings notifications.
    Endpoint: https://registers.esma.europa.eu/publication/searchRegister?core=esma_registers_sh_noti
    Returns results as JSON (Solr-based API).
    """
    results: list[dict] = []
    try:
        cutoff_str = cutoff.strftime("%Y-%m-%dT00:00:00Z")
        params = {
            "core": "esma_registers_sh_noti",
            "fq": f"notifDate:[{cutoff_str} TO NOW]",
            "rows": 200,
            "sort": "notifDate desc",
            "wt": "json",
        }
        resp = requests.get(ESMA_URL, params=params, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  ESMA register returned {resp.status_code}")
            return []

        data = resp.json()
        docs = (data.get("response") or {}).get("docs", [])

        for doc in docs:
            date_raw = doc.get("notifDate", "")
            date_str = date_raw[:10].replace("T", " ") if date_raw else ""
            issuer = doc.get("issuerName", doc.get("issuer", "Unknown"))
            notifier = doc.get("notifyingPerson", doc.get("holder", ""))
            threshold = doc.get("positionAcquired", doc.get("percentage", ""))
            doc_url = doc.get("docUrl", "https://registers.esma.europa.eu")

            title = (
                f"Major holdings notification: {notifier} in {issuer}"
                if notifier else
                f"Major holdings notification: {issuer}"
            )
            content = (
                f"ESMA MAJOR HOLDINGS NOTIFICATION: {notifier or 'Undisclosed holder'} "
                f"has reported a major holding in {issuer}."
                + (f" Position: {threshold}." if threshold else "")
                + f" Date: {date_str}."
            )

            results.append({
                "source": "ESMA",
                "company": issuer,
                "title": title,
                "date": date_str,
                "url": doc_url,
                "category": "major_shareholder",
                "content": content,
            })

    except Exception as exc:
        print(f"  ESMA register error: {exc}")

    return results


# ── Euronext live (opportunistic) ─────────────────────────────────────────────

def _try_euronext_live(cutoff: datetime) -> list[dict]:
    """
    Attempt the Euronext AJAX endpoints. These require a live browser session,
    so failures are expected and silently skipped.
    """
    results: list[dict] = []

    for url, label in [
        (_EURONEXT_DISCLOSURE_URL, "major_shareholder"),
        (_EURONEXT_INSIDER_URL, "insider_transaction"),
    ]:
        try:
            resp = requests.get(url, params={"page": 0, "itemsPerPage": 50},
                                headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            items = data if isinstance(data, list) else data.get("data", data.get("items", []))
            for item in items:
                date_raw = item.get("date", item.get("notificationDate", item.get("transactionDate", "")))
                if date_raw:
                    try:
                        item_date = datetime.strptime(date_raw[:10], "%Y-%m-%d")
                        if item_date < cutoff:
                            continue
                    except ValueError:
                        pass
                company = item.get("company", item.get("issuerName", item.get("issuer", "Unknown")))
                person = item.get("holder", item.get("notifyingPerson", item.get("person", "")))
                title = f"Euronext {label.replace('_', ' ')}: {person} — {company}" if person else f"Euronext {label.replace('_', ' ')}: {company}"
                results.append({
                    "source": "Euronext",
                    "company": company,
                    "title": title,
                    "date": date_raw[:10] if date_raw else "",
                    "url": "https://live.euronext.com/en/products/equities",
                    "category": label,
                    "content": f"Euronext {label}: {title}. Date: {date_raw[:10] if date_raw else 'unknown'}.",
                })
        except Exception:
            continue

    return results

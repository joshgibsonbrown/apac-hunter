"""
UK Companies House scraper.

Uses the Companies House REST API to find recently filed PSC (Persons of
Significant Control) changes, director changes, and new incorporations whose
names suggest family office or wealth structuring activity.

Requires the COMPANIES_HOUSE_API_KEY environment variable. Returns an empty
list gracefully if the key is not configured.
"""

import os
import requests
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")
BASE_URL = "https://api.company-information.service.gov.uk"

# Keywords that suggest family office / wealth structuring entities
FAMILY_OFFICE_KEYWORDS = [
    "family office",
    "family investment",
    "family holdings",
    "family capital",
    "family assets",
    "family wealth",
    "family fund",
    "private office",
    "private trust",
    "private wealth",
    "private capital",
    "wealth management",
    "single family",
    "family partners",
]


def fetch_companies_house(days_back=30):
    """
    Search Companies House for recently incorporated entities with names
    suggesting family office or wealth structuring, plus recent PSC and
    officer changes at those entities.

    Returns a list of dicts matching the standard scraper schema.
    """
    if not API_KEY:
        print("  Companies House API key not set — skipping")
        return []

    results = []
    seen_numbers = set()
    cutoff = datetime.now() - timedelta(days=days_back)
    cutoff_str = cutoff.strftime("%Y-%m-%d")

    auth = (API_KEY, "")  # CH API uses HTTP Basic with key as username

    for keyword in FAMILY_OFFICE_KEYWORDS:
        try:
            time.sleep(0.6)  # Respect 600 req/5 min rate limit

            # --- 1. Search for companies by name ---
            params = {
                "q": keyword,
                "items_per_page": 20,
            }
            resp = requests.get(
                f"{BASE_URL}/search/companies",
                params=params,
                auth=auth,
                timeout=15,
            )

            if resp.status_code == 429:
                print("  Companies House rate limited — waiting 30s")
                time.sleep(30)
                resp = requests.get(
                    f"{BASE_URL}/search/companies",
                    params=params,
                    auth=auth,
                    timeout=15,
                )

            if resp.status_code != 200:
                print(f"  CH search error ({resp.status_code}) for '{keyword}'")
                continue

            data = resp.json()
            items = data.get("items", [])

            for company in items:
                number = company.get("company_number", "")
                if number in seen_numbers:
                    continue

                name = company.get("title", "")
                status = company.get("company_status", "")
                created = company.get("date_of_creation", "")
                address = company.get("registered_office_address", {})
                address_str = ", ".join(
                    filter(None, [
                        address.get("address_line_1", ""),
                        address.get("locality", ""),
                        address.get("postal_code", ""),
                    ])
                )

                # Only include recently created entities or active ones
                if created and created >= cutoff_str:
                    seen_numbers.add(number)
                    results.append({
                        "source": "Companies House",
                        "company": name,
                        "title": f"New UK entity incorporation: {name}",
                        "date": created,
                        "url": f"https://find-and-update.company-information.service.gov.uk/company/{number}",
                        "category": "entity_formation",
                        "content": (
                            f"New UK entity registered with Companies House: '{name}'. "
                            f"Company number: {number}. Status: {status}. "
                            f"Date of creation: {created}. "
                            f"Address: {address_str}. "
                            f"Entity name suggests potential family office or "
                            f"private wealth structuring activity."
                        ),
                    })

                # --- 2. Check for recent PSC changes ---
                _fetch_psc_changes(number, name, auth, cutoff_str, results, seen_numbers)

        except Exception as e:
            print(f"  Companies House error for '{keyword}': {e}")
            continue

    print(f"  → {len(results)} Companies House items found")
    return results


def _fetch_psc_changes(company_number, company_name, auth, cutoff_str, results, seen_numbers):
    """Fetch PSC (Persons of Significant Control) for a company."""
    try:
        time.sleep(0.6)
        resp = requests.get(
            f"{BASE_URL}/company/{company_number}/persons-with-significant-control",
            auth=auth,
            timeout=10,
        )
        if resp.status_code != 200:
            return

        data = resp.json()
        for psc in data.get("items", []):
            notified = psc.get("notified_on", "")
            if notified and notified >= cutoff_str:
                psc_name = psc.get("name", "Unknown")
                natures = ", ".join(psc.get("natures_of_control", []))
                key = f"psc-{company_number}-{psc_name}"
                if key in seen_numbers:
                    continue
                seen_numbers.add(key)

                results.append({
                    "source": "Companies House",
                    "company": company_name,
                    "title": f"PSC change: {psc_name} at {company_name}",
                    "date": notified,
                    "url": (
                        f"https://find-and-update.company-information.service.gov.uk"
                        f"/company/{company_number}/persons-with-significant-control"
                    ),
                    "category": "psc_change",
                    "content": (
                        f"Person of Significant Control change at {company_name} "
                        f"(company number {company_number}). PSC: {psc_name}. "
                        f"Natures of control: {natures}. Notified on: {notified}."
                    ),
                })
    except Exception:
        pass

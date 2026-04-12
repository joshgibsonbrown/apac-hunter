import requests
import time
from datetime import datetime, timedelta

# data.gov.sg new API endpoint (2024+)
DATAGOV_API = "https://data.gov.sg/api/action/datastore_search"
UEN_DATASET_ID = "d_3f960c10fed6145404ca7b821f263b87"

# Keywords suggesting family office / wealth structuring
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
]

def fetch_acra_formations(days_back=30):
    """
    Search ACRA registry for recently registered entities with
    names suggesting family office or wealth structuring activity.
    Uses data.gov.sg public API — no auth required.
    """
    results = []
    seen_uens = set()
    cutoff = datetime.now() - timedelta(days=days_back)

    print(f"  Searching ACRA for entity formations since {cutoff.strftime('%Y-%m-%d')}...")

    for keyword in FAMILY_OFFICE_KEYWORDS:
        try:
            time.sleep(2)  # Respect rate limits

            params = {
                "resource_id": UEN_DATASET_ID,
                "q": keyword,
                "limit": 100,
                "filters": '{"uen_status_desc": "Registered"}'
            }

            response = requests.get(DATAGOV_API, params=params, timeout=15)

            if response.status_code == 429:
                print(f"  Rate limited — waiting 60s...")
                time.sleep(60)
                response = requests.get(DATAGOV_API, params=params, timeout=15)

            if response.status_code != 200:
                continue

            data = response.json()
            records = data.get("result", {}).get("records", [])

            for record in records:
                uen = record.get("uen", "")
                if uen in seen_uens:
                    continue

                entity_name = record.get("entity_name", "")
                uen_issue_date = record.get("uen_issue_date", "")
                entity_type = record.get("entity_type_desc", "")
                status = record.get("uen_status_desc", "")
                street = record.get("reg_street_name", "")

                # Filter to recently registered only
                if uen_issue_date:
                    try:
                        reg_date = datetime.strptime(uen_issue_date[:10], "%Y-%m-%d")
                        if reg_date < cutoff:
                            continue
                    except:
                        continue
                else:
                    continue

                seen_uens.add(uen)

                results.append({
                    "source": "ACRA",
                    "company": entity_name,
                    "title": f"New entity registration: {entity_name}",
                    "date": uen_issue_date[:10],
                    "url": "https://www.bizfile.gov.sg",
                    "category": "entity_formation",
                    "content": (
                        f"New Singapore entity registered with ACRA: '{entity_name}'. "
                        f"Entity type: {entity_type}. "
                        f"UEN: {uen}. "
                        f"Registration date: {uen_issue_date[:10]}. "
                        f"Address: {street}, Singapore. "
                        f"Status: {status}. "
                        f"Entity name suggests potential family office or private wealth structuring activity."
                    )
                })

        except Exception as e:
            print(f"  ACRA error for '{keyword}': {e}")
            continue

    print(f"  → {len(results)} ACRA formations found")
    return results

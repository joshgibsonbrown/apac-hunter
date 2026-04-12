import requests
import re
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; research tool)",
    "Accept": "application/json"
}

# Announcement categories relevant to wealth trigger detection
RELEVANT_CATEGORIES = [
    "Change in Substantial Shareholder's Interest",
    "Change in Director's Interest",
    "General Announcement",
    "Circular to Shareholders",
    "Notice of Extraordinary General Meeting",
    "Notice of Annual General Meeting",
    "Acquisition",
    "Disposal",
    "Interested Person Transactions",
    "Change - Change in Shareholder Structure",
    "Offer",
    "Scheme",
]

def fetch_sgx_announcements(days_back=7):
    """Fetch real SGX announcements via the official API."""
    results = []
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # SGX API uses format: YYYYMMDD_HHMMSS
    period_start = start_date.strftime("%Y%m%d") + "_000000"
    period_end = end_date.strftime("%Y%m%d") + "_235959"
    
    # Fetch in batches of 100
    page = 1
    per_page = 100
    
    while True:
        try:
            url = (
                f"https://api.sgx.com/announcements/v1.0?"
                f"periodstart={period_start}"
                f"&periodend={period_end}"
                f"&category=all"
                f"&page={page}"
                f"&perpage={per_page}"
                f"&orderby=datetime"
                f"&orderbydir=desc"
            )
            
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            if response.status_code != 200:
                print(f"  SGX API error: {response.status_code}")
                break
            
            # SGX prepends {}&& to JSON responses
            text = response.text
            if text.startswith("{}&&"):
                text = text[4:]
            
            data = response.json() if not text.startswith("{}") else __import__('json').loads(text)
            
            announcements = data.get("items", [])
            
            if not announcements:
                break
            
            for ann in announcements:
                category = ann.get("category", "")
                title = ann.get("headline", "") or ann.get("title", "")
                company = ann.get("issuerOrSecurityName", "") or ann.get("companyName", "")
                date_str = ann.get("announcementDate", "") or ann.get("date", "")
                ann_id = ann.get("id", "") or ann.get("announcementId", "")
                
                # Only include relevant categories
                if not is_relevant_category(category, title):
                    continue
                
                # Build URL to full announcement
                if ann_id:
                    doc_url = f"https://www.sgx.com/securities/company-announcements/{ann_id}"
                else:
                    doc_url = "https://www.sgx.com/securities/company-announcements"
                
                results.append({
                    "source": "SGX",
                    "company": company,
                    "title": title,
                    "date": date_str[:10] if date_str else "",
                    "url": doc_url,
                    "category": category,
                    "content": f"{title}. Company: {company}. Category: {category}. Date: {date_str[:10] if date_str else ''}."
                })
            
            # If fewer results than per_page, we've hit the end
            if len(announcements) < per_page:
                break
                
            page += 1
            
            # Safety cap — don't fetch more than 500 announcements
            if page > 5:
                break
                
        except Exception as e:
            print(f"  SGX fetch error: {e}")
            break
    
    print(f"  → {len(results)} relevant SGX items fetched")
    return results if results else get_sgx_fallback()


def is_relevant_category(category: str, title: str) -> bool:
    """Filter to only announcements relevant to wealth trigger detection."""
    combined = f"{category} {title}".lower()
    
    relevant_keywords = [
        "substantial shareholder",
        "director's interest",
        "change in interest",
        "acquisition",
        "disposal",
        "takeover",
        "scheme of arrangement",
        "voluntary offer",
        "egm",
        "extraordinary general meeting",
        "voting rights",
        "share buyback",
        "block sale",
        "placement",
        "family office",
        "holding company",
        "restructur",
        "major transaction",
        "very substantial",
        "interested person",
        "connected transaction",
        "ipo",
        "listing",
        "privatisation",
        "dividend",
        "special distribution",
    ]
    
    for keyword in relevant_keywords:
        if keyword in combined:
            return True
    
    return False


def get_sgx_fallback():
    """Return empty list if SGX API unavailable — no more fake sample data."""
    print("  SGX API unavailable — no fallback data used")
    return []

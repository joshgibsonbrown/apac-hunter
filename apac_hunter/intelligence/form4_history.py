import requests
import re
import time
from datetime import datetime

HEADERS = {"User-Agent": "ICONIQ Capital research@iconiqcapital.com"}

KNOWN_CIKS = {
    "SE": "1703399",
    "GRAB": "1800227",
    "BIDU": "1094819",
    "JD": "1549802",
    "PDD": "1810806",
    "FUTU": "1768012",
    "BILI": "1726445",
    "NIO": "1706946",
}

NAME_ALIASES = {
    "forrest li": ["li xiaodong", "forrest li"],
    "anthony tan": ["tan anthony", "anthony tan"],
    "ming maa": ["maa ming", "ming maa", "maa ming-hokng"],
    "hooi ling tan": ["tan hooi ling", "hooi ling tan"],
    "korawad chearavanont": ["chearavanont korawad", "korawad chearavanont"],
}

def name_matches(owner_name: str, target_name: str) -> bool:
    """Check if owner name matches target using aliases."""
    owner_lower = owner_name.lower().strip()
    target_lower = target_name.lower().strip()
    
    # Direct match
    if target_lower in owner_lower or owner_lower in target_lower:
        return True
    
    # Check aliases
    aliases = NAME_ALIASES.get(target_lower, [])
    for alias in aliases:
        if alias in owner_lower or owner_lower in alias:
            return True
    
    # Check any word in target appears in owner (for partial matches)
    target_words = [w for w in target_lower.split() if len(w) > 3]
    if target_words and all(w in owner_lower for w in target_words):
        return True
        
    return False


def get_company_cik(ticker: str) -> str | None:
    if ticker and ticker in KNOWN_CIKS:
        return KNOWN_CIKS[ticker]
    try:
        r = requests.get(
            f"https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK={ticker}&type=20-F&dateb=&owner=include&count=1&search_text=&action=getcompany&output=atom",
            headers=HEADERS, timeout=10
        )
        if r.status_code == 200:
            match = re.search(r'CIK=(\d+)', r.text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None


def fetch_form4_history(individual_name: str, company: str, ticker: str = None) -> dict:
    print(f"      Fetching filing history for {individual_name} at {company}...")

    result = {
        "individual": individual_name,
        "company": company,
        "ticker": ticker,
        "transactions": [],
        "ownership_history": [],
        "summary": {},
        "source": "SEC EDGAR",
        "error": None
    }

    cik = get_company_cik(ticker) if ticker else None
    if not cik:
        result["error"] = "CIK not found"
        return result

    try:
        r = requests.get(
            f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json",
            headers=HEADERS, timeout=10
        )
        if r.status_code != 200:
            result["error"] = f"EDGAR API returned {r.status_code}"
            return result

        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        primary_docs = filings.get("primaryDocument", [])

    except Exception as e:
        result["error"] = str(e)
        return result

    # Fetch Form 4s
    form4_transactions = []
    form4_indices = [i for i, f in enumerate(forms) if f == "4"]
    print(f"      Found {len(form4_indices)} Form 4 filings, checking for {individual_name}...")

    for idx in form4_indices[:20]:
        try:
            time.sleep(0.3)
            acc_clean = accessions[idx].replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/ownership.xml"
            r = requests.get(doc_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            parsed = parse_form4_xml(r.text, dates[idx], individual_name)
            form4_transactions.extend(parsed)
        except Exception:
            continue

    result["transactions"] = form4_transactions

    # Extract ownership from 20-Fs
    ownership_history = []
    f20_indices = [i for i, f in enumerate(forms) if f == "20-F"]
    print(f"      Found {len(f20_indices)} 20-F filings...")

    for idx in f20_indices[:6]:
        try:
            time.sleep(0.5)
            acc_clean = accessions[idx].replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_clean}/{primary_docs[idx]}"
            r = requests.get(doc_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            ownership = extract_ownership_from_20f(r.text, individual_name, dates[idx])
            if ownership:
                ownership_history.append(ownership)
        except Exception:
            continue

    result["ownership_history"] = ownership_history
    result["summary"] = summarise_all_data(form4_transactions, ownership_history, individual_name)
    return result


def parse_form4_xml(xml_content: str, filing_date: str, target_name: str) -> list:
    transactions = []
    try:
        owner_match = re.search(r'<rptOwnerName>(.*?)</rptOwnerName>', xml_content, re.IGNORECASE)
        owner = owner_match.group(1).strip() if owner_match else ""

        if not name_matches(owner, target_name):
            return []

        issuer_match = re.search(r'<issuerName>(.*?)</issuerName>', xml_content, re.IGNORECASE)
        issuer = issuer_match.group(1).strip() if issuer_match else ""

        title_match = re.search(r'<officerTitle>(.*?)</officerTitle>', xml_content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        non_deriv = re.findall(
            r'<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>',
            xml_content, re.DOTALL | re.IGNORECASE
        )

        code_map = {
            'S': 'Open market sale',
            'P': 'Open market purchase',
            'A': 'Award/grant',
            'D': 'Disposition',
            'F': 'Tax withholding',
            'G': 'Gift',
            'M': 'Option exercise',
            'X': 'Option exercise (from Class B)',
        }

        for t in non_deriv:
            try:
                date = extract_xml_value(t, 'transactionDate')
                shares = extract_xml_value(t, 'transactionShares')
                price = extract_xml_value(t, 'transactionPricePerShare')
                code = extract_xml_value(t, 'transactionCode')
                shares_after = extract_xml_value(t, 'sharesOwnedFollowingTransaction')
                acquired = extract_xml_value(t, 'transactionAcquiredDisposedCode')
                security = extract_xml_value(t, 'securityTitle')

                transaction_type = code_map.get(code, f"Code {code}")

                total_value = "N/A"
                if shares and price:
                    try:
                        tv = float(shares.replace(',', '')) * float(price.replace(',', ''))
                        total_value = f"${tv:,.0f}"
                    except:
                        pass

                transactions.append({
                    "filing_date": filing_date,
                    "transaction_date": date or filing_date,
                    "owner": owner,
                    "title": title,
                    "issuer": issuer,
                    "security": security,
                    "type": transaction_type,
                    "code": code,
                    "acquired_disposed": acquired,
                    "shares": shares,
                    "price_per_share": f"${price}" if price else "N/A",
                    "total_value": total_value,
                    "shares_after": shares_after,
                })
            except Exception:
                continue

    except Exception:
        pass

    return transactions


def extract_ownership_from_20f(html_content: str, target_name: str, filing_date: str) -> dict | None:
    try:
        text = re.sub(r'<[^>]+>', ' ', html_content)
        text = re.sub(r'\s+', ' ', text)

        name_parts = target_name.split()
        search_names = [target_name] + NAME_ALIASES.get(target_name.lower(), [])

        pct_matches = []
        share_matches = []

        for search_name in search_names:
            last = search_name.split()[-1]
            pct = re.findall(
                rf'{re.escape(last)}[^.{{}}]{{0,200}}?(\d+\.?\d*)\s*%',
                text, re.IGNORECASE
            )
            shares = re.findall(
                rf'{re.escape(last)}[^.{{}}]{{0,200}}?(\d[\d,]+)\s*(?:ordinary shares|Class [AB])',
                text, re.IGNORECASE
            )
            pct_matches.extend(pct[:2])
            share_matches.extend(shares[:2])

        if pct_matches or share_matches:
            return {
                "filing_date": filing_date,
                "filing_type": "20-F",
                "individual": target_name,
                "ownership_percentages": list(set(pct_matches))[:3],
                "share_counts": list(set(share_matches))[:3],
                "note": f"Extracted from 20-F filed {filing_date}"
            }
    except Exception:
        pass
    return None


def extract_xml_value(xml: str, tag: str) -> str:
    pattern = rf'<{tag}>\s*<value>(.*?)</value>'
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    pattern = rf'<{tag}>(.*?)</{tag}>'
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def summarise_all_data(transactions: list, ownership_history: list, name: str) -> dict:
    sales = [t for t in transactions if t.get("code") == "S"]
    exercises = [t for t in transactions if t.get("code") in ["M", "X"]]

    total_proceeds = 0
    for s in sales:
        try:
            val = s.get("total_value", "").replace("$", "").replace(",", "")
            total_proceeds += float(val)
        except:
            pass

    dates = sorted([t.get("transaction_date", "") for t in transactions if t.get("transaction_date")])
    sale_dates = sorted([s.get("transaction_date", "") for s in sales if s.get("transaction_date")])

    return {
        "total_form4_transactions": len(transactions),
        "total_sales": len(sales),
        "total_option_exercises": len(exercises),
        "total_proceeds_usd": f"${total_proceeds:,.0f}",
        "first_transaction": dates[0] if dates else "None on record",
        "most_recent_transaction": dates[-1] if dates else "None on record",
        "first_sale": sale_dates[0] if sale_dates else "No open market sales on record",
        "sale_dates": sale_dates,
        "ownership_history_periods": len(ownership_history),
        "selling_cadence": classify_cadence(sale_dates),
        "data_richness": "Rich" if len(transactions) > 5 else "Thin" if transactions else "None"
    }


def classify_cadence(sale_dates: list) -> str:
    if len(sale_dates) < 2:
        return "Insufficient data — fewer than 2 open market sales on record"
    try:
        parsed = [datetime.strptime(d[:10], "%Y-%m-%d") for d in sale_dates if d]
        parsed.sort()
        gaps = [(parsed[i+1] - parsed[i]).days for i in range(len(parsed)-1)]
        avg_gap = sum(gaps) / len(gaps)
        if avg_gap < 45:
            return "High frequency — roughly monthly"
        elif avg_gap < 120:
            return "Regular — every 1-4 months"
        elif avg_gap < 365:
            return "Periodic — a few times per year"
        else:
            return "Infrequent — less than once per year"
    except:
        return "Unable to calculate"

import requests
import re
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "ICONIQ Capital research@iconiqcapital.com"}


def fetch_edgar_filings(days_back=7, region_config=None):
    """Fetch SEC EDGAR filings for insider transactions.

    If *region_config* is provided its ``edgar_tickers`` dict is used;
    otherwise we fall back to the legacy hardcoded APAC list for
    backwards compatibility.
    """
    if region_config is not None:
        companies = region_config["edgar_tickers"]
    else:
        # Legacy fallback
        companies = {
            "GRAB": "Grab Holdings Limited",
            "SE": "Sea Limited",
            "BEKE": "KE Holdings",
            "JD": "JD.com",
            "PDD": "PDD Holdings",
            "BIDU": "Baidu",
            "NIO": "NIO Inc",
            "XPEV": "XPeng",
            "LI": "Li Auto",
            "TME": "Tencent Music",
            "BILI": "Bilibili",
            "FUTU": "Futu Holdings",
            "KC": "Kingsoft Cloud",
        }

    results = []
    cutoff = datetime.now() - timedelta(days=days_back)
    form_types = ["4", "SC 13D", "SC 13G", "SC 13D/A", "SC 13G/A"]

    for ticker, company_name in list(companies.items())[:10]:
        try:
            cik = get_cik_for_ticker(ticker)
            if not cik:
                continue

            url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code != 200:
                continue

            data = response.json()
            filings = data.get("filings", {}).get("recent", {})

            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])
            primary_docs = filings.get("primaryDocument", [])

            for i, form in enumerate(forms):
                if form not in form_types:
                    continue
                try:
                    filing_date = datetime.strptime(dates[i], "%Y-%m-%d")
                    if filing_date < cutoff:
                        continue

                    accession_clean = accessions[i].replace("-", "")
                    accession_fmt = accessions[i]

                    content = fetch_filing_content(
                        cik, accession_clean, accession_fmt, primary_docs[i], form
                    )

                    results.append({
                        "source": "SEC EDGAR",
                        "company": company_name,
                        "ticker": ticker,
                        "title": f"{form} filing - {company_name} ({ticker})",
                        "date": dates[i],
                        "url": (
                            f"https://www.sec.gov/cgi-bin/browse-edgar?"
                            f"action=getcompany&CIK={cik}&type={form}"
                            f"&dateb=&owner=include&count=10"
                        ),
                        "category": form,
                        "content": content,
                    })
                except Exception:
                    continue

        except Exception as e:
            print(f"EDGAR error for {ticker}: {e}")
            continue

    return results


# ---------------------------------------------------------------------------
# Filing content helpers (unchanged)
# ---------------------------------------------------------------------------

def fetch_filing_content(cik, accession_clean, accession_fmt, primary_doc, form_type):
    """Fetch and parse the actual text content of an SEC filing."""
    try:
        # If primary doc is XSL-transformed (e.g. xslF345X06/ownership.xml),
        # fetch the raw XML instead for proper parsing
        actual_doc = primary_doc
        if primary_doc.startswith('xsl') and '/' in primary_doc:
            actual_doc = primary_doc.split('/')[-1]  # e.g. ownership.xml

        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{accession_clean}/{actual_doc}"
        )
        response = requests.get(doc_url, headers=HEADERS, timeout=10)

        if response.status_code == 200:
            content = response.text
            if form_type == "4" and (
                "<XML>" in content or "<?xml" in content.lower()
            ):
                return parse_form4_xml(content)
            clean = re.sub(r"<[^>]+>", " ", content)
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean[:3000]

        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik}/{accession_clean}/{accession_fmt}-index.htm"
        )
        response = requests.get(index_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            clean = re.sub(r"<[^>]+>", " ", response.text)
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean[:2000]
    except Exception:
        pass

    return f"{form_type} filing for CIK {cik}, accession {accession_fmt}. Content unavailable."


def parse_form4_xml(xml_content):
    """Extract key transaction details from Form 4 XML."""
    try:
        owner = ""
        owner_match = re.search(
            r"<rptOwnerName>(.*?)</rptOwnerName>", xml_content, re.IGNORECASE
        )
        if owner_match:
            owner = owner_match.group(1).strip()

        issuer = ""
        issuer_match = re.search(
            r"<issuerName>(.*?)</issuerName>", xml_content, re.IGNORECASE
        )
        if issuer_match:
            issuer = issuer_match.group(1).strip()

        transactions = []

        non_deriv = re.findall(
            r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>",
            xml_content,
            re.DOTALL | re.IGNORECASE,
        )
        for t in non_deriv:
            try:
                date = extract_xml_value(t, "transactionDate")
                shares = extract_xml_value(t, "transactionShares")
                price = extract_xml_value(t, "transactionPricePerShare")
                code = extract_xml_value(t, "transactionCode")
                shares_after = extract_xml_value(t, "sharesOwnedFollowingTransaction")
                direct = extract_xml_value(t, "directOrIndirectOwnership")

                code_meaning = {
                    "S": "Open market sale",
                    "P": "Open market purchase",
                    "A": "Grant/award",
                    "D": "Disposition to issuer",
                    "F": "Tax withholding",
                    "G": "Gift",
                    "M": "Option exercise",
                    "X": "Option exercise",
                    "C": "Conversion",
                    "W": "Will/inheritance",
                }.get(code, f"Transaction code: {code}")

                if shares and price:
                    try:
                        total_value = float(shares.replace(",", "")) * float(
                            price.replace(",", "")
                        )
                        value_str = f"${total_value:,.0f} total value"
                    except Exception:
                        value_str = ""
                    transactions.append(
                        f"{code_meaning}: {shares} shares at ${price}/share "
                        f"{value_str} on {date}. Shares owned after transaction: "
                        f"{shares_after} ({direct} ownership)."
                    )
                else:
                    transactions.append(f"{code_meaning}: {shares} shares on {date}.")
            except Exception:
                continue

        deriv = re.findall(
            r"<derivativeTransaction>(.*?)</derivativeTransaction>",
            xml_content,
            re.DOTALL | re.IGNORECASE,
        )
        for t in deriv:
            try:
                date = extract_xml_value(t, "transactionDate")
                shares = extract_xml_value(t, "transactionShares")
                code = extract_xml_value(t, "transactionCode")
                security = extract_xml_value(t, "securityTitle")
                exercise_price = extract_xml_value(t, "conversionOrExercisePrice")

                code_meaning = {
                    "M": "Option exercise",
                    "X": "Option exercise (expired)",
                    "C": "Conversion",
                    "A": "Grant",
                }.get(code, f"Code {code}")

                transactions.append(
                    f"Derivative — {code_meaning}: {shares} {security} "
                    f"(exercise price: ${exercise_price}) on {date}."
                )
            except Exception:
                continue

        if not transactions and not owner:
            return xml_content[:2000]

        summary = f"Form 4 — Reporting owner: {owner}. Issuer: {issuer}.\n"
        if transactions:
            summary += "Transactions:\n" + "\n".join(transactions)
        else:
            summary += (
                "No standard transactions found in filing — "
                "may contain footnotes or amendments only."
            )
        return summary

    except Exception as e:
        return (
            f"Form 4 filing. XML parse error: {e}. "
            f"Raw excerpt: {xml_content[:500]}"
        )


def extract_xml_value(xml, tag):
    """Extract a value from XML, handling nested value tags."""
    pattern = rf"<{tag}>\s*<value>(.*?)</value>"
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def get_cik_for_ticker(ticker):
    try:
        response = requests.get(
            f"https://www.sec.gov/cgi-bin/browse-edgar?"
            f"company=&CIK={ticker}&type=20-F&dateb=&owner=include"
            f"&count=1&search_text=&action=getcompany&output=atom",
            headers=HEADERS,
            timeout=10,
        )
        if response.status_code == 200:
            match = re.search(r"CIK=(\d+)", response.text)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

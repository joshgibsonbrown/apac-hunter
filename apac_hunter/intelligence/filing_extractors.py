from __future__ import annotations

import re
from typing import Any

from apac_hunter.intelligence.structured_fact_schema import StructuredFactPacket


FORM4_CODE_MEANINGS = {
    "S": "Open market sale",
    "P": "Open market purchase",
    "A": "Grant or award",
    "D": "Disposition to issuer",
    "F": "Tax withholding",
    "G": "Gift",
    "M": "Option exercise",
    "X": "Option exercise",
    "C": "Conversion",
    "W": "Inheritance or will",
}


def _extract_xml_value(xml: str, tag: str) -> str:
    pattern = rf"<{tag}>\s*<value>(.*?)</value>"
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, xml, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()
    return ""


def _as_int(text: str | None) -> int | None:
    if not text:
        return None
    try:
        return int(float(text.replace(",", "")))
    except Exception:
        return None


def _as_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text.replace(",", ""))
    except Exception:
        return None


def extract_edgar_structured_facts(filing: dict[str, Any]) -> dict[str, Any] | None:
    form_type = str(filing.get("category") or "").upper()
    content = filing.get("raw_content") or filing.get("content") or ""
    if not content:
        return None

    if form_type == "4" and ("<ownershipdocument" in content.lower() or "<xml" in content.lower()):
        return extract_form4_facts(filing, content)

    return StructuredFactPacket(
        source_type="edgar",
        issuer=filing.get("company"),
        company=filing.get("company"),
        event_type=form_type or "edgar_filing",
        event_date=filing.get("date"),
        confidence="Low",
        facts={
            "form_type": form_type,
            "title": filing.get("title"),
            "content_excerpt": re.sub(r"\s+", " ", content)[:1000],
        },
        provenance={
            "source": filing.get("source"),
            "url": filing.get("url"),
        },
    ).to_dict()


def extract_form4_facts(filing: dict[str, Any], xml_content: str) -> dict[str, Any]:
    owner = _extract_xml_value(xml_content, "rptOwnerName") or None
    issuer = _extract_xml_value(xml_content, "issuerName") or filing.get("company")
    issuer_ticker = _extract_xml_value(xml_content, "issuerTradingSymbol") or filing.get("ticker")

    transactions = []
    for block in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", xml_content, re.I | re.S):
        code = _extract_xml_value(block, "transactionCode") or None
        shares = _as_int(_extract_xml_value(block, "transactionShares"))
        price = _as_float(_extract_xml_value(block, "transactionPricePerShare"))
        shares_after = _as_int(_extract_xml_value(block, "sharesOwnedFollowingTransaction"))
        date = _extract_xml_value(block, "transactionDate") or filing.get("date")
        ownership_nature = _extract_xml_value(block, "directOrIndirectOwnership") or None
        transaction = {
            "security_type": _extract_xml_value(block, "securityTitle") or "Common stock",
            "transaction_code": code,
            "transaction_label": FORM4_CODE_MEANINGS.get(code or "", code),
            "transaction_date": date,
            "shares": shares,
            "price_per_share": price,
            "gross_value": round(shares * price, 2) if shares and price else None,
            "shares_owned_following": shares_after,
            "ownership_nature": ownership_nature,
        }
        transactions.append(transaction)

    inferred_event = "insider_transaction"
    if any(t.get("transaction_code") == "S" for t in transactions):
        inferred_event = "block_trade"
    elif any(t.get("transaction_code") in {"P", "M", "C"} for t in transactions):
        inferred_event = "equity_position_change"

    primary = transactions[0] if transactions else {}
    return StructuredFactPacket(
        source_type="edgar",
        issuer=issuer,
        company=issuer,
        event_type=inferred_event,
        event_date=primary.get("transaction_date") or filing.get("date"),
        subject_name=owner,
        confidence="High" if transactions else "Medium",
        facts={
            "form_type": "4",
            "issuer_ticker": issuer_ticker,
            "transactions": transactions,
            "primary_transaction": primary,
            "shares_sold": primary.get("shares") if primary.get("transaction_code") == "S" else None,
            "price_per_share": primary.get("price_per_share"),
            "gross_value": primary.get("gross_value"),
            "shares_owned_following": primary.get("shares_owned_following"),
        },
        provenance={
            "source": filing.get("source"),
            "url": filing.get("url"),
            "title": filing.get("title"),
        },
    ).to_dict()


def extract_structured_facts(filing: dict[str, Any]) -> dict[str, Any] | None:
    source = str(filing.get("source") or "").lower()
    if "edgar" in source:
        return extract_edgar_structured_facts(filing)
    return None

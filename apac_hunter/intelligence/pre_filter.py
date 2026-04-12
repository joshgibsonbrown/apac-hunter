"""
Pre-filter: fast keyword/heuristic gate applied before AI classification.

Reduces 200+ scraped items to 30-50 high-signal candidates using
pure Python checks (no API calls). Items from pre-qualified sources
bypass the filter entirely.
"""

import re

# Sources that are already pre-qualified (structured data, not raw news)
BYPASS_SOURCES = {
    "sec edgar", "sgx", "acra", "companies house", "euronext",
    "lock-up expiry", "insider pattern analysis", "sec edgar ipo pipeline",
}

# Money signals — dollar amounts or wealth-related keywords
MONEY_PATTERNS = [
    re.compile(r"\$\d+[\d,.]*\s*[mbMB]", re.IGNORECASE),          # $50M, $1.2B
    re.compile(r"\$\d[\d,.]+\s*(?:million|billion)", re.IGNORECASE),  # $50 million
    re.compile(r"\d+\s*(?:million|billion)\s*(?:dollar|usd|eur|gbp)", re.IGNORECASE),
    re.compile(r"(?:€|£)\d+[\d,.]*\s*[mbMB]", re.IGNORECASE),      # €50M, £1.2B
]

MONEY_KEYWORDS = {
    "stake", "sale", "sold", "selling", "sell", "ipo", "listing",
    "acquisition", "merger", "acquire", "acquires", "acquired",
    "founder", "family office", "liquidity", "secondary",
    "tender offer", "lock-up", "lockup", "insider", "block trade",
    "dividend", "distribution", "proceeds", "exit", "buyout",
    "divestiture", "disposal", "restructur", "privatisation",
    "privatization", "valuation", "billion", "million",
    "pre-ipo", "series c", "series d", "series e", "unicorn",
    "spac", "de-spac",
}

# Person signals — named individuals or role keywords
PERSON_KEYWORDS = {
    "founder", "ceo", "chairman", "chairwoman", "director", "owner",
    "family", "tycoon", "billionaire", "millionaire", "co-founder",
    "cofounder", "executive", "cfo", "president", "managing director",
    "principal", "partner", "heir", "heiress", "patriarch", "matriarch",
    "controlling shareholder", "majority owner", "beneficial owner",
}

# Pattern for detecting capitalized name-like strings (e.g. "John Smith")
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")


def pre_filter(filings: list) -> list:
    """
    Apply fast heuristic checks to reduce the filing list before
    sending to the AI classifier.

    Returns only filings that pass the relevance gate.
    """
    passed = []

    for filing in filings:
        source = filing.get("source", "").lower()

        # Bypass filter for pre-qualified sources
        if _is_bypass_source(source):
            passed.append(filing)
            continue

        # Combine searchable text
        text = _get_searchable_text(filing)
        text_lower = text.lower()

        # Check for money signal
        has_money = _has_money_signal(text, text_lower)

        # Check for person signal
        has_person = _has_person_signal(text, text_lower)

        # Must have at least one of each to pass
        if has_money and has_person:
            passed.append(filing)
        elif has_money and _has_strong_money_signal(text_lower):
            # Strong money signal alone can pass (e.g. "$500M acquisition")
            passed.append(filing)

    filtered = len(filings) - len(passed)
    print(f"\nPre-filter: {len(passed)}/{len(filings)} items passed ({filtered} filtered out)")

    return passed


def _is_bypass_source(source_lower: str) -> bool:
    """Check if this source should bypass the filter."""
    for bypass in BYPASS_SOURCES:
        if bypass in source_lower:
            return True
    return False


def _get_searchable_text(filing: dict) -> str:
    """Combine all text fields for searching."""
    parts = [
        filing.get("title", ""),
        filing.get("content", ""),
        filing.get("company", ""),
        filing.get("source", ""),
    ]
    return " ".join(p for p in parts if p)


def _has_money_signal(text: str, text_lower: str) -> bool:
    """Check for dollar amounts or money-related keywords."""
    # Check regex patterns first (most specific)
    for pattern in MONEY_PATTERNS:
        if pattern.search(text):
            return True

    # Check keywords
    for kw in MONEY_KEYWORDS:
        if kw in text_lower:
            return True

    return False


def _has_strong_money_signal(text_lower: str) -> bool:
    """Check for particularly strong money signals that can pass alone."""
    strong = [
        "ipo", "acquisition", "merger", "tender offer", "block trade",
        "family office", "liquidity event", "exit", "billion",
    ]
    count = sum(1 for kw in strong if kw in text_lower)
    return count >= 2


def _has_person_signal(text: str, text_lower: str) -> bool:
    """Check for named individuals or person-related keywords."""
    # Check person keywords
    for kw in PERSON_KEYWORDS:
        if kw in text_lower:
            return True

    # Check for capitalized name patterns
    if NAME_PATTERN.search(text):
        return True

    return False

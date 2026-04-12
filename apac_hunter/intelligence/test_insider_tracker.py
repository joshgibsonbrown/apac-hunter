"""
Unit tests for insider_tracker transaction parsing.

Run with: python -m pytest apac_hunter/intelligence/test_insider_tracker.py -v
Or simply: python apac_hunter/intelligence/test_insider_tracker.py
"""

import sys
import os

# Prevent actual Supabase calls during tests
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key")

from apac_hunter.intelligence.insider_tracker import (
    save_form4_transactions,
    _safe_float,
    _description_to_code,
    detect_10b5_1_plan,
    parse_ownership_pct,
)
import re


# ---------------------------------------------------------------------------
# Sample Form 4 content (matches edgar.py parse_form4_xml output)
# ---------------------------------------------------------------------------

SAMPLE_FORM4_WITH_PRICE = (
    "Form 4 — Reporting owner: Anthony Tan. Issuer: Grab Holdings Limited.\n"
    "Transactions:\n"
    "Open market sale: 50000.0000 shares at $4.25/share $212,500 total value "
    "on 2026-03-28. Shares owned after transaction: 1500000.0000 (Direct ownership).\n"
    "Open market sale: 25000.0000 shares at $4.30/share $107,500 total value "
    "on 2026-03-29. Shares owned after transaction: 1475000.0000 (Direct ownership)."
)

SAMPLE_FORM4_NO_PRICE = (
    "Form 4 — Reporting owner: Forrest Li. Issuer: Sea Limited.\n"
    "Transactions:\n"
    "Tax withholding: 10000 shares on 2026-04-01.\n"
    "Gift: 5000 shares on 2026-04-01."
)

SAMPLE_FORM4_DERIVATIVE = (
    "Form 4 — Reporting owner: Min-Liang Tan. Issuer: Razer Inc.\n"
    "Transactions:\n"
    "Option exercise: 100000.0000 shares at $2.50/share $250,000 total value "
    "on 2026-03-25. Shares owned after transaction: 5000000.0000 (Direct ownership).\n"
    "Derivative — Option exercise: 100000 Stock Option (exercise price: $2.50) on 2026-03-25."
)

SAMPLE_10B5_1 = (
    "Form 4 — Reporting owner: Test Person. Issuer: Test Corp.\n"
    "Transactions:\n"
    "Open market sale: 20000 shares at $10.00/share $200,000 total value "
    "on 2026-04-01. Shares owned after transaction: 800000 (Direct ownership).\n"
    "Footnote: These transactions were effected pursuant to a Rule 10b5-1 "
    "trading plan adopted on January 15, 2026."
)


def test_primary_parser_with_price():
    """Test that the primary regex correctly parses transactions with price/value."""
    from apac_hunter.intelligence.insider_tracker import save_form4_transactions

    # Monkey-patch save to avoid DB calls
    saved_records = []
    original_save = __import__('apac_hunter.intelligence.insider_tracker',
                                fromlist=['save_insider_transaction']).save_insider_transaction

    def mock_save(**kwargs):
        saved_records.append(kwargs)

    import apac_hunter.intelligence.insider_tracker as mod
    mod.save_insider_transaction = lambda *a, **kw: saved_records.append(kw)

    try:
        result = save_form4_transactions(
            SAMPLE_FORM4_WITH_PRICE, "Grab Holdings Limited", "GRAB",
            "https://sec.gov/test", "apac"
        )
        assert len(result) == 2, f"Expected 2 transactions, got {len(result)}"
        assert result[0]["individual_name"] == "Anthony Tan"
        assert result[0]["transaction_code"] == "S"
        assert result[0]["shares"] == 50000.0
        assert result[0]["price_per_share"] == 4.25
        assert result[0]["total_value"] == 212500.0
        assert result[1]["shares"] == 25000.0
        print("✓ test_primary_parser_with_price passed")
    finally:
        mod.save_insider_transaction = original_save


def test_primary_parser_no_price():
    """Test parsing transactions without price/total value."""
    saved_records = []
    import apac_hunter.intelligence.insider_tracker as mod
    original = mod.save_insider_transaction
    mod.save_insider_transaction = lambda *a, **kw: saved_records.append(kw)

    try:
        result = save_form4_transactions(
            SAMPLE_FORM4_NO_PRICE, "Sea Limited", "SE",
            "https://sec.gov/test", "apac"
        )
        assert len(result) == 2, f"Expected 2 transactions, got {len(result)}"
        assert result[0]["transaction_code"] == "F"  # Tax withholding
        assert result[1]["transaction_code"] == "G"  # Gift
        print("✓ test_primary_parser_no_price passed")
    finally:
        mod.save_insider_transaction = original


def test_10b5_1_detection():
    """Test 10b5-1 plan detection."""
    is_plan, text = detect_10b5_1_plan(SAMPLE_10B5_1)
    assert is_plan is True
    assert "10b5-1" in text.lower()
    print("✓ test_10b5_1_detection passed")

    is_plan2, _ = detect_10b5_1_plan("Just a normal filing with no plan references.")
    assert is_plan2 is False
    print("✓ test_10b5_1_no_match passed")


def test_safe_float():
    """Test _safe_float edge cases."""
    assert _safe_float("1,234.56") == 1234.56
    assert _safe_float("$50,000") == 50000.0
    assert _safe_float("50000.0000") == 50000.0
    assert _safe_float(None) == 0.0
    assert _safe_float("") == 0.0
    assert _safe_float("abc") == 0.0
    print("✓ test_safe_float passed")


def test_description_to_code():
    """Test transaction description to code mapping."""
    assert _description_to_code("Open market sale") == "S"
    assert _description_to_code("OPEN MARKET SALE") == "S"
    assert _description_to_code("Tax withholding") == "F"
    assert _description_to_code("Option exercise") == "M"
    assert _description_to_code("Gift") == "G"
    assert _description_to_code("Unknown thing") == "X"
    print("✓ test_description_to_code passed")


def test_ownership_pct_parsing():
    """Test SC 13D/G ownership percentage extraction."""
    content1 = "The reporting person beneficially owns 5.2% of the outstanding common stock."
    pct, _ = parse_ownership_pct(content1)
    assert pct == 5.2, f"Expected 5.2, got {pct}"
    print("✓ test_ownership_pct_parsing passed")

    content2 = "Aggregate percentage of class: 12.8%"
    pct2, _ = parse_ownership_pct(content2)
    assert pct2 == 12.8, f"Expected 12.8, got {pct2}"
    print("✓ test_ownership_pct_aggregate passed")


if __name__ == "__main__":
    print("\nRunning insider_tracker unit tests...\n")
    test_safe_float()
    test_description_to_code()
    test_primary_parser_with_price()
    test_primary_parser_no_price()
    test_10b5_1_detection()
    test_ownership_pct_parsing()
    print("\n✅ All tests passed!\n")

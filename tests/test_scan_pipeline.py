"""
Tests for scan pipeline logic that can run without external API calls.
Covers: source list building, deduplication, progress callback contract,
and pre-filter pass-through.
"""
import pytest
from unittest.mock import MagicMock, patch, call


# ── Source / mode filtering ────────────────────────────────────────────────────

class TestSourceFiltering:
    """Verify QUICK_SOURCES filtering matches expected set."""

    def test_quick_sources_defined(self):
        from apac_hunter.scanner._run import QUICK_SOURCES
        assert "sgx" in QUICK_SOURCES
        assert "edgar" in QUICK_SOURCES
        assert "news" in QUICK_SOURCES
        # deep-only sources should NOT be in quick
        assert "acra" not in QUICK_SOURCES
        assert "rss_feeds" not in QUICK_SOURCES
        assert "secondary_market" not in QUICK_SOURCES

    def test_quick_mode_filters_sources(self):
        from apac_hunter.scanner._run import QUICK_SOURCES
        full_sources = ["sgx", "acra", "rss_feeds", "edgar", "private_companies", "news"]
        quick = [s for s in full_sources if s in QUICK_SOURCES]
        assert set(quick) == {"sgx", "edgar", "news"}


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:
    """The dedup step in run_scan removes filings with duplicate titles."""

    def _dedup(self, filings):
        seen = set()
        deduped = []
        for f in filings:
            title = f.get("title", "").strip().lower()[:80]
            if title and title not in seen:
                seen.add(title)
                deduped.append(f)
        return deduped

    def test_removes_exact_duplicates(self):
        filings = [
            {"title": "Grab IPO lock-up expiry", "content": "a"},
            {"title": "Grab IPO lock-up expiry", "content": "b"},  # dup
            {"title": "Sea Ltd insider selling", "content": "c"},
        ]
        deduped = self._dedup(filings)
        assert len(deduped) == 2

    def test_case_insensitive(self):
        filings = [
            {"title": "GRAB IPO", "content": "a"},
            {"title": "grab ipo", "content": "b"},
        ]
        deduped = self._dedup(filings)
        assert len(deduped) == 1

    def test_empty_title_not_deduped_with_others(self):
        filings = [
            {"title": "", "content": "a"},
            {"title": "", "content": "b"},
            {"title": "Real title", "content": "c"},
        ]
        # items with empty titles are dropped by the title check
        deduped = self._dedup(filings)
        assert len(deduped) == 1
        assert deduped[0]["title"] == "Real title"

    def test_truncates_at_80_chars(self):
        long = "A" * 100
        filings = [
            {"title": long, "content": "a"},
            {"title": long + "extra", "content": "b"},  # same first 80 chars
        ]
        deduped = self._dedup(filings)
        assert len(deduped) == 1


# ── Progress callback ─────────────────────────────────────────────────────────

class TestProgressCallback:
    """Verify that run_scan calls progress_callback and that the default no-op works."""

    def test_noop_callback_is_callable(self):
        from apac_hunter.scanner._run import _noop_progress
        _noop_progress(50, "half way")  # should not raise

    def test_run_scan_calls_callback(self):
        """
        Run a minimal patched scan and confirm the callback is invoked at least once.
        """
        callback = MagicMock()

        with (
            patch("apac_hunter.scanner._run.collect_filings", return_value=([], {})),
            patch("apac_hunter.scanner._run.enrich_edgar_filings"),
            patch("apac_hunter.scanner._run.pre_filter", return_value=[]),
            patch("apac_hunter.scanner._run._update_scan_stats"),
        ):
            from apac_hunter.scanner._run import run_scan
            result = run_scan(days_back=1, regions=["apac"], scan_mode="quick",
                              progress_callback=callback)

        assert result == []
        assert callback.call_count >= 1
        # First call should include a meaningful status string
        first_status = callback.call_args_list[0][0][1]
        assert isinstance(first_status, str) and len(first_status) > 0

    def test_run_scan_no_valid_regions_returns_empty(self):
        from apac_hunter.scanner._run import run_scan
        result = run_scan(regions=["nonexistent_region"])
        assert result == []


# ── Normaliser ────────────────────────────────────────────────────────────────

class TestNormaliser:
    def test_cleans_name(self):
        from apac_hunter.intelligence.normaliser import normalise_name
        assert normalise_name("  john doe  ") == "John Doe"

    def test_rejects_short_name(self):
        from apac_hunter.intelligence.normaliser import normalise_name
        assert normalise_name("Jo") is None or normalise_name("Jo") == ""

    def test_strips_uncertainty_words(self):
        from apac_hunter.intelligence.normaliser import normalise_name
        result = normalise_name("Unknown Founder")
        # Should be rejected or return empty/None for uncertain names
        assert result != "Unknown Founder" or result == ""

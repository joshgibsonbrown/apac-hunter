"""
Tests for scan job DB functions.
Uses unittest.mock to avoid hitting Supabase — tests the function logic only.
"""
import pytest
from unittest.mock import MagicMock, patch


# ── save_scan_job ─────────────────────────────────────────────────────────────

class TestSaveScanJob:
    def test_returns_job_id_on_success(self):
        mock_result = MagicMock()
        mock_result.data = [{"id": "abc-123"}]

        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.insert.return_value.execute.return_value = mock_result
            from apac_hunter.database import save_scan_job
            job_id = save_scan_job({"scan_mode": "quick", "regions": ["apac"]})

        assert job_id == "abc-123"

    def test_returns_none_on_db_error(self):
        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception("DB down")
            from apac_hunter.database import save_scan_job
            job_id = save_scan_job({"scan_mode": "quick"})

        assert job_id is None


# ── update_scan_job ───────────────────────────────────────────────────────────

class TestUpdateScanJob:
    def test_calls_update_with_correct_id(self):
        with patch("apac_hunter.database.supabase") as mock_sb:
            chain = MagicMock()
            mock_sb.table.return_value.update.return_value.eq.return_value.execute = chain
            from apac_hunter.database import update_scan_job
            update_scan_job("abc-123", {"status": "running", "progress": 50})

        mock_sb.table.return_value.update.assert_called_once_with({"status": "running", "progress": 50})
        mock_sb.table.return_value.update.return_value.eq.assert_called_once_with("id", "abc-123")

    def test_silently_ignores_db_error(self):
        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("oops")
            from apac_hunter.database import update_scan_job
            # Should not raise
            update_scan_job("abc-123", {"status": "running"})


# ── get_scan_job ──────────────────────────────────────────────────────────────

class TestGetScanJob:
    def test_returns_job_dict(self):
        job = {"id": "abc-123", "status": "complete", "progress": 100}
        mock_result = MagicMock()
        mock_result.data = [job]

        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            from apac_hunter.database import get_scan_job
            result = get_scan_job("abc-123")

        assert result == job

    def test_returns_none_when_not_found(self):
        mock_result = MagicMock()
        mock_result.data = []

        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
            from apac_hunter.database import get_scan_job
            result = get_scan_job("does-not-exist")

        assert result is None

    def test_returns_none_on_db_error(self):
        with patch("apac_hunter.database.supabase") as mock_sb:
            mock_sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("err")
            from apac_hunter.database import get_scan_job
            result = get_scan_job("abc-123")

        assert result is None


# ── get_latest_scan_job ───────────────────────────────────────────────────────

class TestGetLatestScanJob:
    def test_returns_most_recent_job(self):
        job = {"id": "abc-123", "status": "complete", "created_at": "2026-04-09T12:00:00"}
        mock_result = MagicMock()
        mock_result.data = [job]

        with patch("apac_hunter.database.supabase") as mock_sb:
            (mock_sb.table.return_value.select.return_value
             .order.return_value.limit.return_value.execute.return_value) = mock_result
            from apac_hunter.database import get_latest_scan_job
            result = get_latest_scan_job()

        assert result == job

    def test_returns_none_when_no_jobs(self):
        mock_result = MagicMock()
        mock_result.data = []

        with patch("apac_hunter.database.supabase") as mock_sb:
            (mock_sb.table.return_value.select.return_value
             .order.return_value.limit.return_value.execute.return_value) = mock_result
            from apac_hunter.database import get_latest_scan_job
            result = get_latest_scan_job()

        assert result is None


# ── scan_status endpoint ──────────────────────────────────────────────────────

class TestScanStatusEndpoint:
    """Integration-style test for the /scan/status route shape."""

    def _make_app(self):
        import os
        os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
        os.environ.setdefault("DASHBOARD_PASSWORD", "testpass")
        os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")
        os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
        os.environ.setdefault("SUPABASE_KEY", "test-key")

    def test_status_response_shape_with_job(self):
        self._make_app()
        job = {
            "id": "job-1",
            "status": "running",
            "progress": 42,
            "status_message": "Classifying...",
            "error": None,
            "briefs_generated": 0,
        }
        with patch("apac_hunter.database.get_scan_job", return_value=job):
            import app as flask_app
            flask_app.app.config["TESTING"] = True
            with flask_app.app.test_client() as client:
                with client.session_transaction() as sess:
                    sess["authenticated"] = True
                resp = client.get("/scan/status?job_id=job-1")
                data = resp.get_json()

        assert data["running"] is True
        assert data["progress"] == 42
        assert data["status"] == "Classifying..."
        assert "job_id" in data

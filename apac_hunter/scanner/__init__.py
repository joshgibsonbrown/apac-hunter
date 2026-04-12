"""
apac_hunter.scanner — intelligence scan orchestration package.

Public API (unchanged from original scanner.py):
    run_scan(days_back, sources, regions, scan_mode, progress_callback) -> list
    get_last_scan_stats() -> dict
"""
from apac_hunter.scanner._run import run_scan, get_last_scan_stats

__all__ = ["run_scan", "get_last_scan_stats"]

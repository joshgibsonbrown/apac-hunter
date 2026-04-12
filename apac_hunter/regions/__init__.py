from datetime import datetime
from apac_hunter.regions.apac import REGION_CONFIG as APAC_CONFIG
from apac_hunter.regions.europe import REGION_CONFIG as EUROPE_CONFIG

ALL_REGIONS = {
    "apac": APAC_CONFIG,
    "europe": EUROPE_CONFIG,
}


def get_region_config(region_id: str) -> dict:
    """Return the region config dict for a given region ID, or raise KeyError."""
    config = ALL_REGIONS.get(region_id)
    if config is None:
        raise KeyError(f"Unknown region: {region_id!r}. Available: {list(ALL_REGIONS.keys())}")
    return config


def get_current_year() -> str:
    """Return the current year as a string. Used to replace hardcoded
    years in news queries so they don't go stale."""
    return str(datetime.now().year)

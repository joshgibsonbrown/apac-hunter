from __future__ import annotations
"""
Source fetching layer — collects raw filings from all configured data sources.

Returns (all_filings, filing_region_map, edgar_filings, ipo_filings) where:
  - all_filings: every fetched filing (pre-dedup, pre-filter)
  - filing_region_map: {id(filing_dict): region_config}
  - edgar_filings: subset from SEC EDGAR (for insider/ownership enrichment)
  - ipo_filings: subset from IPO pipeline (for lock-up calendar seeding)
"""
from apac_hunter.regions import get_region_config
from apac_hunter.scrapers.sgx import fetch_sgx_announcements
from apac_hunter.scrapers.acra import fetch_acra_formations
from apac_hunter.scrapers.edgar import fetch_edgar_filings
from apac_hunter.scrapers.news import fetch_news
from apac_hunter.scrapers.companies_house import fetch_companies_house
from apac_hunter.scrapers.euronext import fetch_euronext
from apac_hunter.scrapers.rns import fetch_rns_announcements
from apac_hunter.scrapers.ipo_pipeline import fetch_ipo_pipeline
from apac_hunter.scrapers.secondary_market import fetch_secondary_market
from apac_hunter.scrapers.rss_feeds import fetch_rss_feeds
from apac_hunter.scrapers.hkex_listings import fetch_hkex_listings
from apac_hunter.scrapers.sgx_listings import fetch_sgx_listings
from apac_hunter.scrapers.ma_regulatory import fetch_ma_regulatory
from apac_hunter.scrapers.pe_deal_feeds import fetch_pe_deal_feeds
from apac_hunter.scrapers.private_companies import fetch_private_companies


def collect_filings(
    active_configs: list,
    merged_sources: list,
    days_back: int,
) -> tuple[list, dict, list, list]:
    """
    Fetch raw filings from every active source.

    Returns:
        all_filings: every filing fetched (not yet deduplicated)
        filing_region_map: {id(filing): region_config}
        edgar_filings: EDGAR filings only (for insider/ownership enrichment)
        ipo_filings: IPO pipeline filings only (for lock-up calendar seeding)
    """
    all_filings: list = []
    filing_region_map: dict = {}
    edgar_filings: list = []
    ipo_filings: list = []

    def _add(filings, region_cfg):
        for f in filings:
            filing_region_map[id(f)] = region_cfg
        all_filings.extend(filings)

    if "sgx" in merged_sources:
        print("Fetching SGX announcements...")
        _add(fetch_sgx_announcements(days_back=days_back), get_region_config("apac"))

    if "acra" in merged_sources:
        print("Fetching ACRA formations...")
        _add(fetch_acra_formations(days_back=days_back), get_region_config("apac"))

    if "hkex_listings" in merged_sources:
        print("Fetching HKEX new listings...")
        _add(fetch_hkex_listings(days_back=days_back), get_region_config("apac"))

    if "sgx_listings" in merged_sources:
        print("Fetching SGX new listings...")
        _add(fetch_sgx_listings(days_back=days_back), get_region_config("apac"))

    if "edgar" in merged_sources:
        merged_tickers: dict = {}
        for cfg in active_configs:
            if "edgar" in cfg["sources"]:
                merged_tickers.update(cfg["edgar_tickers"])
        print("Fetching SEC EDGAR filings...")
        edgar_filings = fetch_edgar_filings(
            days_back=days_back, region_config={"edgar_tickers": merged_tickers}
        )
        print(f"  → {len(edgar_filings)} EDGAR items fetched")
        for f in edgar_filings:
            filing_region_map[id(f)] = _region_for_ticker(f.get("ticker", ""), active_configs)
        all_filings.extend(edgar_filings)

    if "ipo_pipeline" in merged_sources:
        print("Fetching IPO pipeline filings...")
        merged_tickers_ipo: dict = {}
        for cfg in active_configs:
            if "ipo_pipeline" in cfg["sources"]:
                merged_tickers_ipo.update(cfg.get("edgar_tickers", {}))
        ipo_filings = fetch_ipo_pipeline(
            days_back=max(days_back, 30),
            region_config={"edgar_tickers": merged_tickers_ipo, "id": "merged"},
        )
        for f in ipo_filings:
            rcfg = _region_for_ticker(f.get("ticker", ""), active_configs) or active_configs[0]
            filing_region_map[id(f)] = rcfg
        all_filings.extend(ipo_filings)

    if "secondary_market" in merged_sources:
        print("Fetching secondary market intelligence...")
        _add(fetch_secondary_market(days_back=days_back), active_configs[0])

    if "ma_regulatory" in merged_sources:
        print("Fetching M&A regulatory filings...")
        _add(fetch_ma_regulatory(days_back=days_back), active_configs[0])

    if "pe_deal_feeds" in merged_sources:
        print("Fetching PE and advisory deal feeds...")
        _add(fetch_pe_deal_feeds(days_back=days_back), active_configs[0])

    if "private_companies" in merged_sources:
        for cfg in active_configs:
            if "private_companies" in cfg["sources"]:
                print(f"Fetching private company intelligence for {cfg['label']}...")
                _add(fetch_private_companies(days_back=days_back, region_config=cfg), cfg)

    if "news" in merged_sources:
        for cfg in active_configs:
            if "news" in cfg["sources"]:
                print(f"Fetching news for {cfg['label']}...")
                _add(fetch_news(days_back=days_back, region_config=cfg), cfg)

    if "rss_feeds" in merged_sources:
        for cfg in active_configs:
            if "rss_feeds" in cfg["sources"]:
                print(f"Fetching RSS feeds for {cfg['label']}...")
                _add(fetch_rss_feeds(days_back=days_back, region_config=cfg), cfg)

    if "companies_house" in merged_sources:
        print("Fetching Companies House filings...")
        _add(fetch_companies_house(days_back=days_back), get_region_config("europe"))

    if "euronext" in merged_sources:
        print("Fetching Euronext / ESMA disclosures...")
        _add(fetch_euronext(days_back=days_back), get_region_config("europe"))

    if "rns" in merged_sources:
        print("Fetching LSE RNS announcements (via Investegate)...")
        _add(fetch_rns_announcements(days_back=days_back), get_region_config("europe"))

    return all_filings, filing_region_map, edgar_filings, ipo_filings


def _region_for_ticker(ticker: str, configs: list) -> dict | None:
    for cfg in configs:
        if ticker in cfg.get("edgar_tickers", {}):
            return cfg
    return configs[0] if configs else None

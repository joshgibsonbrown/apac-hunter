REGION_CONFIG = {
    "id": "apac",
    "label": "APAC",
    "countries": [
        "Singapore", "Hong Kong", "China", "Taiwan", "Japan", "South Korea",
        "Indonesia", "Malaysia", "Thailand", "Philippines", "Vietnam",
        "India", "Australia", "New Zealand", "Bangladesh", "Sri Lanka",
        "Myanmar", "Cambodia", "Laos", "Brunei", "Macau",
    ],
    "sources": ["sgx", "acra", "edgar", "news", "ipo_pipeline", "secondary_market", "rss_feeds", "hkex_listings", "sgx_listings", "ma_regulatory", "pe_deal_feeds", "private_companies"],
    "news_queries": [
        # M&A and liquidity events
        "APAC founder acquisition merger deal 2026 Singapore Hong Kong",
        "Southeast Asia founder IPO listing 2026",
        "Singapore billionaire family office formation 2026",
        "Hong Kong tycoon stake sale block trade 2026",
        "APAC tech founder secondary sale shares 2026",
        # Dividend and distribution events
        "Singapore private company dividend distribution 2026",
        "Malaysia founder family dividend special distribution 2026",
        # Structural changes
        "Singapore family office setup MAS 13O 13U 2026",
        "APAC founder holding company restructure 2026",
        "Southeast Asia wealth succession planning 2026",
        # SGX filing signals
        "SGX substantial shareholder change Singapore 2026",
        "SGX director interest disposal block trade Singapore 2026",
        "SGX EGM voting rights dual class Singapore founder 2026",
        "Singapore IPO listing Bursa SGX founder stake 2026",
        # Specific high-value sectors
        "Singapore real estate developer family liquidity 2026",
        "Indonesia founder stake sale IPO 2026",
        "Vietnam founder wealth event 2026",
        "Philippines conglomerate family restructure 2026",
        "Thailand billionaire family office 2026",
        # Secondary market (Phase 6)
        "secondary share sale private company Asia 2026",
        "employee liquidity program Singapore Hong Kong 2026",
        "tender offer private company Southeast Asia 2026",
        "pre-IPO secondary shares Asia 2026",
        # Global secondary (Phase 6)
        "Forge Global secondary transaction 2026",
        "EquityZen secondary shares 2026",
        "secondary tender offer unicorn 2026",
        "employee stock liquidity program 2026",
    ],
    "edgar_tickers": {
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
    },
    "classifier_mandate": (
        "ICONIQ's APAC mandate covers founders, private business owners, and "
        "business-owning families based in or originating from the Asia-Pacific region, "
        "including Singapore, Hong Kong, China, Taiwan, Japan, South Korea, Southeast Asia, "
        "India, and Australia/New Zealand. The individual must be an APAC founder, private "
        "business owner, or business-owning family member. Wealth threshold: individual "
        "likely has $50M+ net worth OR the specific event involves $30M+ in value. For "
        "corporate events (dividends, M&A): the company must be large enough that private "
        "owner proceeds would be material (typically $100M+ company value)."
    ),
}

REGION_CONFIG = {
    "id": "europe",
    "label": "Europe",
    "countries": [
        "United Kingdom", "UK", "England", "Scotland", "Wales", "Northern Ireland",
        "Germany", "France", "Switzerland", "Netherlands", "Sweden", "Norway",
        "Denmark", "Finland", "Ireland", "Belgium", "Luxembourg", "Austria",
        "Italy", "Spain", "Portugal", "Greece", "Poland", "Czech Republic",
        "Monaco", "Liechtenstein", "Channel Islands", "Jersey", "Guernsey",
        "Isle of Man", "Cyprus", "Malta", "Iceland", "Estonia", "Latvia", "Lithuania",
    ],
    "sources": ["companies_house", "euronext", "rns", "edgar", "news", "ipo_pipeline", "secondary_market", "rss_feeds", "ma_regulatory", "pe_deal_feeds", "private_companies"],
    "news_queries": [
        # UK M&A and liquidity
        "UK founder acquisition merger deal 2026",
        "London IPO listing AIM Main Market founder 2026",
        "UK tech founder secondary sale block trade 2026",
        "UK billionaire family office formation 2026",
        # Continental Europe M&A
        "Germany founder acquisition Mittelstand sale 2026",
        "France founder IPO Euronext listing 2026",
        "Switzerland family office wealth structuring 2026",
        "Netherlands founder stake sale block trade 2026",
        "Nordic founder IPO Stockholm Nasdaq 2026",
        # Family office and succession
        "European family office formation restructure 2026",
        "European founder succession planning wealth transfer 2026",
        "UK family office Single Family Office setup 2026",
        "Swiss holding company restructure founder 2026",
        # Structural and regulatory
        "European founder holding company restructure 2026",
        "UK Companies House PSC significant control change 2026",
        "Euronext major shareholder disclosure insider transaction 2026",
        # High-value sectors
        "European real estate developer family liquidity event 2026",
        "German industrial family Mittelstand sale private equity 2026",
        "Scandinavian founder tech IPO secondary 2026",
        "French luxury brand founder stake sale 2026",
        # Secondary market (Phase 6)
        "secondary share sale private company UK Europe 2026",
        "employee liquidity program London 2026",
        "tender offer private company Europe 2026",
        "pre-IPO secondary shares Europe 2026",
        # Global secondary (Phase 6)
        "Forge Global secondary transaction 2026",
        "EquityZen secondary shares 2026",
        "secondary tender offer unicorn 2026",
        "employee stock liquidity program 2026",
    ],
    "edgar_tickers": {
        "ASML": "ASML Holding NV",
        "SPOT": "Spotify Technology SA",
        "WISE": "Wise plc",
        "FLUT": "Flutter Entertainment plc",
        "UL": "Unilever plc",
        "SAP": "SAP SE",
        "NVO": "Novo Nordisk A/S",
        "AZN": "AstraZeneca plc",
        "GSK": "GSK plc",
        "SHOP": "Shopify Inc",
        "RACE": "Ferrari NV",
        "ARM": "Arm Holdings plc",
        "BIRK": "Birkenstock Holding plc",
        "LSPD": "Lightspeed Commerce Inc",
        "COUR": "Coursera Inc",
        "TKO": "TKO Group Holdings",
        "CRTO": "Criteo SA",
        "DAVA": "Endava plc",
        "MNDY": "monday.com Ltd",
    },
    "classifier_mandate": (
        "ICONIQ's Europe mandate covers founders, private business owners, and "
        "business-owning families based in or originating from Europe, including the "
        "United Kingdom, Germany, France, Switzerland, Netherlands, Nordics (Sweden, "
        "Norway, Denmark, Finland), Ireland, Belgium, Luxembourg, Austria, Italy, Spain, "
        "and Portugal. This includes Mittelstand family businesses, tech founders with "
        "European roots who may have US-listed vehicles, family offices based in London, "
        "Zurich, Geneva, or Amsterdam, and multigenerational European industrial families "
        "undergoing succession or liquidity events. The individual must be a European "
        "founder, private business owner, or business-owning family member. Wealth "
        "threshold: individual likely has $50M+ net worth OR the specific event involves "
        "$30M+ in value. For corporate events (dividends, M&A): the company must be large "
        "enough that private owner proceeds would be material (typically $100M+ company value)."
    ),
}

ADAPTERS = {
    'APAC': {
        'primary_sources': ['SGX', 'ACRA', 'EDGAR', 'regional business news'],
        'notes': 'APAC Hunter prioritises founder, control, and liquidity signals across SGX, EDGAR, and regional news.',
    },
    'Europe': {
        'primary_sources': ['Companies House', 'FCA/RNS', 'AMF', 'Bundesanzeiger', 'regional business news'],
        'notes': 'Europe Hunter will require jurisdiction adapters because disclosure regimes and insider filing norms differ materially from APAC.',
    },
}


def get_adapter(region: str) -> dict:
    return ADAPTERS.get(region or 'APAC', ADAPTERS['APAC'])

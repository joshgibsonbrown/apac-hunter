from __future__ import annotations

import re
from typing import Any


CONTROL_TERMS = [
    'controlling shareholder', 'maintain control', 'control position', 'control preservation'
]

CAPITAL_DEPLOYMENT_TERMS = [
    'acquisition', 'takeover', 'bid', 'merger', 'm&a', 'capital deployment', 'integration'
]

SUCCESSION_TERMS = [
    'succession', 'intergenerational', 'family', 'daughter', 'legacy'
]

PHILANTHROPY_TERMS = [
    'foundation', 'philanthropy', 'pledge', 'university', 'education'
]


def _clean(value: Any) -> str:
    return str(value or '').strip()


def _first(values):
    return values[0] if values else None


def _money_from_match(raw: str, unit: str | None) -> int:
    value = float(raw.replace(',', ''))
    unit = (unit or '').lower()
    mult = 1
    if unit in {'m', 'million'}:
        mult = 1_000_000
    elif unit in {'bn', 'billion'}:
        mult = 1_000_000_000
    return int(value * mult)


def _extract_headline_raise(text: str) -> int | None:
    if not text:
        return None
    patterns = [
        re.compile(r'raising\s+(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)\s*(million|bn|billion|m)?', re.I),
        re.compile(r'raised\s+(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)\s*(million|bn|billion|m)?', re.I),
        re.compile(r'raise of\s+(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)\s*(million|bn|billion|m)?', re.I),
    ]
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return _money_from_match(m.group(1), m.group(2))
    return None


def _extract_money_near(text: str, keywords: list[str]) -> int | None:
    if not text:
        return None
    pattern = re.compile(r'(.{0,60}?)(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)\s*(million|bn|billion|m)?', re.I)
    vals = []
    for prefix, raw, unit in pattern.findall(text):
        pl = prefix.lower()
        if any(k in pl for k in keywords):
            vals.append(_money_from_match(raw, unit))
    return max(vals) if vals else None


def _extract_price(text: str) -> float | None:
    if not text:
        return None
    patterns = [
        re.compile(r'(?:priced at|price(?:d)? at|offer price(?:d)? at|at)\s*(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)', re.I),
        re.compile(r'(?:RM|MYR|HK\$|S\$)\s*(\d[\d,]*(?:\.\d+)?)', re.I),
    ]
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            return float(m.group(1).replace(',', ''))
    return None


def _range_text(low: int | None, high: int | None) -> str | None:
    if low is None and high is None:
        return None
    if low is not None and high is not None:
        return f'${low:,.0f} to ${high:,.0f}'
    v = low if low is not None else high
    return f'${v:,.0f}' if v is not None else None


def build_ipo_payload(brief: dict, context: dict) -> dict:
    subject = context['subject']
    event = context['event']
    raw = context.get('raw_sections', {})
    numeric = context.get('event_numeric_signals', {}) or context.get('numeric_signals', {})

    event_summary = _clean(event.get('summary'))
    profile = _clean(raw.get('profile'))
    wealth = _clean(raw.get('wealth_control_analysis'))
    behavioural = _clean(raw.get('behavioural_signals'))
    combined = ' '.join([event_summary, profile, wealth, behavioural])
    combined_low = combined.lower()

    headline_raise = _extract_headline_raise(event_summary)
    if headline_raise is None:
        headline_raise = _extract_money_near(event_summary, ['ipo', 'listing', 'debut'])
    offer_price = _extract_price(event_summary) or _first(numeric.get('price_points', []))
    shares_offered = _first(numeric.get('share_counts', []))
    stake_sale_pct = max(numeric.get('percentages', []) or []) if numeric.get('percentages') else None
    net_worth = _extract_money_near(profile, ['net worth', 'forbes estimates'])
    capital_need = _extract_money_near(event_summary, ['takeover', 'bid', 'acquisition', 'merger'])
    philanthropy_commitment = _extract_money_near(combined, ['foundation', 'pledge', 'commitment'])

    control_pressure = any(term in combined_low for term in CONTROL_TERMS)
    capital_deployment_live = any(term in combined_low for term in CAPITAL_DEPLOYMENT_TERMS)
    succession_relevance = any(term in combined_low for term in SUCCESSION_TERMS)
    philanthropy_relevance = any(term in combined_low for term in PHILANTHROPY_TERMS)
    mentions_lockup = 'lock-up' in combined_low or 'lock up' in combined_low

    liquidity_type = 'primary_listing' if ('raised' in event_summary.lower() or 'raising' in event_summary.lower() or 'debut' in event_summary.lower()) else 'mixed_or_unspecified'
    accessibility_band = 'constrained' if (control_pressure or mentions_lockup) else 'moderate'

    founder_exposure_low = founder_exposure_high = None
    if headline_raise:
        # tighter and more grounded than prior version: exposure is a read-through, not the full raise
        founder_exposure_low = int(headline_raise * 0.15)
        founder_exposure_high = int(headline_raise * 0.45 if control_pressure else headline_raise * 0.35)

    accessible_low = accessible_high = None
    if founder_exposure_low is not None and founder_exposure_high is not None:
        if accessibility_band == 'constrained':
            accessible_low = int(founder_exposure_low * 0.1)
            accessible_high = int(founder_exposure_high * 0.35)
        else:
            accessible_low = int(founder_exposure_low * 0.2)
            accessible_high = int(founder_exposure_high * 0.5)

    concentration_reference_pct = None
    if net_worth and founder_exposure_high:
        concentration_reference_pct = round(min(founder_exposure_high / net_worth, 1.0) * 100, 2)

    observed_facts = [
        {'metric': 'Headline raise', 'value': headline_raise, 'source': 'Event summary'},
        {'metric': 'Offer price', 'value': offer_price, 'source': 'Event summary or brief numeric extraction'},
        {'metric': 'Shares offered', 'value': shares_offered, 'source': 'Event summary or brief numeric extraction'},
        {'metric': 'Stated sell-down %', 'value': stake_sale_pct, 'source': 'Event summary or brief numeric extraction'},
        {'metric': 'Referenced net worth', 'value': net_worth, 'source': 'Profile'},
        {'metric': 'Competing capital deployment', 'value': capital_need, 'source': 'Event summary'},
        {'metric': 'Philanthropy commitment', 'value': philanthropy_commitment, 'source': 'Profile / wealth narrative'},
    ]

    assumptions = [
        'Headline IPO raise is treated as a company-level liquidity marker, not direct founder cash proceeds.',
        'Founder exposure is inferred as a bounded read-through from the listed asset rather than a verified personal sell-down.',
        'Accessible liquidity is haircut further for control, optics, and potential lock-up constraints.',
    ]
    if capital_deployment_live:
        assumptions.append('Part of the economic value created by the listing may be redirected toward operating or M&A priorities rather than personal diversification.')

    interpretation_parts = []
    if headline_raise:
        interpretation_parts.append(
            f'The listing creates a headline liquidity event of about ${headline_raise:,.0f}, but that should not be treated as equivalent to immediate founder cash proceeds.'
        )
    else:
        interpretation_parts.append(
            'The brief signals an IPO-related liquidity moment, but the size of the listing is not yet cleanly extractable from the available text.'
        )
    if founder_exposure_low is not None:
        interpretation_parts.append(
            f'A grounded founder exposure range is better framed at roughly {_range_text(founder_exposure_low, founder_exposure_high)}, with only {_range_text(accessible_low, accessible_high)} likely to be near-term accessible under current constraints.'
        )
    if capital_need:
        interpretation_parts.append(
            f'The concurrent reference to about ${capital_need:,.0f} of capital deployment pressure means this is partly a capital-allocation event, not just a monetisation event.'
        )
    elif capital_deployment_live:
        interpretation_parts.append(
            'The company appears to be in an active capital-deployment phase, which can reduce the practical importance of immediate founder liquidity.'
        )
    if succession_relevance or philanthropy_relevance:
        interpretation_parts.append(
            'This also looks like a governance and legacy moment: the more consequential question may be how listing liquidity reshapes succession, philanthropy, or family-asset architecture.'
        )

    decision_points = [
        {
            'title': 'Headline raise vs founder-accessible liquidity',
            'detail': 'Separate company-level capital raised from the portion the founder can realistically access in the near term without creating signalling or governance problems.',
        },
        {
            'title': 'Portfolio simplification vs strategic reinvestment',
            'detail': 'Assess whether any liquidity should reduce founder concentration or instead remain implicitly committed to operating-company or M&A priorities.',
        },
    ]
    if control_pressure or mentions_lockup:
        decision_points.append({
            'title': 'Control and optics constraints',
            'detail': 'Any early sell-down should be evaluated through the lens of control preservation, lock-up mechanics, and public-market interpretation rather than pure affordability.',
        })
    if succession_relevance or philanthropy_relevance:
        decision_points.append({
            'title': 'Legacy architecture',
            'detail': 'Use the listing as a forcing event to decide how much wealth should remain inside the operating structure versus being redirected toward family governance or philanthropic vehicles.',
        })

    risk_flags = [
        'Corporate IPO proceeds can materially overstate founder-accessible liquidity.',
        'Early sell-downs may be constrained by optics, lock-up, or control considerations even when the share price performs well.',
        'Where parallel M&A or reinvestment needs are live, founder diversification may not be the immediate priority.',
    ]

    return {
        'template_type': 'ipo_liquidity',
        'founder_name': subject['individual_name'],
        'company': subject['company'],
        'event_summary': event_summary,
        'observed': {
            'headline_raise': headline_raise,
            'offer_price': offer_price,
            'shares_offered': shares_offered,
            'stake_sale_pct': stake_sale_pct,
            'net_worth_reference': net_worth,
            'capital_need_reference': capital_need,
            'philanthropy_commitment': philanthropy_commitment,
        },
        'inferred': {
            'founder_exposure_range': _range_text(founder_exposure_low, founder_exposure_high),
            'accessible_liquidity_range': _range_text(accessible_low, accessible_high),
            'concentration_reference_pct_of_net_worth': concentration_reference_pct,
        },
        'model': {
            'liquidity_type': liquidity_type,
            'accessibility_band': accessibility_band,
            'control_pressure': control_pressure,
            'capital_deployment_live': capital_deployment_live,
            'succession_relevance': succession_relevance,
            'inference_confidence': 'Medium' if headline_raise else 'Low',
        },
        'scenario_defaults': {
            'base_price': offer_price,
            'base_sale_pct': stake_sale_pct,
            'lockup_days': 180 if mentions_lockup or liquidity_type == 'primary_listing' else None,
            'accessibility_band': accessibility_band,
        },
        'insight': {
            'interpretation': ' '.join(interpretation_parts),
            'real_liquidity_view': 'Near-term accessible founder liquidity should be treated as a constrained subset of the headline listing economics.',
            'concentration_view': 'The analytical question is whether the listing meaningfully reduces founder concentration or simply creates a more visible mark-to-market valuation for a still-concentrated position.',
            'decision_points': decision_points,
            'risk_flags': risk_flags,
        },
        'facts': [item for item in observed_facts if item['value'] not in (None, '')],
        'assumptions': assumptions,
    }


def build_ipo_liquidity_payload(brief: dict, context: dict) -> dict:
    return build_ipo_payload(brief, context)

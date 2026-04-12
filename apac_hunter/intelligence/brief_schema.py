import re
from typing import Any


APAC_COUNTRIES = {
    "singapore", "hong kong", "china", "japan", "south korea", "india",
    "indonesia", "malaysia", "thailand", "philippines", "vietnam", "taiwan",
    "australia", "new zealand"
}


def _clean(text: Any) -> str:
    return str(text or "").strip()


def _contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(term in low for term in terms)


def infer_region(country: str, company: str, trigger_type: str) -> str:
    text = " ".join([_clean(country), _clean(company), _clean(trigger_type)]).lower()
    if any(token in text for token in APAC_COUNTRIES):
        return "APAC"
    return "Global"


def extract_numeric_signals(text: str) -> dict:
    signals: dict[str, Any] = {
        "currency_amounts": [],
        "share_counts": [],
        "percentages": [],
        "price_points": [],
    }
    if not text:
        return signals

    amount_pattern = re.compile(r'(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)\s*(million|bn|billion|m)?', re.I)
    share_pattern = re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(million|m|bn|billion)?\s+shares?', re.I)
    pct_pattern = re.compile(r'(\d{1,3}(?:\.\d+)?)\s*%')
    price_pattern = re.compile(r'(?:at|price(?:d)? at|priced at|offer price(?:d)? at)\s*(?:US\$|USD\s?|\$)(\d[\d,]*(?:\.\d+)?)', re.I)

    for match in amount_pattern.finditer(text):
        raw, unit = match.groups()
        value = float(raw.replace(',', ''))
        mult = 1
        unit = (unit or '').lower()
        if unit in {'m', 'million'}:
            mult = 1_000_000
        elif unit in {'bn', 'billion'}:
            mult = 1_000_000_000
        signals['currency_amounts'].append(int(value * mult))

    for match in share_pattern.finditer(text):
        raw, unit = match.groups()
        value = float(raw.replace(',', ''))
        mult = 1
        unit = (unit or '').lower()
        if unit in {'m', 'million'}:
            mult = 1_000_000
        elif unit in {'bn', 'billion'}:
            mult = 1_000_000_000
        signals['share_counts'].append(int(value * mult))

    for match in pct_pattern.finditer(text):
        signals['percentages'].append(float(match.group(1)))

    for match in price_pattern.finditer(text):
        signals['price_points'].append(float(match.group(1).replace(',', '')))

    return signals


def _trigger_template_hint(trigger_type: str) -> str | None:
    trigger = (trigger_type or '').lower()
    # Control/voting events
    if any(token in trigger for token in [
        'voting', 'control', 'dual-class', 'dual class', 'structure change', 'voting structure'
    ]):
        return 'control_transition'
    # Liquidity/sale events
    if any(token in trigger for token in [
        'block trade', 'insider sale', 'disposal', 'large insider'
    ]):
        return 'liquidity_sequencing'
    # IPO events — only fire on explicit IPO trigger types, not mentions in text
    if any(token in trigger for token in [
        'ipo liquidity', 'ipo event', 'initial public offering', 'listing event'
    ]):
        return 'ipo_liquidity'
    return None


def build_analysis_context(brief: dict) -> dict:
    trigger_type = _clean(brief.get('last_trigger_type'))
    event_summary = _clean(brief.get('event_summary'))
    profile = _clean(brief.get('individual_profile'))
    wealth = _clean(brief.get('wealth_control_analysis'))
    access = _clean(brief.get('access_pathways'))
    behavioural = _clean(brief.get('behavioural_signals'))
    iconiq = _clean(brief.get('iconiq_value_prop'))
    conversation = _clean(brief.get('suggested_conversation'))

    combined = ' '.join([trigger_type, event_summary, profile, wealth, access, behavioural, iconiq, conversation])
    # For signal detection: use only trigger_type + event_summary to avoid false positives from narrative text
    summary_and_trigger = ' '.join([trigger_type, event_summary])

    numeric = extract_numeric_signals(combined)
    summary_numeric = extract_numeric_signals(summary_and_trigger)

    trigger_hint = _trigger_template_hint(trigger_type)

    # Signal detection from trigger + event summary only (not full brief)
    control_event = _contains_any(summary_and_trigger, [
        'voting', 'control', 'dual-class', 'dual class', 'proxy unwind', 'super-voting', 'super voting',
        'structure change', 'voting structure'
    ])
    liquidity_event = _contains_any(summary_and_trigger, [
        'block trade', 'insider sale', 'secondary', 'disposed', 'disposal', 'sale of shares', 'stake sale'
    ])
    # IPO detection: only from trigger_type, not event_summary, to avoid false positives
    ipo_event = _contains_any(trigger_type, [
        'ipo', 'initial public offering', 'listing event', 'ipo liquidity'
    ])

    return {
        'subject': {
            'individual_name': _clean(brief.get('individual_name')),
            'company': _clean(brief.get('company')),
            'region': infer_region(_clean(brief.get('country')), _clean(brief.get('company')), trigger_type),
        },
        'event': {
            'trigger_type': trigger_type,
            'summary': event_summary,
            'confidence': _clean(brief.get('confidence')) or 'Medium',
        },
        'signals': {
            'control_event': control_event,
            'liquidity_event': liquidity_event,
            'ipo_event': ipo_event,
            'mentions_price': bool(summary_numeric['price_points']),
            'mentions_shares': bool(summary_numeric['share_counts']),
            'mentions_percentages': bool(summary_numeric['percentages']),
        },
        'selection_hints': {
            'trigger_template_hint': trigger_hint,
            'trigger_is_high_confidence': trigger_hint is not None,
            'summary_contains_ipo_language': ipo_event,
            'summary_contains_control_language': control_event,
            'summary_contains_liquidity_language': liquidity_event,
        },
        'numeric_signals': numeric,
        'event_numeric_signals': summary_numeric,
        'raw_sections': {
            'profile': profile,
            'wealth_control_analysis': wealth,
            'access_pathways': access,
            'behavioural_signals': behavioural,
            'iconiq_value_prop': iconiq,
            'suggested_conversation': conversation,
        },
    }

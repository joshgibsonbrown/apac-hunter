from __future__ import annotations


def _first_or_none(values):
    return values[0] if values else None



def _safe_div(num, den):
    if not den:
        return None
    return num / den



def build_liquidity_payload(brief: dict, context: dict) -> dict:
    numeric = context.get('numeric_signals', {})
    shares = _first_or_none(numeric.get('share_counts', []))
    price = _first_or_none(numeric.get('price_points', []))
    percentages = numeric.get('percentages', []) or []
    stated_stake_pct = max(percentages) if percentages else None

    proceeds = shares * price if shares and price else None
    notional_remaining_pct = None
    if stated_stake_pct and len(percentages) > 1:
        try:
            sold_pct = min(percentages)
            if sold_pct < stated_stake_pct:
                notional_remaining_pct = round(stated_stake_pct - sold_pct, 2)
        except Exception:
            notional_remaining_pct = None

    intensity = 'Moderate'
    if proceeds and proceeds >= 300_000_000:
        intensity = 'High'
    elif proceeds and proceeds < 100_000_000:
        intensity = 'Low'

    interpretation_parts = []
    if proceeds:
        interpretation_parts.append(
            f'The event implies an estimated liquidity realization of approximately ${proceeds:,.0f}.'
        )
    else:
        interpretation_parts.append(
            'The event signals founder monetisation, but disclosed share count and pricing are incomplete, so proceeds cannot yet be sized deterministically.'
        )

    if stated_stake_pct:
        interpretation_parts.append(
            f'The brief references stake percentages up to {stated_stake_pct:.2f}%, which suggests relevance for ownership concentration and future selling capacity.'
        )
    else:
        interpretation_parts.append(
            'Ownership concentration remains a key unknown and should be confirmed from primary filings before drawing strong conclusions on sequencing risk.'
        )

    interpretation_parts.append(
        'The analytical question is whether this looks like one-off liquidity, the start of a monetisation program, or a broader shift in founder risk appetite.'
    )

    scenario_defaults = {
        'base_share_price': price or 10.0,
        'base_shares_to_sell': shares or 1_000_000,
        'estimated_remaining_stake_pct': notional_remaining_pct,
    }

    return {
        'template_type': 'liquidity_sequencing',
        'company': context['subject']['company'],
        'founder_name': context['subject']['individual_name'],
        'event_summary': context['event']['summary'],
        'observed': {
            'shares_sold': shares,
            'price_per_share': price,
            'estimated_proceeds': proceeds,
            'stated_stake_pct': stated_stake_pct,
            'estimated_remaining_stake_pct': notional_remaining_pct,
        },
        'scenario_defaults': scenario_defaults,
        'insight': {
            'liquidity_intensity': intensity,
            'interpretation': ' '.join(interpretation_parts),
            'questions': [
                'Was this sale opportunistic or programmatic?',
                'How much residual concentration remains after the sale?',
                'Does this create a repeatable liquidity path over the next 12 to 24 months?',
            ],
            'knowns_vs_unknowns': {
                'knowns': [
                    'Trigger identified as a monetisation / liquidity event.',
                    'Deterministic extraction run over the brief and trigger text.',
                ],
                'unknowns': [
                    'Remaining stake may not be fully disclosed in the current brief.',
                    'Selling program mechanics and intent may require primary filing confirmation.',
                ],
            },
        },
        'facts': [
            {
                'metric': 'Shares sold',
                'value': shares,
                'source': 'Brief-derived extraction',
            },
            {
                'metric': 'Price per share',
                'value': price,
                'source': 'Brief-derived extraction',
            },
            {
                'metric': 'Estimated proceeds',
                'value': proceeds,
                'source': 'Derived from shares x price when both are present',
            },
            {
                'metric': 'Largest stake % referenced',
                'value': stated_stake_pct,
                'source': 'Brief-derived extraction',
            },
        ],
    }

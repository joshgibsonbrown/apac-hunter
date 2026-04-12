from apac_hunter.intelligence.brief_schema import build_analysis_context


def choose_template(brief: dict) -> tuple[str, dict]:
    """
    Select the appropriate analysis template for a brief.
    
    Priority order:
    1. trigger_template_hint (derived directly from trigger_type string) — always wins
    2. Signal-based fallback — control takes priority over IPO if both present
    """
    context = build_analysis_context(brief)
    signals = context['signals']
    hints = context.get('selection_hints', {})

    # trigger_template_hint is derived directly from trigger_type string
    # and ALWAYS takes priority over text-based signal detection
    trigger_hint = hints.get('trigger_template_hint')
    if trigger_hint:
        return trigger_hint, context

    # Fallback: signal-based routing
    # Control takes priority over IPO if both signals present
    if signals['control_event']:
        return 'control_transition', context

    if signals['liquidity_event']:
        return 'liquidity_sequencing', context

    if signals['ipo_event']:
        return 'ipo_liquidity', context

    return 'generic', context

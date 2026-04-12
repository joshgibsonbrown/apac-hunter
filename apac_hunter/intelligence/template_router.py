from apac_hunter.intelligence.control_transition_template import run_control_transition
from apac_hunter.intelligence.liquidity_sequencing_template import build_liquidity_payload
from apac_hunter.intelligence.ipo_liquidity_template import build_ipo_liquidity_payload


def run_template(
    template_type: str,
    *,
    brief=None,
    context=None,
    pre_period=None,
    post_period=None,
    founder_name=None,
    aligned_names=None,
    control_floor_pct=50.0,
    sell_class="class_b",
    pre_sale_mechanics=None,
    post_sale_mechanics=None,
):
    if template_type == "control_transition":
        return run_control_transition(
            pre_period=pre_period,
            post_period=post_period,
            founder_name=founder_name,
            aligned_names=aligned_names or [],
            control_floor_pct=control_floor_pct,
            sell_class=sell_class,
            pre_sale_mechanics=pre_sale_mechanics,
            post_sale_mechanics=post_sale_mechanics,
        )

    if template_type == "liquidity_sequencing":
        return build_liquidity_payload(brief or {}, context or {})

    if template_type == "ipo_liquidity":
        return build_ipo_liquidity_payload(brief or {}, context or {})

    return {
        "template_type": template_type,
        "status": "not_implemented_yet"
    }

from apac_hunter.intelligence.control_model import snapshot, max_sellable_shares
from apac_hunter.intelligence.control_insight import analyse_control_transition


def build_transition_point(
    period: dict,
    founder_name: str,
    aligned_names: list[str],
    control_floor_pct: float = 50.0,
    sell_class: str = "class_b",
    sale_mechanics: dict | None = None,
) -> dict:
    snap = snapshot(period, founder_name, aligned_names)
    max_sell = max_sellable_shares(
        period,
        founder_name,
        aligned_names,
        control_floor_pct=control_floor_pct,
        sell_class=sell_class,
        sale_mechanics=sale_mechanics,
    )

    return {
        "period_label": period["label"],
        "founder_voting_pct": snap["founder_voting_pct"],
        "aligned_voting_pct": snap["aligned_voting_pct"],
        "max_sellable": max_sell,
    }


def run_control_transition(
    pre_period: dict,
    post_period: dict,
    founder_name: str,
    aligned_names: list[str],
    control_floor_pct: float = 50.0,
    sell_class: str = "class_b",
    pre_sale_mechanics: dict | None = None,
    post_sale_mechanics: dict | None = None,
) -> dict:
    pre_data = build_transition_point(
        pre_period,
        founder_name,
        aligned_names,
        control_floor_pct=control_floor_pct,
        sell_class=sell_class,
        sale_mechanics=pre_sale_mechanics,
    )

    post_data = build_transition_point(
        post_period,
        founder_name,
        aligned_names,
        control_floor_pct=control_floor_pct,
        sell_class=sell_class,
        sale_mechanics=post_sale_mechanics,
    )

    insight = analyse_control_transition(pre_data, post_data)

    return {
        "template_type": "control_transition",
        "founder_name": founder_name,
        "control_floor_pct": control_floor_pct,
        "sell_class": sell_class,
        "pre_sale_mechanics": pre_sale_mechanics,
        "post_sale_mechanics": post_sale_mechanics,
        "pre": pre_data,
        "post": post_data,
        "insight": insight,
    }

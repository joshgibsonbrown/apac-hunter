from apac_hunter.intelligence.jurisdiction_adapters import get_adapter
from apac_hunter.intelligence.scenario_registry import get_registered_scenario
from apac_hunter.intelligence.template_router import run_template
from apac_hunter.intelligence.template_selector import choose_template


def get_period(periods: list[dict], label: str) -> dict:
    for p in periods:
        if p["label"] == label:
            return p
    raise ValueError(f"Period not found: {label}")


def _standard_response(template_type: str, context: dict, adapter: dict, result: dict, assumptions: list[str] | None = None) -> dict:
    return {
        "status": "ok",
        "template_type": template_type,
        "analysis": result,
        "assumptions": assumptions or [],
        "context": context,
        "adapter": adapter,
    }


def build_template_analysis(brief: dict) -> dict:
    template_type, context = choose_template(brief)
    adapter = get_adapter(context["subject"]["region"])

    scenario = get_registered_scenario(context["subject"]["individual_name"], template_type)
    assumptions: list[str] = []

    if template_type == "control_transition" and scenario:
        pre_period = get_period(scenario["periods"], scenario["pre_period_label"])
        post_period = get_period(scenario["periods"], scenario["post_period_label"])
        assumptions = scenario.get("scenario", {}).get("assumptions", [])

        result = run_template(
            template_type,
            brief=brief,
            context=context,
            pre_period=pre_period,
            post_period=post_period,
            founder_name=context["subject"]["individual_name"],
            aligned_names=scenario.get("aligned_names") or [],
            control_floor_pct=scenario.get("control_floor_pct", 50.0),
            sell_class=scenario.get("sell_class", "class_b"),
            pre_sale_mechanics=scenario.get("scenario", {}).get("pre_sale_mechanics"),
            post_sale_mechanics=scenario.get("scenario", {}).get("post_sale_mechanics"),
        )
        return _standard_response(template_type, context, adapter, result, assumptions)

    if template_type in {"liquidity_sequencing", "ipo_liquidity"}:
        result = run_template(
            template_type,
            brief=brief,
            context=context,
        )
        return _standard_response(template_type, context, adapter, result, assumptions)

    return {
        "status": "not_implemented",
        "template_type": template_type,
        "analysis": None,
        "context": context,
        "adapter": adapter,
        "note": "No deterministic template wired yet for this brief.",
    }

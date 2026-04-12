from typing import Any

CONTROL_TRANSITION_SCHEMA = {
    "template_type": "control_transition",
    "founder_name": None,
    "company": None,
    "periods": [],
    "share_classes": {},
    "founder_holdings": {},
    "aligned_holders": [],
    "sale_mechanics": {
        "sell_class": None,
        "conversion_on_sale_to": None,
        "founder_vote_change_per_share_sold": None,
        "total_vote_change_per_share_sold": None,
    },
    "control_context": {
        "solo_control_floor_pct": 50.0,
        "notes": None,
    },
    "source_notes": [],
}


def build_control_transition_payload(
    founder_name: str,
    company: str,
    periods: list[dict],
    share_classes: dict[str, dict[str, Any]],
    founder_holdings: dict[str, float],
    aligned_holders: list[dict],
    sell_class: str,
    conversion_on_sale_to: str,
    founder_vote_change_per_share_sold: float,
    total_vote_change_per_share_sold: float,
    solo_control_floor_pct: float = 50.0,
    notes: str | None = None,
    source_notes: list[str] | None = None,
) -> dict:
    return {
        "template_type": "control_transition",
        "founder_name": founder_name,
        "company": company,
        "periods": periods,
        "share_classes": share_classes,
        "founder_holdings": founder_holdings,
        "aligned_holders": aligned_holders,
        "sale_mechanics": {
            "sell_class": sell_class,
            "conversion_on_sale_to": conversion_on_sale_to,
            "founder_vote_change_per_share_sold": founder_vote_change_per_share_sold,
            "total_vote_change_per_share_sold": total_vote_change_per_share_sold,
        },
        "control_context": {
            "solo_control_floor_pct": solo_control_floor_pct,
            "notes": notes,
        },
        "source_notes": source_notes or [],
    }


def validate_control_transition_payload(payload: dict) -> dict:
    required_top = [
        "template_type",
        "founder_name",
        "company",
        "periods",
        "share_classes",
        "founder_holdings",
        "aligned_holders",
        "sale_mechanics",
        "control_context",
    ]
    missing = [k for k in required_top if k not in payload]

    sale = payload.get("sale_mechanics", {})
    sale_required = [
        "sell_class",
        "conversion_on_sale_to",
        "founder_vote_change_per_share_sold",
        "total_vote_change_per_share_sold",
    ]
    sale_missing = [k for k in sale_required if sale.get(k) is None]

    ctx = payload.get("control_context", {})
    floor_missing = ctx.get("solo_control_floor_pct") is None

    return {
        "ok": not missing and not sale_missing and not floor_missing,
        "missing_top_level": missing,
        "missing_sale_mechanics": sale_missing,
        "missing_control_context": ["solo_control_floor_pct"] if floor_missing else [],
    }


if __name__ == "__main__":
    sample = build_control_transition_payload(
        founder_name="Anthony Tan",
        company="Grab Holdings",
        periods=[
            {"label": "FY2025", "founder_voting_pct": 41.49},
            {"label": "Post-EGM", "founder_voting_pct": 50.87},
        ],
        share_classes={
            "class_a": {"votes_per_share": 1},
            "class_b": {"votes_per_share": 90},
        },
        founder_holdings={"class_a": 0, "class_b": 26000000},
        aligned_holders=[],
        sell_class="class_b",
        conversion_on_sale_to="class_a",
        founder_vote_change_per_share_sold=-90,
        total_vote_change_per_share_sold=-89,
        solo_control_floor_pct=50.0,
        notes="Post-EGM control transition case",
        source_notes=["Derived from validated Anthony Tan model inputs"],
    )
    print(validate_control_transition_payload(sample))

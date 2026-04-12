from apac_hunter.data.anthony_tan_sample import ANTHONY_PERIODS, ANTHONY_ALIGNED
from apac_hunter.intelligence.control_extraction_schema import (
    build_control_transition_payload,
    validate_control_transition_payload,
)


def get_period(periods: list[dict], label: str) -> dict:
    for p in periods:
        if p["label"] == label:
            return p
    raise ValueError(f"Period not found: {label}")


def build_anthony_payload() -> dict:
    pre = get_period(ANTHONY_PERIODS, "FY2025")
    post = get_period(ANTHONY_PERIODS, "Post-EGM")

    payload = build_control_transition_payload(
        founder_name="Anthony Tan",
        company="Grab Holdings",
        periods=[
            {
                "label": pre["label"],
                "founder_voting_pct": pre["founder_voting_pct"],
                "aligned_voting_pct": pre["aligned_voting_pct"],
                "max_sellable": pre["max_sellable"],
            },
            {
                "label": post["label"],
                "founder_voting_pct": post["founder_voting_pct"],
                "aligned_voting_pct": post["aligned_voting_pct"],
                "max_sellable": post["max_sellable"],
            },
        ],
        share_classes={
            "class_a": {"votes_per_share": 1},
            "class_b": {"votes_per_share": 90},
        },
        founder_holdings={
            "class_a": post.get("founder_class_a_shares", 0),
            "class_b": post.get("founder_class_b_shares", 0),
        },
        aligned_holders=ANTHONY_ALIGNED,
        sell_class="class_b",
        conversion_on_sale_to="class_a",
        founder_vote_change_per_share_sold=-90,
        total_vote_change_per_share_sold=-89,
        solo_control_floor_pct=50.0,
        notes="Validated Anthony Tan control-transition case derived from sample model inputs.",
        source_notes=[
            "Pre-period = FY2025",
            "Post-period = Post-EGM",
            "Sale of Class B converts to Class A",
            "Founder votes fall by 90 per share sold; total vote pool falls by 89",
        ],
    )
    return payload


if __name__ == "__main__":
    payload = build_anthony_payload()
    print("PAYLOAD")
    print(payload)
    print()
    print("VALIDATION")
    print(validate_control_transition_payload(payload))

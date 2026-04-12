from apac_hunter.intelligence.control_model import (
    snapshot,
    max_sellable_shares,
)
from apac_hunter.data.anthony_tan_sample import ANTHONY_PERIODS


def run_case(period: dict, case_name: str, aligned_names: list[str]):
    snap = snapshot(period, "Anthony Tan", aligned_names)
    max_sell_50 = max_sellable_shares(
        period,
        "Anthony Tan",
        aligned_names,
        control_floor_pct=50.0,
        sell_class="class_b",
    )

    print(f"CASE: {case_name}")
    print(f"  Founder voting %: {snap['founder_voting_pct']}")
    print(f"  Aligned voting %: {snap['aligned_voting_pct']}")
    print(f"  Max sellable B shares above 50% floor: {max_sell_50}")
    print("")


def main():
    period = None
    for p in ANTHONY_PERIODS:
        if p["label"] == "Post-EGM":
            period = p
            break

    if period is None:
        raise ValueError("Post-EGM period not found")

    print("ANTHONY TAN — POST-EGM CONTROL SCENARIOS\n")

    run_case(
        period,
        "Anthony only",
        ["Anthony Tan"],
    )

    run_case(
        period,
        "Anthony + Ming Maa + Hooi Ling Tan aligned",
        ["Anthony Tan", "Ming Maa", "Hooi Ling Tan"],
    )


if __name__ == "__main__":
    main()

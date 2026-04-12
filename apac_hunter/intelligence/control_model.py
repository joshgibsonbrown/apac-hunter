from copy import deepcopy


def total_economic_shares(period: dict) -> int:
    return int(period["class_a_outstanding"]) + int(period["class_b_outstanding"])


def total_votes(period: dict) -> int:
    return (
        int(period["class_a_outstanding"]) * int(period["votes_per_class_a"])
        + int(period["class_b_outstanding"]) * int(period["votes_per_class_b"])
    )


def holder_economic_shares(holder: dict) -> int:
    return int(holder.get("class_a", 0)) + int(holder.get("class_b", 0))


def holder_votes(holder: dict, period: dict) -> int:
    return (
        int(holder.get("class_a", 0)) * int(period["votes_per_class_a"])
        + int(holder.get("class_b", 0)) * int(period["votes_per_class_b"])
    )


def economic_pct(holder: dict, period: dict) -> float:
    total = total_economic_shares(period)
    if total == 0:
        return 0.0
    return holder_economic_shares(holder) / total * 100


def voting_pct(holder: dict, period: dict) -> float:
    votes_total = total_votes(period)
    if votes_total == 0:
        return 0.0
    return holder_votes(holder, period) / votes_total * 100


def aligned_votes(period: dict, include_names: list[str]) -> int:
    total = 0
    for holder in period["holders"]:
        if holder["name"] in include_names:
            total += holder_votes(holder, period)
    return total


def aligned_voting_pct(period: dict, include_names: list[str]) -> float:
    votes_total = total_votes(period)
    if votes_total == 0:
        return 0.0
    return aligned_votes(period, include_names) / votes_total * 100


def get_holder(period: dict, name: str) -> dict | None:
    for holder in period["holders"]:
        if holder["name"] == name:
            return holder
    return None


def apply_founder_sale(
    period: dict,
    founder_name: str,
    shares_to_sell: int,
    sell_class: str = "class_b",
    sale_mechanics: dict | None = None,
) -> dict:
    updated = deepcopy(period)
    founder = get_holder(updated, founder_name)
    if founder is None:
        raise ValueError(f"Founder '{founder_name}' not found")

    if sell_class not in {"class_a", "class_b"}:
        raise ValueError("sell_class must be 'class_a' or 'class_b'")

    current = int(founder.get(sell_class, 0))
    if shares_to_sell < 0:
        raise ValueError("shares_to_sell cannot be negative")
    if shares_to_sell > current:
        raise ValueError(
            f"Cannot sell {shares_to_sell} shares; founder only has {current} {sell_class}"
        )

    founder[sell_class] = current - shares_to_sell

    mechanics = sale_mechanics or {}
    converts_to = mechanics.get("converts_to")
    buyer_gets_converted_shares = mechanics.get("buyer_gets_converted_shares", True)

    if converts_to and converts_to != sell_class:
        sold_outstanding_key = f"{sell_class}_outstanding"
        converted_outstanding_key = f"{converts_to}_outstanding"

        if sold_outstanding_key not in updated or converted_outstanding_key not in updated:
            raise ValueError("Sale mechanics reference unknown share classes")

        updated[sold_outstanding_key] = int(updated[sold_outstanding_key]) - shares_to_sell

        if buyer_gets_converted_shares:
            updated[converted_outstanding_key] = int(updated[converted_outstanding_key]) + shares_to_sell

    return updated


def proceeds(shares_to_sell: int, share_price: float) -> float:
    return float(shares_to_sell) * float(share_price)


def max_sellable_shares(
    period: dict,
    founder_name: str,
    aligned_names: list[str],
    control_floor_pct: float = 50.0,
    sell_class: str = "class_b",
    sale_mechanics: dict | None = None,
) -> int:
    founder = get_holder(period, founder_name)
    if founder is None:
        raise ValueError(f"Founder '{founder_name}' not found")

    low = 0
    high = int(founder.get(sell_class, 0))
    best = 0

    while low <= high:
        mid = (low + high) // 2
        updated = apply_founder_sale(
            period,
            founder_name,
            mid,
            sell_class=sell_class,
            sale_mechanics=sale_mechanics,
        )
        pct = aligned_voting_pct(updated, aligned_names)

        if pct >= control_floor_pct:
            best = mid
            low = mid + 1
        else:
            high = mid - 1

    return best


def snapshot(period: dict, founder_name: str, aligned_names: list[str]) -> dict:
    founder = get_holder(period, founder_name)
    if founder is None:
        raise ValueError(f"Founder '{founder_name}' not found")

    return {
        "period_label": period["label"],
        "founder_name": founder_name,
        "founder_economic_pct": round(economic_pct(founder, period), 2),
        "founder_voting_pct": round(voting_pct(founder, period), 2),
        "aligned_voting_pct": round(aligned_voting_pct(period, aligned_names), 2),
        "total_votes": total_votes(period),
        "total_economic_shares": total_economic_shares(period),
    }


if __name__ == "__main__":
    from apac_hunter.data.anthony_tan_sample import ANTHONY_TAN_SAMPLE, ANTHONY_ALIGNED

    snap = snapshot(ANTHONY_TAN_SAMPLE, "Anthony Tan", ANTHONY_ALIGNED)
    print("SNAPSHOT")
    print(snap)

    max_sell_50 = max_sellable_shares(
        ANTHONY_TAN_SAMPLE,
        "Anthony Tan",
        ANTHONY_ALIGNED,
        control_floor_pct=50.0,
        sell_class="class_b",
    )
    print("\nMAX SELLABLE SHARES ABOVE 50% CONTROL FLOOR")
    print(max_sell_50)

    max_sell_40 = max_sellable_shares(
        ANTHONY_TAN_SAMPLE,
        "Anthony Tan",
        ANTHONY_ALIGNED,
        control_floor_pct=40.0,
        sell_class="class_b",
    )
    print("\nMAX SELLABLE SHARES ABOVE 40% CONTROL FLOOR")
    print(max_sell_40)

    print("\nPROCEEDS AT US$5.00 (50% FLOOR)")
    print(round(proceeds(max_sell_50, 5.0), 2))

    updated = apply_founder_sale(
        ANTHONY_TAN_SAMPLE,
        "Anthony Tan",
        min(5000000, max_sell_50),
        sell_class="class_b",
    )
    print("\nALIGNED VOTING % AFTER SELLING 5,000,000 CLASS B SHARES")
    print(round(aligned_voting_pct(updated, ANTHONY_ALIGNED), 2))

def analyse_control_transition(pre, post):
    """
    Takes two snapshots (pre and post event) and produces
    a structured, reusable insight.
    """

    voting_delta = post["founder_voting_pct"] - pre["founder_voting_pct"]
    sell_delta = post["max_sellable"] - pre["max_sellable"]

    return {
        "control_shift": {
            "pre_voting_pct": pre["founder_voting_pct"],
            "post_voting_pct": post["founder_voting_pct"],
            "delta": voting_delta,
            "independent_control_achieved": post["founder_voting_pct"] >= 50,
        },
        "liquidity_unlock": {
            "pre_sellable": pre["max_sellable"],
            "post_sellable": post["max_sellable"],
            "delta": sell_delta,
            "multiple": round(post["max_sellable"] / pre["max_sellable"], 2)
            if pre["max_sellable"] > 0 else None,
        },
        "interpretation": build_interpretation(pre, post, voting_delta, sell_delta)
    }


def build_interpretation(pre, post, voting_delta, sell_delta):
    if post["founder_voting_pct"] >= 50 and pre["founder_voting_pct"] < 50:
        return (
            "Founder transitioned from dependent to independent control. "
            "However, this should not be treated as a clean liquidity unlock. Any monetisation decision remains constrained by confirmation that the EGM mechanics are legally effective and by the need to preserve adequate control through any Grab-GoTo merger scenario."
        )

    if sell_delta > 0:
        return (
            "Governance change increased liquidity capacity while preserving control."
        )

    return (
        "No meaningful change in control or liquidity capacity."
    )

from pprint import pprint

from apac_hunter.data.anthony_tan_sample import ANTHONY_PERIODS, ANTHONY_ALIGNED
from apac_hunter.intelligence.template_router import choose_template, run_template


def main():
    trigger_type = "Voting structure change"

    template = choose_template(trigger_type)

    fy2025 = next(p for p in ANTHONY_PERIODS if p["label"] == "FY2025")
    post_egm = next(p for p in ANTHONY_PERIODS if p["label"] == "Post-EGM")

    result = run_template(
        template,
        pre_period=fy2025,
        post_period=post_egm,
        founder_name="Anthony Tan",
        aligned_names=ANTHONY_ALIGNED,
        control_floor_pct=50.0,
        sell_class="class_b",
    )

    print("CHOSEN TEMPLATE:", template)
    print("")
    pprint(result)


if __name__ == "__main__":
    main()

from apac_hunter.data.anthony_tan_sample import ANTHONY_PERIODS, ANTHONY_ALIGNED
from apac_hunter.intelligence.scenario_overrides import ANTHONY_TAN_POST_EGM_SCENARIO


SCENARIO_REGISTRY = {
    'Anthony Tan': {
        'template_type': 'control_transition',
        'pre_period_label': 'FY2025',
        'post_period_label': 'Post-EGM',
        'periods': ANTHONY_PERIODS,
        'aligned_names': ANTHONY_ALIGNED,
        'sell_class': 'class_b',
        'control_floor_pct': 50.0,
        'scenario': ANTHONY_TAN_POST_EGM_SCENARIO,
    }
}


def get_registered_scenario(individual_name: str, template_type: str) -> dict | None:
    cfg = SCENARIO_REGISTRY.get(individual_name)
    if not cfg:
        return None
    if cfg.get('template_type') != template_type:
        return None
    return cfg

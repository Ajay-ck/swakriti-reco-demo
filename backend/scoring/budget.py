import re

from nlp.taxonomy import BUDGET_SOFT_BUFFER

BUDGET_LABEL_MAP = {
    "Under Rs.1,500": {"min": 0, "max": 1500},
    "Rs.1,500-3,000": {"min": 1500, "max": 3000},
    "Rs.3,000-6,000": {"min": 3000, "max": 6000},
    "Rs.6,000-12,000": {"min": 6000, "max": 12000},
    "Rs.12,000+": {"min": 12000, "max": None},
}


def normalize_budget(user_budget):
    if not user_budget:
        return None

    if isinstance(user_budget, dict):
        min_value = user_budget.get("min")
        max_value = user_budget.get("max")
        if min_value is None and max_value is None:
            return None
        if min_value is not None:
            min_value = int(min_value)
        if max_value is not None:
            max_value = int(max_value)
        return {"min": min_value, "max": max_value}

    if isinstance(user_budget, (int, float)):
        value = int(user_budget)
        return {"min": value, "max": value}

    if isinstance(user_budget, str):
        value = user_budget.strip()
        if not value:
            return None

        if value in BUDGET_LABEL_MAP:
            return BUDGET_LABEL_MAP[value]

        ranges = re.findall(r"(\d{2,6})", value)
        if len(ranges) >= 2:
            low = int(ranges[0])
            high = int(ranges[-1])
            if low <= high:
                return {"min": low, "max": high}

        single_match = re.search(r"(\d{2,6})", value)
        if single_match:
            value_int = int(single_match.group(1))
            return {"min": value_int, "max": value_int}

    return None


def score_budget(user_budget, product_price):
    budget_range = normalize_budget(user_budget)
    if not budget_range:
        return 5.0

    min_value = budget_range.get("min")
    max_value = budget_range.get("max")

    if min_value is not None and max_value is not None:
        if min_value <= product_price <= max_value:
            return 10.0
        if min_value * 0.9 <= product_price <= max_value * BUDGET_SOFT_BUFFER:
            return 5.0
        return 0.0

    if max_value is not None:
        if product_price <= max_value:
            return 10.0
        if product_price <= max_value * BUDGET_SOFT_BUFFER:
            return 5.0
        return 0.0

    if min_value is not None:
        if product_price >= min_value:
            return 10.0
        return 0.0
    
from nlp.taxonomy import FABRIC_COMFORT_MATRIX, FABRIC_BOOST_RULES


def score_fabric_comfort(user_comfort, product_fabric, is_wedding_formal=False):
    if not user_comfort or user_comfort == "none":
        return 5.0
    m = FABRIC_COMFORT_MATRIX.get(user_comfort, {})
    if product_fabric in m.get(10, set()):
        return 10.0
    if product_fabric in m.get(5, set()):
        return 5.0
    if product_fabric in m.get(0, set()):
        if user_comfort == "festive" and is_wedding_formal:
            return 5.0
        return 0.0
    return 5.0


def apply_fabric_boost(user_occasion, product_fabric, base_score):
    if user_occasion and product_fabric in FABRIC_BOOST_RULES.get(user_occasion, set()):
        return max(0.0, min(10.0, base_score + 2))
    return base_score
def score_age(user_age_group, product_age_tags):
    if not user_age_group:
        return 5.0
    product_age_tags = product_age_tags or []
    if user_age_group in product_age_tags:
        return 10.0
    if "universal_ageless" in product_age_tags:
        return 10.0
    return 5.0  # soft signal, never hard-block
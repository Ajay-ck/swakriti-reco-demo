from nlp.taxonomy import BODY_TYPE_SILHOUETTES


def score_body_type(user_body_type, product_silhouettes, product_body_type_fit=None):
    if not user_body_type:
        return 5.0
    product_silhouettes = set(product_silhouettes or [])
    product_body_type_fit = product_body_type_fit or []

    if "universal" in product_body_type_fit:
        return 5.0

    flattering = BODY_TYPE_SILHOUETTES.get(user_body_type, set())
    if product_silhouettes & flattering or user_body_type in product_body_type_fit:
        return 10.0
    return 5.0
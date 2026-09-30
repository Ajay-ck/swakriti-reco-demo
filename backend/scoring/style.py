from nlp.catalog_labels import normalize_style
from nlp.taxonomy import STYLE_ADJACENCY


def score_style(user_style, product_style):
    user_style = normalize_style(user_style)
    product_style = normalize_style(product_style)
    if not user_style:
        return 5.0
    if product_style == user_style:
        return 10.0
    if product_style in STYLE_ADJACENCY.get(user_style, set()):
        return 5.0
    return 0.0
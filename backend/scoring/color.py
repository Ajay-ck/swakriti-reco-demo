from nlp.preferences import COLOR_FAMILIES, canonical, value_matches
def _family(color_name):
    color=canonical("color",color_name)
    return next((key for key,vals in COLOR_FAMILIES.items() if color in vals),None)
def score_color(user_color, product_color):
    if not user_color or not product_color: return 0.0
    if value_matches("color",user_color,product_color): return 10.0
    return 5.0 if _family(user_color) is not None and _family(user_color)==_family(product_color) else 0.0

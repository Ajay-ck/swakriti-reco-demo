from nlp.taxonomy import SKIN_TONE_BEST_FAMILIES, NEUTRAL_FAMILY


def score_skin_tone(user_skin_tone, product_color_family, product_high_contrast_festive=False):
    if not user_skin_tone:
        return 5.0
    if product_color_family == NEUTRAL_FAMILY:
        return 5.0

    best = SKIN_TONE_BEST_FAMILIES.get(user_skin_tone, set())
    if product_color_family in best:
        return 10.0
    if product_high_contrast_festive and user_skin_tone in ("medium", "tan", "deep"):
        return 10.0
    return 5.0
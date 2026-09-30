from nlp.taxonomy import OCCASION_HARD_BLOCK


def passes_hard_filters(user_prefs, product):
    user_occasion = user_prefs.get("occasion")
    product_occasion = product.get("occasion_primary")
    height_band = user_prefs.get("height_band") or user_prefs.get("height_cm_or_label")
    product_height_bands = product.get("height_band_fit") or []

    if user_occasion and product_occasion in OCCASION_HARD_BLOCK.get(user_occasion, set()):
        return False
    if user_occasion == "kidswear" and "kidswear" not in (product.get("occasion_tags") or []):
        return False

    if height_band:
        height_band = str(height_band).strip().lower()
        allowed_bands = {str(h).strip().lower() for h in product_height_bands}
        if allowed_bands and height_band not in allowed_bands and height_band not in {"petite", "regular", "tall"}:
            return False
        if allowed_bands and height_band in {"petite", "regular", "tall"} and height_band not in allowed_bands:
            return False

    return True
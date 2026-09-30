"""Legacy 50/30/20 formula; not used by ranking v2. See nlp/rule_engine.py."""
def combine_scores(occasion, budget, style, color, comfort, body, skin, age,
                    seasonal, popular, trend_color, trend_silhouette, best_fabric):
    user_input = occasion * 0.35 + budget * 0.25 + style * 0.20 + color * 0.15 + comfort * 0.05
    characteristics = body * 0.4286 + skin * 0.3571 + age * 0.2143
    business = (
        seasonal * 0.30 + popular * 0.25 + trend_color * 0.20
        + trend_silhouette * 0.15 + best_fabric * 0.10
    )
    final = user_input * 0.50 + characteristics * 0.30 + business * 0.20
    return user_input, characteristics, business, final
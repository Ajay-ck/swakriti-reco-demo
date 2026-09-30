OCCASION_TAGS = [
    "casual_daily", "streetwear", "smart_casual", "workwear",
    "festive_pan_india", "wedding_guest", "wedding_bride",
    "kerala_traditional", "avant_garde", "kidswear",
]

STYLE_TAGS = [
    "minimalist", "maximalist", "avant_garde", "indo_western",
    "bohemian", "classic_timeless", "traditional_ethnic", "western",
]

FABRIC_TAGS = [
    "breathable_lightweight", "fluid_drape", "structured_heavyweight",
    "crisp_volumetric", "sensory_hypoallergenic", "rich_festive",
]

BODY_TYPE_TAGS = ["hourglass", "pear", "apple", "rectangle", "universal"]

HEIGHT_TAGS = ["petite", "regular", "tall"]

SKIN_TONE_TAGS = ["fair", "light", "medium", "tan", "deep"]

AGE_TAGS = ["18-25", "26-35", "36-50", "all"]

COMFORT_LEVELS = ["high", "medium", "festive", "none"]

OCCASION_ADJACENCY = {
    "wedding_bride":       {"wedding_guest", "festive_pan_india"},
    "wedding_guest":       {"festive_pan_india", "smart_casual"},
    "festive_pan_india":   {"wedding_guest", "kerala_traditional"},
    "workwear":            {"smart_casual"},
    "smart_casual":        {"workwear", "casual_daily"},
    "casual_daily":        {"streetwear", "smart_casual"},
    "streetwear":          {"casual_daily"},
    "kerala_traditional":  {"festive_pan_india", "wedding_guest"},
    "avant_garde":         {"streetwear"},
    "kidswear":            set(),
}

STYLE_ADJACENCY = {
    "minimalist":         {"classic_timeless"},
    "maximalist":         {"bohemian", "indo_western"},
    "indo_western":       {"traditional_ethnic", "classic_timeless"},
    "avant_garde":        {"bohemian"},
    "classic_timeless":   {"minimalist", "indo_western"},
    "bohemian":           {"maximalist"},
    "traditional_ethnic": {"indo_western"},
}

from nlp.preferences import COLOR_FAMILIES

NEUTRAL_FAMILY = "neutral"

HIGH_CONTRAST_FESTIVE_COLORS = {
    "gold", "red", "vermillion", "maroon", "emerald", "royal purple",
    "ruby", "sapphire", "scarlet",
}

SKIN_TONE_BEST_FAMILIES = {
    "fair":   {"cool", "neutral", "muted_pastel"},
    "light":  {"warm", "neutral", "muted_pastel"},
    "medium": {"warm", "neutral"},
    "tan":    {"warm", "cool", "neon"},
    "deep":   {"cool", "warm", "neon"},
}

FABRIC_COMFORT_MATRIX = {
    "high": {
        10: {"breathable_lightweight", "sensory_hypoallergenic"},
        5:  {"fluid_drape", "crisp_volumetric"},
        0:  {"structured_heavyweight"},
    },
    "medium": {
        10: {"fluid_drape", "breathable_lightweight"},
        5:  {"crisp_volumetric", "rich_festive"},
        0:  {"structured_heavyweight"},
    },
    "festive": {
        10: {"rich_festive", "fluid_drape"},
        5:  {"breathable_lightweight", "crisp_volumetric"},
        0:  set(),
    },
    "none": {10: set(), 5: set(), 0: set()},
}

BODY_TYPE_SILHOUETTES = {
    "hourglass": {"wrap", "cinched_waist", "tailored_blazer", "high_waist_trouser", "corsetry"},
    "pear_triangle": {"a_line_skirt", "structured_shoulders", "boat_neck", "embellished_neckline", "cowl_neck"},
    "inverted_triangle": {"peplum", "wide_leg_trouser", "pleated_skirt", "deep_v_neck", "dropped_waist"},
    "rectangle_athletic": {"ruched", "statement_belt", "ruffles", "tiered_layers", "fit_and_flare"},
    "round_apple": {"empire_waist", "fluid_tunic", "shift_dress", "vertical_panel", "unstructured_layers"},
}

FABRIC_BOOST_RULES = {
    "kidswear": {"breathable_lightweight", "sensory_hypoallergenic"},
    "festive_pan_india": {"rich_festive"},
    "wedding_guest": {"rich_festive"},
    "wedding_bride": {"rich_festive"},
    "casual_daily": {"breathable_lightweight"},
    "streetwear": {"breathable_lightweight"},
    "kerala_traditional": {"breathable_lightweight", "crisp_volumetric"},
}

OCCASION_HARD_BLOCK = {
    "casual_daily": {"wedding_bride", "wedding_guest"},
}

BUDGET_SOFT_BUFFER = 1.10
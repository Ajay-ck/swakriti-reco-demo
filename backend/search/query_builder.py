
from nlp.taxonomy import COLOR_FAMILIES  

COLOUR_LABEL_TO_FAMILY = {
    "Warm tones": "warm",
    "Cool tones": "cool",
    "Neutrals": "neutral",
    "Pastels": "muted_pastel",
    "Bold & rich": "neon",
}


def state_to_gender(state):
    child_gender = state.get("child_gender")
    if child_gender in ["Girl", "Boy"]:
        return child_gender.lower()

    gender = state.get("gender")
    if gender == "Myself (woman)":
        return "female"
    if gender == "Myself (man)":
        return "male"
    return None


def state_to_size(state):
    child_gender = state.get("child_gender")
    if child_gender in ["Girl", "Boy"]:
        size = state.get("size_kids")
    else:
        size = state.get("size")
    if not size or size in ("Not sure",):
        return None
    return size


def state_to_query(state):
    """Build QUERY_1: Clean query from state (removes conversational noise)."""
    parts = []

    # Occasion detail + main occasion
    occasion_detail = (
        state.get("occasion_detail_wedding")
        or state.get("occasion_detail_festival")
        or state.get("occasion_detail_office")
    )
    if occasion_detail:
        parts.append(occasion_detail)

    occasion = state.get("occasion")
    if occasion:
        parts.append(occasion)

    # Intent: extract JUST the product type, skip conversational filler
    # "I want a wedding silk saree for my sisters..." → extract "silk saree"
    intent = state.get("intent")
    if intent:
        if isinstance(intent, list):
            parts.extend(intent)
        elif isinstance(intent, str):
            # Extract product keywords: saree, kurta, lehenga, dress, etc.
            intent_lower = intent.lower()
            products = ["saree", "kurta", "lehenga", "dress", "dupatta", "blouse",
                       "anarkali", "kurti", "suit", "salwar"]
            for product in products:
                if product in intent_lower:
                    parts.append(product)
                    break
            # Also capture fabric if mentioned: silk, cotton, chiffon, etc.
            fabrics = ["silk", "cotton", "chiffon", "crepe", "organza", "georgette"]
            for fabric in fabrics:
                if fabric in intent_lower:
                    parts.append(fabric)

    product_category = state.get("product_category")
    if product_category:
        parts.append(product_category)
    # Style
    style = state.get("style")
    if style:
        parts.append(style)

    # Color
    colours = state.get("colour")
    if colours:
        colour_list = colours if isinstance(colours, list) else [colours]
        for c in colour_list:
            family_key = COLOUR_LABEL_TO_FAMILY.get(c)
            if family_key:
                parts.append(f"{family_key} colour")   # "warm colour" not just "warm"
            else:
                parts.append(c)

    fit = state.get("fit")
    if fit:
        parts.append(fit)

    # Kidswear
    kidswear_priority = state.get("kidswear_priority")
    if kidswear_priority:
        parts.extend(kidswear_priority if isinstance(kidswear_priority, list) else [kidswear_priority])

    child_age_group = state.get("child_age_group")
    if child_age_group:
        parts.append(child_age_group)

    # Avoid colors
    avoid = state.get("avoid_colour")
    if avoid:
        avoid_list = avoid if isinstance(avoid, list) else [avoid]
        avoid_list = [a for a in avoid_list if a and a != "None"]
        if avoid_list:
            parts.append("avoid " + " ".join(avoid_list))

    # Deduplicate while preserving order
    seen = set()
    clean_parts = []
    for p in parts:
        p_lower = str(p).lower()
        if p_lower not in seen:
            seen.add(p_lower)
            clean_parts.append(p)

    return " ".join(str(p) for p in clean_parts if p).strip()


# ---------- Gemini Query Builder ----------
QUERY_BUILD_PROMPT = """You are building a search query for a fashion e-commerce search engine
from a shopper's structured answers below.

Shopper's answers (raw JSON):
{state_json}

Task:
- Convert this into ONE clean, natural search sentence.
- Remove ALL symbols like "/", extra punctuation, and filler words like "only", "not sure".
- If an answer has multiple options separated by "/", pick the most specific/relevant one only,
  don't keep both joined by a slash.
- Keep it short — just the meaningful shopping keywords (occasion, product type, fabric,
  style, color, budget hints, fit).
- Do NOT invent details not present in the answers.
- Do NOT include field names or labels, just plain natural words.

Return ONLY the final sentence as plain text. No JSON, no quotes, no explanation.
"""


def build_clean_query_with_gemini(client, state: dict) -> str:
    """Build a clean search query using Gemini from structured state."""
    import json
    try:
        prompt = QUERY_BUILD_PROMPT.format(state_json=json.dumps(state, indent=2))
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )
        clean_query = response.text.strip()
        # safety: strip any stray quotes/markdown Gemini might add
        clean_query = clean_query.strip('"').strip("`").strip()
        return clean_query
    except Exception as e:
        print(f"[build_clean_query_with_gemini] error: {e}")
        return None
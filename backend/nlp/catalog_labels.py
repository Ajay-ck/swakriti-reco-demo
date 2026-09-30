"""Shared catalog labels for the existing demo pipeline."""
import re

CATEGORY_MAP = {'a line dress': 'dress', 'a line skirt': 'skirt', 'anarkali style dress': 'dress', 'asymmetric hem skirt': 'skirt', 'banarasi silk saree': 'saree', 'bandhani print saree': 'saree', 'bandhgala sherwani': 'sherwani', 'blazer dress': 'dress', 'bodycon dress': 'dress', 'bodycon midi skirt': 'skirt', 'box pleat skirt': 'skirt', 'button down shirt dress': 'dress', 'chikankari cotton kurta': 'kurta', 'chikankari kota saree': 'saree', 'chikankari kurti dress': 'dress', 'cocktail dress': 'dress', 'corset waist dress': 'dress', 'cotton casual shirt': 'shirt', 'cotton chinese collar shirt': 'shirt', 'denim style shirt dress': 'dress', 'denim style skirt': 'skirt', 'empire waist dress': 'dress', 'ethnic kurta pajama set': 'kurta set', 'fit flare dress': 'dress', 'floral sundress': 'dress', 'georgette printed saree': 'saree', 'halter neck dress': 'dress', 'handloom cotton dress': 'dress', 'handloom cotton skirt': 'skirt', 'ikat cotton saree': 'saree', 'ikat print dress': 'dress', 'indo western fusion dress': 'dress', 'kaftan dress': 'dress', 'kanjivaram silk saree': 'saree', 'linen formal blazer': 'blazer', 'linen handloom saree': 'saree', 'maxi dress': 'dress', 'nehru jacket kurta set': 'kurta set', 'off shoulder dress': 'dress', 'party bodycon dress': 'dress', 'pathani suit set': 'suit set', 'pencil skirt': 'skirt', 'peplum dress': 'dress', 'pleated midi skirt': 'skirt', 'puff sleeve fit flare dress': 'dress', 'ruffle hem fit flare dress': 'dress', 'sequin party saree': 'saree', 'sequin party skirt': 'skirt', 'sheath dress': 'dress', 'shift dress': 'dress', 'shirt dress': 'dress', 'skater dress': 'dress', 'slip dress': 'dress', 'tiered maxi dress': 'dress', 'tunic dress': 'dress', 'tussar silk saree': 'saree', 'velvet border saree': 'saree', 'velvet festive blazer': 'blazer', 'wedding silk sherwani': 'sherwani', 'wrap dress': 'dress', 'wrap maxi dress': 'dress', 'wrap skirt': 'skirt', 'zari stripe tussar saree': 'saree'}
OCCASION_MAP = {
 "everyday wear":"casual_daily", "photo shoot":"avant_garde", "party":"smart_casual",
 "formal event":"smart_casual", "wedding guest":"wedding_guest", "festival":"festive_pan_india",
 "birthday":"smart_casual", "vacation":"casual_daily", "office":"workwear",
}
STYLE_MAP = {
 "modern/western":"western", "mix of indian and western":"indo_western",
 "fusion (mixed styles)":"indo_western", "traditional/indian":"traditional_ethnic",
 "traditional":"traditional_ethnic", "indian":"traditional_ethnic",
 "south_indian":"traditional_ethnic", "fusion":"indo_western",
 "classic":"classic_timeless", "modern":"western",
}
def normalize_style(value):
    key=str(value or "").strip().lower()
    return STYLE_MAP.get(key,key) or None

def normalize_category(value):
    key=re.sub(r"[^a-z0-9]+"," ",str(value or "").lower()).strip()
    if key in CATEGORY_MAP: return CATEGORY_MAP[key]
    aliases={"sari":"saree","sarees":"saree","gown":"dress","dresses":"dress","skirts":"skirt","shirts":"shirt"}
    if key in aliases: return aliases[key]
    if key in set(CATEGORY_MAP.values()): return key
    return None

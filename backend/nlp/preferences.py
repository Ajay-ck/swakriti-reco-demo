"""Canonical catalog attributes shared by extraction, filters and ranking."""
import re
import math
from decimal import Decimal, InvalidOperation
from nlp.catalog_labels import normalize_category, normalize_style, OCCASION_MAP

ATTRIBUTE_FIELDS = ("sub_category", "fabric", "color", "occasion", "style", "comfort",
                    "fit", "length", "sleeve", "neckline")
SOURCE_FIELDS = {"sub_category":"sub_category", "fabric":"fabric_category",
                 "color":"specific_color", "style":"style_category", "fit":"fit_type",
                 "length":"length", "sleeve":"sleeve_type", "neckline":"neckline"}
ALIASES = {
    "sub_category":{"anarkali":"anarkali style dress", "anarkali dress":"anarkali style dress",
                    "halter dress":"halter neck dress", "fit and flare dress":"fit flare dress"},
    "color":{"navy":"navy blue", "wine":"wine red", "grey":"gray", "charcoal grey":"charcoal gray"},
    "sleeve":{"full sleeves":"full sleeve","long sleeves":"full sleeve","long sleeve":"full sleeve",
              "short sleeves":"short sleeve","three quarter sleeves":"3 4th sleeve",
              "three quarter sleeve":"3 4th sleeve","no sleeves":"sleeveless"},
    "neckline":{"v neck":"v neck", "halter neck":"halter","round neck":"round"},
    "fit":{"relaxed":"loose and relaxed", "loose":"loose and relaxed",
           "fitted":"fitted tailored","body hugging":"body hugging"},
    "length":{"maxi":"full length","floor length":"full length","mini":"short","midi":"calf length"},
    "comfort":{"comfortable":"high","very comfortable":"high","breathable":"high",
               "lightweight":"high","easy care":"easy care","easy to wash":"easy care"},
    "gender":{"woman":"female","women":"female","womens":"female","man":"male","men":"male","mens":"male"},
    "size":{"free size":"FREE","free":"FREE","medium":"M","small":"S","large":"L",
            "extra small":"XS","extra large":"XL","2xl":"XXL","3xl":"3XL"},
    "body_type":{"pear shaped":"pear","apple shaped":"apple","hourglass shaped":"hourglass",
                 "inverted triangle":"inverted triangle","athletic":"rectangle"},
    "height_band":{"short":"petite","average":"regular"}
}
OCCASION_ALIASES = {
    **{re.sub(r"[^a-z0-9]+", " ", k).strip():v for k,v in OCCASION_MAP.items()},
    "birthday party":"smart_casual", "office party":"smart_casual",
    "wedding":"wedding_guest", "wedding reception":"wedding_guest", "reception":"wedding_guest",
    "wedding guest":"wedding_guest", "bride":"wedding_bride", "bridal":"wedding_bride",
    "holiday":"casual_daily","travel":"casual_daily","daily wear":"casual_daily",
    "casual":"casual_daily","work":"workwear","college":"workwear","festive":"festive_pan_india",
}
COLOR_GROUPS = {
    "blue":{"navy blue","sky blue","blue","royal blue","teal"},
    "red":{"red","wine red","maroon","burgundy"},
    "pink":{"pink","coral pink","blush pink"},
    "green":{"green","emerald green","sage green","olive green","mint green"},
    "yellow":{"yellow","mustard yellow","golden yellow"},
    "gray":{"gray","charcoal gray"},
}
COLOR_FAMILIES = {
    "warm":{"coral pink","mustard yellow","rust orange","wine red","maroon","blush pink",
            "golden yellow","peach","terracotta","amber","copper","apricot","sunset orange"},
    "cool":{"navy blue","sky blue","sage green","emerald green","lavender","olive green",
            "blue","slate blue","ice blue","teal","purple","grape","indigo","mint green"},
    "neutral":{"beige","white","black","charcoal gray","gray","cream","ivory","taupe",
               "greige","stone","silver gray","ash gray","brown","sand"},
}

class PreferenceError(ValueError):
    """Request needs clarification; never quietly discard an explicit condition."""

def words(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

def canonical(field, value):
    key = words(value)
    if field == "occasion":
        if key in OCCASION_ALIASES: return OCCASION_ALIASES[key]
        return key.replace(" ", "_")
    if field == "style":
        return normalize_style(str(value).lower()) or key
    if field == "category":
        return normalize_category(value) or key
    if field == "size":
        return ALIASES["size"].get(key, str(value).strip().upper())
    return ALIASES.get(field, {}).get(key, key)

def values(value):
    if value is None: return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v is not None and str(v).strip()]
    return [str(value)] if str(value).strip() else []

def attributes(product):
    if "attributes" in product:
        return product["attributes"]
    result = {}
    for field, source in SOURCE_FIELDS.items():
        result[field] = sorted(set(canonical(field,v) for v in values(product.get(source)) if words(v)))
    result["occasion"] = sorted(set(canonical("occasion",v) for v in
        values(product.get("occasion_tags")) + values(product.get("occasion_primary")) if words(v)))
    comfort = []
    if words(product.get("comfort_level")) == "high":
        comfort.append("high")
    if words(product.get("comfort_level")) in {"high","medium"}:
        comfort.append("medium")
    if words(product.get("care_difficulty")) == "low":
        comfort.append("easy care")
    result["comfort"] = comfort
    return result

def value_matches(field, wanted, actual):
    wanted, actual = canonical(field,wanted), canonical(field,actual)
    if wanted == actual: return True
    if field == "color":
        return actual in COLOR_GROUPS.get(wanted, set()) or actual in COLOR_FAMILIES.get(wanted, set())
    # A broad garment name may match a more specific subtype; never the reverse.
    if field == "sub_category" and wanted in {"maxi dress","wrap dress","a line dress","saree","kurta","dress","skirt"}:
        tokens = wanted.split()
        actual_tokens = actual.split()
        return all(t in actual_tokens for t in tokens)
    return False

def field_match(field, requested, actual):
    return any(value_matches(field,w,a) for w in requested for a in actual)

def price_minor(value):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
            raise ValueError()
        return int(number * 100)
    except (InvalidOperation, ValueError):
        raise PreferenceError("Price/budget must be a nonnegative number with at most two decimal places.")

def validate_budget(budget):
    if budget is None: return None
    if not isinstance(budget,dict): raise PreferenceError("Budget must have min/max bounds.")
    try:
        result = {k:float(Decimal(str(budget[k]))) if budget.get(k) is not None else None for k in ("min","max")}
    except (InvalidOperation, ValueError, TypeError):
        raise PreferenceError("Budget must contain numeric bounds.")
    for v in result.values():
        if v is not None: price_minor(v)
    if result["min"] is not None and result["max"] is not None and result["min"]>result["max"]:
        raise PreferenceError("Minimum budget is greater than maximum budget.")
    return result if any(v is not None for v in result.values()) else None

def eligible_variants(product, prefs):
    variants=product.get("variants")
    if variants is None:
        raise PreferenceError("Index is missing variant inventory. Rebuild the index.")
    budget=prefs.get("budget") or {}
    wanted_size=canonical("size",prefs["size"]) if prefs.get("size") else None
    good=[]
    for v in variants:
        if not v.get("is_active") or not v.get("stock_known",True) or v.get("inventory_qty",0)<=0: continue
        if wanted_size and canonical("size",v.get("size"))!=wanted_size: continue
        price=v.get("price_minor")
        if price is None: continue
        if budget.get("min") is not None and price<price_minor(budget["min"]): continue
        if budget.get("max") is not None and price>price_minor(budget["max"]): continue
        good.append(v)
    return good

def check_hard_filters(product, prefs):
    if not product.get("is_active") or not product.get("in_stock"): return False
    for field in ("gender","category"):
        if prefs.get(field) and canonical(field,product.get(field))!=canonical(field,prefs[field]): return False
    if not eligible_variants(product,prefs): return False
    attrs=attributes(product)
    for field, wanted in prefs.get("must_have",{}).items():
        if not field_match(field,wanted,attrs.get(field,[])): return False
    for field, forbidden in prefs.get("exclude",{}).items():
        if field_match(field,forbidden,attrs.get(field,[])): return False
        # Unknown data cannot certify an explicit exclusion.
        if not attrs.get(field): return False
    return True

def vocabulary(products):
    result={field:set() for field in ATTRIBUTE_FIELDS}
    for product in products:
        for field,vals in attributes(product).items():
            if field in result: result[field].update(vals)
    return {k:sorted(v) for k,v in result.items()}

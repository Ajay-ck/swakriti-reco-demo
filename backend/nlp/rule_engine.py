"""Explicit-match priority followed by query-aware Python scoring (0..100)."""
import json
import math
from pathlib import Path
from nlp.preferences import attributes, canonical, field_match, eligible_variants, check_hard_filters
POLICY=json.loads((Path(__file__).resolve().parents[1]/"scoring/ranking_policy.json").read_text(encoding="utf-8"))

def validate_policy(policy):
    p=policy["personalization"];b=policy["business"];r=policy["relevance"]
    checks=[
        0 <= p["body_weight"] <= .06 and 0 <= p["height_weight"] <= .04,
        0 <= b["max_weight"] <= .05,
        0 < b["relevance_band_width"] <= 1,
        all(0 <= r[k] <= 1 for k in ("specific_attribute_weight","broad_attribute_weight")),
        r["rank_decay"] > 0,
        all(math.isfinite(w) and w>=0 for w in policy["attribute_weights"].values()),
        sum(policy["attribute_weights"].values()) > 0,
        abs(sum(b["metric_weights"].values())-1) < 1e-8,
    ]
    if not all(checks): raise ValueError("Invalid ranking policy or weighting caps")
validate_policy(POLICY)

def active_weights(prefs, policy=POLICY):
    personal=policy["personalization"]
    body=personal["body_weight"] if personal["body_enabled"] and prefs.get("body_type") else 0.
    height=personal["height_weight"] if personal["height_enabled"] and prefs.get("height_band") else 0.
    business=policy["business"]["max_weight"] if policy["business"]["enabled"] else 0.
    return {"relevance":1-body-height-business,"body":body,"height":height,
            "personalization":body+height,"business":business}

def _personal_match(product, field, wanted):
    if not wanted or (product.get("personalization_evidence") or {}).get("verified") is not True: return 0.
    catalog_field={"body_type":"body_type_fit","height_band":"height_band_fit"}[field]
    return float(canonical(field,wanted) in {canonical(field,v) for v in product.get(catalog_field,[])})

def _business_score(product, policy):
    evidence=product.get("business_evidence") or {}
    if evidence.get("verified") is not True or not evidence.get("source") or not evidence.get("as_of"): return 0.
    score=0.
    for field,weight in policy["business"]["metric_weights"].items():
        value=evidence.get(field)
        if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and 0<=value<=1:
            score+=weight*value
    return score

def score_product(user_prefs, product, policy=POLICY):
    if not check_hard_filters(product,user_prefs):
        return {"sku_id":product.get("sku_id"),"eliminated":True,"final_score":-1}
    attrs=attributes(product)
    requested=dict(user_prefs.get("requested_attributes") or {})
    for field,wanted in (user_prefs.get("must_have") or {}).items(): requested.setdefault(field,wanted)
    matches={};unknown=[];misses=[]
    for field,wanted in requested.items():
        if not wanted: continue
        actual=attrs.get(field,[])
        matches[field]=float(field_match(field,wanted,actual))
        if not actual: unknown.append(field)
        elif not matches[field]: misses.append(field)
    weights=policy["attribute_weights"]
    detailed=[f for f in policy["detail_fields"] if f in matches]
    raw_weights={f:(weights["details"]/len(detailed) if f in detailed else weights.get(f,0.)) for f in matches}
    denominator=sum(raw_weights.values())
    structured=sum(matches[f]*w for f,w in raw_weights.items())/denominator if denominator else None
    rank=max(1,product.get("retrieval_rank",1))
    semantic=1./(1.+policy["relevance"]["rank_decay"]*(rank-1))
    specific=any(f in requested for f in ("sub_category","fabric","color","neckline","sleeve","length","fit"))
    attribute_weight=(policy["relevance"]["specific_attribute_weight"] if specific else
                      policy["relevance"]["broad_attribute_weight"]) if structured is not None else 0.
    relevance=attribute_weight*(structured or 0.)+(1-attribute_weight)*semantic
    active=active_weights(user_prefs,policy)
    body=_personal_match(product,"body_type",user_prefs.get("body_type"))
    height=_personal_match(product,"height_band",user_prefs.get("height_band"))
    business=_business_score(product,policy) if active["business"] else 0.
    total=active["relevance"]*relevance+active["body"]*body+active["height"]*height+active["business"]*business
    tier=(2 if all(v==1 for v in matches.values()) else 1 if any(matches.values()) else 0) if matches else 1
    group=("complete" if tier==2 else "partial" if tier==1 else "broader") if matches else "relevance"
    band=math.floor(relevance/policy["business"]["relevance_band_width"]) if active["business"] else 0
    return {"sku_id":product.get("sku_id"),"eliminated":False,"final_score":round(total*100,4),
        "match_tier":tier,"match_group":group,"relevance_band":band,
        "retrieval_rank":rank,"retrieval_score":product.get("retrieval_score"),
        "relevance_score":round(relevance*100,4),
        "structured_score":None if structured is None else round(structured*100,4),
        "semantic_rank_score":round(semantic*100,4),"attribute_scores":matches,
        "matched_attributes":[f for f,v in matches.items() if v==1],
        "unmatched_attributes":misses,"unknown_attributes":unknown,"ranking_weights":active,
        "attribute_weights":{f:w/denominator for f,w in raw_weights.items()} if denominator else {},
        "score_components":{"relevance":active["relevance"]*relevance*100,
            "body":active["body"]*body*100,"height":active["height"]*height*100,"business":active["business"]*business*100},
        "business_score":business*100,"matched_variants":eligible_variants(product,user_prefs),
        "explanation":("Matches all stated product preferences." if group=="complete" else
            "Alternative; differs on: "+", ".join(misses+unknown) if matches else
            "Ranked by query relevance; no unstated preferences were assumed.")}

def rank_products(user_prefs, products, top_k=5, policy=POLICY):
    scored=[score_product(user_prefs,p,policy) for p in products]
    scored=[p for p in scored if not p["eliminated"]]
    scored.sort(key=lambda p:(p["match_tier"],p["relevance_band"],p["final_score"],-p["retrieval_rank"]),reverse=True)
    for i,p in enumerate(scored[:top_k],1):
        label={"complete":"Complete match","partial":"Partial-match alternative",
               "broader":"Broader alternative","relevance":"Closest match"}[p["match_group"]]
        p["rank_label"]=f"#{i} {label}";p["rank"]=i
    return scored[:top_k]

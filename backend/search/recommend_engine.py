import hashlib
import re
import pandas as pd
import os
import threading

from fastembed import TextEmbedding
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, SparseVectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, MatchAny, Range,
    SparseVector, Prefetch, FusionQuery, Fusion, Nested, NestedCondition,
)

from erp.erp_fetch import fetch_products_from_erp, fetch_single_product
from erp.excel_fetch import fetch_products_from_excel, fetch_single_product_excel

from nlp.tag_extractor import extract_tags
from nlp.rule_engine import rank_products, POLICY
from nlp.preferences import attributes, check_hard_filters, eligible_variants, PreferenceError, validate_budget, price_minor, canonical, vocabulary, field_match
from scoring.budget import normalize_budget
from nlp.taxonomy import COLOR_FAMILIES

DATA_SOURCE = os.environ.get("DATA_SOURCE", "excel")

COLLECTION = "skus"

dense_model = TextEmbedding("BAAI/bge-small-en-v1.5")
sparse_model = SparseTextEmbedding("Qdrant/bm25")

client = QdrantClient(
    url=os.environ.get("QDRANT_URL"),
    api_key=os.environ.get("QDRANT_API_KEY"),
    timeout=60,
)

_model_lock = threading.Lock()


def get_vector_db_status():
    collection_exists = client.collection_exists(COLLECTION)
    count = 0
    if collection_exists:
        try:
            count = client.count(collection_name=COLLECTION).count
        except Exception:
            count = 0
    return {
        "collection": COLLECTION,
        "exists": collection_exists,
        "count": count,
    }


def sku_to_point_id(sku):
    if isinstance(sku, int):
        return sku
    return int(hashlib.md5(str(sku).encode("utf-8")).hexdigest()[:12], 16)


def _fallback_dense_text(product: dict) -> str:
    occasion_tags = product.get("occasion_tags") or []
    body_type_fit = product.get("body_type_fit") or []
    skin_tone_match = product.get("skin_tone_match") or []
    age_group_fit = product.get("age_tags") or []
    color_family = product.get("color_family") or []
    return " ".join(filter(None, [
        product.get("name"),
        product.get("item_group"),
        product.get("brand"),
        product.get("gender"),
        product.get("sub_category"),
        product.get("collection_name"),
        product.get("style_category"),
        product.get("silhouette"),
        product.get("fit_type"),
        product.get("fabric_category"),
        product.get("specific_color"),
        product.get("pattern"),
        ", ".join(occasion_tags),
        ", ".join(body_type_fit),
        ", ".join(skin_tone_match),
        ", ".join(age_group_fit),
        ", ".join([str(v) for v in color_family if v]),
    ]))


def _fallback_sparse_text(product: dict) -> str:
    return " ".join(filter(None, [
        product.get("embedding_text_sparse"),
        product.get("style_category"),
        product.get("silhouette"),
        product.get("fit_type"),
        product.get("fabric_category"),
        product.get("specific_color"),
        product.get("pattern"),
        product.get("occasion_primary"),
        ", ".join(product.get("occasion_tags") or []),
        ", ".join(product.get("body_type_fit") or []),
        ", ".join(product.get("skin_tone_match") or []),
    ])).strip()


def _dense_text(product: dict) -> str:
    return product.get("embedding_text_dense") or _fallback_dense_text(product)


def _sparse_text(product: dict) -> str:
    return product.get("embedding_text_sparse") or _fallback_sparse_text(product)


def _to_direct_image_url(url: str) -> str:
    """Convert a Google Drive 'view' link into a directly-loadable image URL."""
    if not url:
        return ""
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        file_id = match.group(1)
        return f"https://lh3.googleusercontent.com/d/{file_id}"
    return url


def update_single_product(item_code: str):
    """
    Incremental update: fetch ONE product from the configured source,
    re-embed it, and upsert just that point into Qdrant.
    """
    product = fetch_single_product_excel(item_code) if DATA_SOURCE == "excel" else fetch_single_product(item_code)
    if not product:
        print(f"[update_single_product] Item {item_code} not found in the configured source.")
        return False

    sizes_str = ", ".join(product.get("available_sizes", []))
    occasion_tags = product.get("occasion_tags", []) or []
    body_type_fit = product.get("body_type_fit", []) or []
    skin_tone_match = product.get("skin_tone_match", []) or []
    age_group_fit = product.get("age_tags", []) or []
    color_family = product.get("color_family") or []
    silhouette = product.get("silhouette")
    dense_text = _dense_text(product)
    sparse_text = _sparse_text(product)

    with _model_lock:
        dense_vec = list(dense_model.embed([dense_text]))[0].tolist()
        sparse_vec = list(sparse_model.embed([sparse_text]))[0]

    point = PointStruct(
        id=sku_to_point_id(product["sku_id"]),
        vector={
            "dense": dense_vec,
            "sparse": SparseVector(
                indices=sparse_vec.indices.tolist(),
                values=sparse_vec.values.tolist(),
            ),
        },
        payload={
            "sku_id": product.get("sku_id"),
            "sku_codes": product.get("sku_codes", []),
            "variants": product.get("variants", []),
            "business_evidence": product.get("business_evidence") or {},
            "personalization_evidence": product.get("personalization_evidence") or {},
            "product_name": product.get("name"),
            "category": str(product.get("item_group", "")).strip().lower(),
            "sub_category": product.get("sub_category"),
            "collection_name": product.get("collection_name"),
            "gender": str(product.get("gender", "")).strip().lower(),
            "brand": product.get("brand"),
            "price": float(product.get("price", 0)),
            "budget_tier": product.get("budget_tier"),
            "sizes": [s.strip().upper() for s in sizes_str.split(",") if s.strip()],
            "in_stock": product.get("stock_count", 0) > 0,
            "is_active": True,
            "is_new_arrival": product.get("is_new_arrival", False),
            "stock_count": product.get("stock_count", 0),

            "specific_color": product.get("specific_color"),
            "secondary_colors": ", ".join(color_family[1:]) if isinstance(color_family, list) else "",
            "color_family": str(product.get("color_family", "")).strip().lower() or None,
            "pattern": product.get("pattern"),
            "style_category": product.get("style_category"),
            "silhouette": product.get("silhouette"),
            "silhouettes": [silhouette] if silhouette else [],
            "fit_type": product.get("fit_type"),
            "length": product.get("length"),
            "sleeve_type": product.get("sleeve_type"),
            "neckline": product.get("neckline"),
            "fabric_category": product.get("fabric_category"),
            "fabric_weight": product.get("fabric_weight"),
            "breathability": product.get("breathability"),
            "stretch": product.get("stretch"),
            "texture": product.get("texture"),
            "care_difficulty": product.get("care_difficulty"),
            "comfort_level": product.get("comfort_level"),
            "weather_suitability": product.get("weather_suitability"),
            "season": product.get("season"),
            "occasion_primary": occasion_tags[0] if occasion_tags else None,
            "occasion_tags": occasion_tags,
            "occasion_intensity": product.get("occasion_intensity"),
            "dress_code": product.get("dress_code"),
            "indoor_outdoor": product.get("indoor_outdoor"),
            "trend_level": product.get("trend_level"),
            "statement_level": product.get("statement_level"),
            "minimal_maximal": product.get("minimal_maximal"),
            "body_type_fit": body_type_fit,
            "skin_tone_match": skin_tone_match,
            "age_tags": age_group_fit,
            "height_band_fit": product.get("height_band_fit", []),
            "petite_friendly": product.get("petite_friendly", False),
            "plus_size_friendly": product.get("plus_size_friendly", False),
            "alteration_available": product.get("alteration_available", False),
            "wedding_suitability": product.get("wedding_suitability", False),
            "wedding_function": product.get("wedding_function"),
            "travel_friendly": product.get("travel_friendly", False),
            "layer_friendly": product.get("layer_friendly", False),
            "premium_flag": product.get("premium_flag", False),
            "bestseller_flag": product.get("bestseller_flag", False),
            "trending_flag": product.get("trending_flag", False),
            "limited_edition": product.get("limited_edition", False),
            "sale_item": product.get("sale_item", False),
            "rating": product.get("rating"),
            "image_url": product.get("image_url"),
            "back_image_url": product.get("back_image_url"),
            "embedding_text_dense": dense_text,
            "embedding_text_sparse": sparse_text,

            "trend_score": product.get("trend_score"),
            "bestseller_score": product.get("bestseller_score"),
            "margin_score": product.get("margin_score"),
            "inventory_urgency": product.get("inventory_urgency"),
        },
    )

    point.payload['attributes'] = attributes(point.payload)
    client.upsert(collection_name=COLLECTION, points=[point])
    print(f"[update_single_product] Upserted {product['sku_id']} into Qdrant.")
    return True


def delete_product(item_code: str):
    """Remove a product from the index (e.g. when disabled/deleted in ERPNext)."""
    point_id = sku_to_point_id(item_code)
    client.delete(collection_name=COLLECTION, points_selector=[point_id])
    print(f"[delete_product] Removed {item_code} from Qdrant.")
    return True


def load_merged_dataset():
    """Load the product catalog from the configured source (Excel by default for this demo)."""
    products = fetch_products_from_excel() if DATA_SOURCE == "excel" else fetch_products_from_erp()

    rows = []
    for p in products:
        sizes_str = ", ".join(p.get("available_sizes", []))
        occasion_str = ", ".join(p.get("occasion_tags", []))
        body_fit_str = ", ".join(p.get("body_type_fit", []))
        skin_str = ", ".join(p.get("skin_tone_match", []))
        age_str = ", ".join(p.get("age_tags", []))
        height_str = ", ".join(p.get("height_band_fit", []))

        rows.append({
            "SKU ID": p.get("sku_id"),
            "Variants": p.get("variants", []),
            "Business Evidence": p.get("business_evidence") or {},
            "Personalization Evidence": p.get("personalization_evidence") or {},
            "SKU Codes": ", ".join(p.get("sku_codes", [])),
            "Product Name": p.get("name"),
            "Category": p.get("item_group"),
            "Sub Category": p.get("sub_category"),
            "Collection Name": p.get("collection_name"),
            "Gender": p.get("gender"),
            "Brand": p.get("brand"),
            "Budget Tier": p.get("budget_tier"),
            "Discounted Price (INR)": p.get("price", 0),
            "Available Sizes": sizes_str,
            "In Stock": "YES" if p.get("stock_count", 0) > 0 else "NO",
            "Is Active": "YES",
            "Is New Arrival": "YES" if p.get("is_new_arrival") else "NO",
            "Stock Count": p.get("stock_count", 0),
            "Primary Color": p.get("specific_color"),
            "Secondary Colors": ", ".join(p.get("color_family", [])[1:]) if isinstance(p.get("color_family"), list) else "",
            "Color Family": p.get("color_family"),
            "Pattern": p.get("pattern"),
            "Style Category": p.get("style_category"),
            "Silhouette": p.get("silhouette"),
            "Fit Type": p.get("fit_type"),
            "Length": p.get("length"),
            "Sleeve Type": p.get("sleeve_type"),
            "Neckline": p.get("neckline"),
            "Fabric": p.get("fabric_category"),
            "Fabric Weight": p.get("fabric_weight"),
            "Breathability": p.get("breathability"),
            "Stretch": p.get("stretch"),
            "Texture": p.get("texture"),
            "Care Difficulty": p.get("care_difficulty"),
            "Comfort Level": p.get("comfort_level"),
            "Weather Suitability": p.get("weather_suitability"),
            "Season": p.get("season"),
            "Occasion Tags": occasion_str,
            "Occasion Intensity": p.get("occasion_intensity"),
            "Dress Code": p.get("dress_code"),
            "Indoor/Outdoor": p.get("indoor_outdoor"),
            "Trend Level": p.get("trend_level"),
            "Statement Level": p.get("statement_level"),
            "Minimal/Maximal": p.get("minimal_maximal"),
            "Body Type Fit": body_fit_str,
            "Skin Tone Suitability": skin_str,
            "Age Group Fit": age_str,
            "Height Band Fit": height_str,
            "Petite Friendly": "YES" if p.get("petite_friendly") else "NO",
            "Plus Size Friendly": "YES" if p.get("plus_size_friendly") else "NO",
            "Alteration Available": "YES" if p.get("alteration_available") else "NO",
            "Wedding Suitability": "YES" if p.get("wedding_suitability") else "NO",
            "Wedding Function": p.get("wedding_function"),
            "Travel Friendly": "YES" if p.get("travel_friendly") else "NO",
            "Layer Friendly": "YES" if p.get("layer_friendly") else "NO",
            "Premium Flag": "YES" if p.get("premium_flag") else "NO",
            "Bestseller Flag": "YES" if p.get("bestseller_flag") else "NO",
            "Trending Flag": "YES" if p.get("trending_flag") else "NO",
            "Limited Edition": "YES" if p.get("limited_edition") else "NO",
            "Sale Item": "YES" if p.get("sale_item") else "NO",
            "Rating": p.get("rating"),
            "Trend Score (0-1)": p.get("trend_score", 0.5),
            "Bestseller Score (0-1)": p.get("bestseller_score", 0.5),
            "Margin Score (0-1)": p.get("margin_score", 0.5),
            "Inventory Urgency (0-1)": p.get("inventory_urgency", 0.0),
            "Image URL": p.get("image_url"),
            "Back Image URL": p.get("back_image_url"),
            "Embedding Text Dense": _dense_text(p),
            "Embedding Text Sparse": _sparse_text(p),
        })

    return pd.DataFrame(rows)



def build_index(force: bool = False):
    status = get_vector_db_status()
    if not force and status["exists"]:
        count = status["count"]
        if count > 0:
            print(f"[build_index] vector DB already exists with {count} SKUs — skipping rebuild.")
            return
        print(f"[build_index] vector DB collection exists but is empty (count={count}). Rebuilding index.")
    else:
        print("[build_index] vector DB collection missing. Rebuilding index.")

    df = load_merged_dataset()
    dense_texts = df["Embedding Text Dense"].fillna("").astype(str).tolist()
    sparse_texts = df["Embedding Text Sparse"].fillna("").astype(str).tolist()

    dense_vectors = list(dense_model.embed(dense_texts))
    sparse_vectors = list(sparse_model.embed(sparse_texts))

    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)

    client.create_collection(
        collection_name=COLLECTION,
        vectors_config={"dense": VectorParams(size=len(dense_vectors[0]), distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
    )

    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="in_stock",
        field_schema="bool",
    )
    client.create_payload_index(
        collection_name=COLLECTION,
        field_name="is_active",
        field_schema="bool",
    )

    for field, kind in {"gender": "keyword", "category": "keyword", "sizes": "keyword", "price": "float"}.items():
        client.create_payload_index(collection_name=COLLECTION, field_name=field, field_schema=kind)

    for field,kind in {"variants[].size":"keyword","variants[].price_minor":"integer",
                       "variants[].inventory_qty":"integer","variants[].is_active":"bool",
                       "variants[].stock_known":"bool"}.items():
        client.create_payload_index(collection_name=COLLECTION,field_name=field,field_schema=kind)
    for field in ("sub_category","fabric","color","occasion","style","comfort","fit","length","sleeve","neckline"):
        client.create_payload_index(collection_name=COLLECTION,field_name="attributes."+field,field_schema="keyword")
    points = []
    for i, row in df.iterrows():
        sizes = [s.strip().upper() for s in str(row["Available Sizes"]).split(",")]
        occasion_tags = [t.strip() for t in str(row.get("Occasion Tags", "")).split(",") if t.strip()]
        style_tags = [t.strip() for t in str(row.get("Style Tags", "")).split(",") if t.strip()]
        body_type_fit = [t.strip() for t in str(row.get("Body Type Fit", "")).split(",") if t.strip()]
        skin_tone_match = [t.strip() for t in str(row.get("Skin Tone Suitability", "")).split(",") if t.strip()]
        age_group_fit = [t.strip() for t in str(row.get("Age Group Fit", "")).split(",") if t.strip()]

        points.append(
            PointStruct(
                id=sku_to_point_id(row["SKU ID"]),
                vector={
                    "dense": dense_vectors[i].tolist(),
                    "sparse": SparseVector(
                        indices=sparse_vectors[i].indices.tolist(),
                        values=sparse_vectors[i].values.tolist(),
                    ),
                },
                payload={
                    "sku_id": row["SKU ID"],
                    "variants": row["Variants"],
                    "business_evidence": row.get("Business Evidence") or {},
                    "personalization_evidence": row.get("Personalization Evidence") or {},
                    "sku_codes": [s.strip() for s in str(row.get("SKU Codes", "")).split(",") if s.strip()],
                    "product_name": row["Product Name"],
                    "category": str(row["Category"]).strip().lower(),
                    "sub_category": row.get("Sub Category"),
                    "collection_name": row.get("Collection Name"),
                    "gender": str(row["Gender"]).strip().lower(),
                    "brand": row["Brand"],
                    "budget_tier": row.get("Budget Tier"),
                    "price": float(row["Discounted Price (INR)"]),
                    "sizes": sizes,
                    "in_stock": row["In Stock"] == "YES",
                    "is_active": row["Is Active"] == "YES",
                    "is_new_arrival": row["Is New Arrival"] == "YES",
                    "stock_count": row["Stock Count"],

                    "specific_color": row.get("Primary Color"),
                    "secondary_colors": row.get("Secondary Colors"),
                    "color_family": str(row.get("Color Family", "")).strip().lower() or None,
                    "pattern": row.get("Pattern"),
                    "style_category": row.get("Style Category"),
                    "silhouette": row.get("Silhouette"),
                    "silhouettes": [str(row.get("Silhouette", "")).strip()] if row.get("Silhouette") else [],
                    "fit_type": row.get("Fit Type"),
                    "length": row.get("Length"),
                    "sleeve_type": row.get("Sleeve Type"),
                    "neckline": row.get("Neckline"),
                    "fabric_category": row.get("Fabric"),
                    "fabric_weight": row.get("Fabric Weight"),
                    "breathability": row.get("Breathability"),
                    "stretch": row.get("Stretch"),
                    "texture": row.get("Texture"),
                    "care_difficulty": row.get("Care Difficulty"),
                    "comfort_level": row.get("Comfort Level"),
                    "weather_suitability": row.get("Weather Suitability"),
                    "season": row.get("Season"),
                    "occasion_primary": occasion_tags[0] if occasion_tags else None,
                    "occasion_tags": occasion_tags,
                    "occasion_intensity": row.get("Occasion Intensity"),
                    "dress_code": row.get("Dress Code"),
                    "indoor_outdoor": row.get("Indoor/Outdoor"),
                    "trend_level": row.get("Trend Level"),
                    "statement_level": row.get("Statement Level"),
                    "minimal_maximal": row.get("Minimal/Maximal"),
                    "body_type_fit": body_type_fit,
                    "skin_tone_match": skin_tone_match,
                    "skin_tone_suitability": skin_tone_match,
                    "age_tags": age_group_fit,
                    "height_band_fit": [t.strip() for t in str(row.get("Height Band Fit", "")).split(",") if t.strip()],
                    "petite_friendly": str(row.get("Petite Friendly", "NO")).strip().upper() == "YES",
                    "plus_size_friendly": str(row.get("Plus Size Friendly", "NO")).strip().upper() == "YES",
                    "alteration_available": str(row.get("Alteration Available", "NO")).strip().upper() == "YES",
                    "wedding_suitability": str(row.get("Wedding Suitability", "NO")).strip().upper() == "YES",
                    "wedding_function": row.get("Wedding Function"),
                    "travel_friendly": str(row.get("Travel Friendly", "NO")).strip().upper() == "YES",
                    "layer_friendly": str(row.get("Layer Friendly", "NO")).strip().upper() == "YES",
                    "premium_flag": str(row.get("Premium Flag", "NO")).strip().upper() == "YES",
                    "bestseller_flag": str(row.get("Bestseller Flag", "NO")).strip().upper() == "YES",
                    "trending_flag": str(row.get("Trending Flag", "NO")).strip().upper() == "YES",
                    "limited_edition": str(row.get("Limited Edition", "NO")).strip().upper() == "YES",
                    "sale_item": str(row.get("Sale Item", "NO")).strip().upper() == "YES",
                    "rating": row.get("Rating"),
                    "image_url": row.get("Image URL"),
                    "back_image_url": row.get("Back Image URL"),
                    "embedding_text_dense": row.get("Embedding Text Dense", ""),
                    "embedding_text_sparse": row.get("Embedding Text Sparse", ""),
                    "trend_score": row.get("Trend Score (0-1)"),
                    "bestseller_score": row.get("Bestseller Score (0-1)"),
                    "margin_score": row.get("Margin Score (0-1)"),
                    "inventory_urgency": row.get("Inventory Urgency (0-1)"),
                },
            )
        )

    for point in points:
        point.payload["attributes"] = attributes(point.payload)
    BATCH_SIZE = 50
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i:i + BATCH_SIZE]
        client.upsert(collection_name=COLLECTION, points=batch)
        print(f"[build_index] uploaded batch {i//BATCH_SIZE + 1} ({len(batch)} points)")
    print(f"[build_index] Index built: {len(points)} SKUs ready (dense + sparse).")
    print(f"[build_index] Final vector DB count: {client.count(collection_name=COLLECTION).count}")


def build_search_query(raw_query: str, tags: dict) -> str:
    """Build QUERY_2: Clean keyword search query for BM25 (removes duplication + noise)."""
    parts = []
    seen = set()

    def add_tag(tag_name, value):
        """Helper to add tags without duplication."""
        if not value:
            return
        if isinstance(value, (list, tuple, set)):
            values = [str(v).strip().lower() for v in value if str(v).strip()]
        else:
            values = [str(value).strip().lower()]

        for item in values:
            if item and item not in seen:
                seen.add(item)
                parts.append(item)

    # Priority order for tags (most specific first)
    add_tag("occasion", tags.get("occasion"))
    add_tag("event_context", tags.get("event_context"))
    add_tag("category", tags.get("category"))
    add_tag("style", tags.get("style"))


    color_value = tags.get("color")
    if not color_value and tags.get("formality") in COLOR_FAMILIES:
        color_value = tags.get("formality")
    if color_value:

        color_list = color_value if isinstance(color_value, list) else [color_value]
        for c in color_list:
            c_lower = str(c).strip().lower()
            if c_lower in COLOR_FAMILIES:            # it's a family name like "warm"
                add_tag("color_family", sorted(COLOR_FAMILIES[c_lower]))  # expand to all specific colors
            else:
                add_tag("color", c)                  # it's already a specific color

    add_tag("fabric_comfort", tags.get("fabric_comfort"))
    add_tag("body_type", tags.get("body_type"))
    add_tag("skin_tone", tags.get("skin_tone"))
    add_tag("mood", tags.get("mood"))
    add_tag("formality", tags.get("formality"))
    add_tag("height_cm_or_label", tags.get("height_cm_or_label"))
    add_tag("age_group", tags.get("age_group"))

    # Budget as keywords (no duplication)
    budget = tags.get("budget")
    if budget and isinstance(budget, dict):
        max_b = budget.get("max")
        min_b = budget.get("min")
        if max_b is not None:
            add_tag("budget_max", f"under {max_b}")
        elif min_b is not None:
            add_tag("budget_min", f"from {min_b}")

    # Join and return
    return " ".join(parts).strip()


def search(query_text: str, gender: str = None, size: str = None,
           budget: int = None, top_k: int = 50, semantic_query: str = None, category: str = None, preferences: dict = None):
    if gender:
        gender = gender.strip().lower()
    if size:
        size = size.strip().upper()

    semantic_query = semantic_query or query_text

    with _model_lock:   # ← NEW: serialize access to the shared tokenizer/model
        query_dense = list(dense_model.embed([semantic_query]))[0].tolist()
        query_sparse = list(sparse_model.embed([query_text]))[0]

    must = [
        FieldCondition(key="in_stock", match=MatchValue(value=True)),
        FieldCondition(key="is_active", match=MatchValue(value=True)),
    ]
    if gender:
        must.append(FieldCondition(key="gender", match=MatchValue(value=gender)))

    if category:
        must.append(FieldCondition(key="category", match=MatchValue(value=category.strip().lower())))

    variant_must = [
        FieldCondition(key="inventory_qty", range=Range(gt=0)),
        FieldCondition(key="is_active", match=MatchValue(value=True)),
        FieldCondition(key="stock_known", match=MatchValue(value=True)),
    ]
    if size:
        variant_must.append(FieldCondition(key="size", match=MatchValue(value=canonical("size",size))))
    if budget:
        bounds=validate_budget(budget)
        if bounds:
            variant_must.append(FieldCondition(key="price_minor", range=Range(
                gte=price_minor(bounds["min"]) if bounds.get("min") is not None else None,
                lte=price_minor(bounds["max"]) if bounds.get("max") is not None else None)))
    must.append(NestedCondition(nested=Nested(key="variants",filter=Filter(must=variant_must))))
    must_not=[]
    if preferences:
        vocab=preferences.get("_catalog_vocabulary",{})
        for field,wanted in preferences.get("must_have",{}).items():
            accepted=[v for v in vocab.get(field,[]) if field_match(field,wanted,[v])]
            must.append(FieldCondition(key="attributes."+field,match=MatchAny(any=accepted or ["__unavailable__"])))
        for field,excluded in preferences.get("exclude",{}).items():
            allowed=[v for v in vocab.get(field,[]) if not field_match(field,excluded,[v])]
            forbidden=[v for v in vocab.get(field,[]) if field_match(field,excluded,[v])]
            must.append(FieldCondition(key="attributes."+field,match=MatchAny(any=allowed or ["__unavailable__"])))
            if forbidden:
                must_not.append(FieldCondition(key="attributes."+field,match=MatchAny(any=forbidden)))

    print("\nFILTERS APPLIED:")
    print(must)

    response = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=query_dense, using="dense", limit=top_k, filter=Filter(must=must, must_not=must_not)),
            Prefetch(
                query=SparseVector(indices=query_sparse.indices.tolist(), values=query_sparse.values.tolist()),
                using="sparse", limit=top_k, filter=Filter(must=must, must_not=must_not),
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
    )

    candidates = response.points
    print(f"\n--- HYBRID (dense+sparse+filter, ONE call) -> {len(candidates)} candidates ---")
    for r in candidates[:10]:
        print(f"sku_id={r.payload['sku_id']}  rrf_score={r.score:.4f}")

    return candidates


def recommend(raw_query: str, gender: str = None, size: str = None, top_k: int = 5, budget: dict = None):
    """Full pipeline: Gemini extraction -> hybrid search -> rule engine -> top 5."""

    catalog_products = fetch_products_from_excel() if DATA_SOURCE == "excel" else fetch_products_from_erp()
    tags = extract_tags(raw_query, catalog_products)
    print("\nEXTRACTED TAGS:", tags)
    gender = gender or tags.get("gender")
    size = size or tags.get("size")

    if budget is not None:
        tags["budget"] = validate_budget(budget)

    tags["gender"], tags["size"] = gender, size
    search_text = " ".join(v for vals in tags["requested_attributes"].values() for v in vals)
    search_text = search_text or tags["positive_query"]
    print(f"\n{'='*80}")
    print(f"[QUERY_2] KEYWORD SEARCH QUERY (BM25 sparse search):")
    print(f"  {search_text!r}")
    print(f"{'='*80}")
    print(f"[QUERY_3] VECTOR SEARCH QUERY (BGE dense semantic embedding):")
    print(f"  {raw_query!r}")
    print(f"{'='*80}")

    candidates = search(
        query_text=search_text,
        gender=gender,
        size=size,
        budget=tags.get("budget"),
        top_k=(len(catalog_products) if len(catalog_products) <= POLICY["retrieval"]["small_catalog_limit"] else POLICY["retrieval"]["candidate_limit"]),
        semantic_query=tags["positive_query"],
        category=tags.get("category"),
        preferences={**tags, "_catalog_vocabulary": vocabulary(catalog_products)},
    )

    products = []
    for rank, candidate in enumerate(candidates,1):
        product = dict(candidate.payload)
        product["retrieval_rank"] = rank
        product["retrieval_score"] = candidate.score
        if check_hard_filters(product,tags):
            products.append(product)
    user_prefs = tags
    ranked = rank_products(user_prefs, products, top_k=top_k)

    products_by_sku = {p.get("sku_id"): p for p in products}
    for item in ranked:
        product = products_by_sku.get(item["sku_id"], {})
        item["name"] = product.get("product_name") or product.get("sku_id")
        item["category"] = product.get("category")
        item["brand"] = product.get("brand")
        item["price"] = min(v["price_minor"] for v in item["matched_variants"]) / 100
        item["specific_color"] = product.get("specific_color")
        item["fabric_category"] = product.get("fabric_category")
        item["occasion_primary"] = product.get("occasion_primary")
        item["occasion_tags"] = product.get("occasion_tags")
        item["style"] = product.get("style") or product.get("style_category")
        item["is_new_arrival"] = product.get("is_new_arrival")
        item["metadata"] = {
            "Product Name": product.get("product_name") or item.get("sku_id"),
            "Brand": product.get("brand") or "",
            "Category": product.get("category") or "",
            "Sub Category": product.get("sub_category") or "",
            "Price": item["price"],
            "Primary Colour": product.get("specific_color") or "",
            "Fabric": product.get("fabric_category") or "",
            "Occasion": product.get("occasion_primary") or "",
            "Rating": product.get("rating") or 0,
            "Image URL": _to_direct_image_url(product.get("image_url")),
            "Product Description": product.get("embedding_text_dense") or "",
            "Wedding Suitability": "YES" if product.get("wedding_suitability") else "NO",
            "Fashion Keywords": product.get("embedding_text_sparse") or "",
        }

    return ranked, tags



if __name__ == "__main__":
    build_index()

    results, extracted = recommend(
        "Need an elegant saree for Onam under 5000, medium skin tone",
        gender="female",
    )

    print("\n--- FINAL TOP 5 (Gemini tags + full rule engine) ---")
    for r in results:
        print(f"{r['rank_label']}: {r['sku_id']}  final_score={r['final_score']}")

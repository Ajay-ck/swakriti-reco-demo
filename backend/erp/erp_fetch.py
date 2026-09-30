
import os
import requests
from dotenv import load_dotenv

load_dotenv()

ERP_BASE_URL = os.environ.get("ERP_BASE_URL", "https://swakriti-db.m.frappe.cloud")
ERP_API_KEY = os.environ.get("ERP_API_KEY")
ERP_API_SECRET = os.environ.get("ERP_API_SECRET")

# Fields to request from ERPNext (default + custom fields)
FIELDS = [
    "item_code", "item_name", "item_group", "brand", "disabled",
    "custom_price_inr", "custom_available_sizes", "custom_stock_count",
    "custom_is_new_arrival", "custom_gender", "custom_occasion_tags",
    "custom_style_tags", "custom_color_primary", "custom_color_secondary",
    "custom_color_tone", "custom_fabric", "custom_body_type_fit",
    "custom_skin_tone_match", "custom_age_group_fit", "custom_trend_score",
    "custom_bestseller_score", "custom_margin_score", "custom_inventory_urgency",
]


def _split_csv(value):
    """Turn 'wedding, bridal, festive' -> ['wedding', 'bridal', 'festive']"""
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def fetch_products_from_erp():
    if not ERP_API_KEY or not ERP_API_SECRET:
        raise RuntimeError("ERP_API_KEY / ERP_API_SECRET missing in .env")

    url = f"{ERP_BASE_URL}/api/resource/Item"
    headers = {"Authorization": f"token {ERP_API_KEY}:{ERP_API_SECRET}"}
    params = {
        "fields": '["' + '","'.join(FIELDS) + '"]',
        "filters": '[["disabled","=",0]]',
        "limit_page_length": 0,  # 0 = fetch all, no pagination cap
    }

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    raw_items = resp.json().get("data", [])

    products = []
    for it in raw_items:
        occasion_tags = _split_csv(it.get("custom_occasion_tags"))
        products.append({
            "sku_id": it.get("item_code"),
            "name": it.get("item_name"),
            "item_group": it.get("item_group"),
            "brand": it.get("brand"),

            "price": it.get("custom_price_inr", 0),
            "available_sizes": _split_csv(it.get("custom_available_sizes")),
            "stock_count": it.get("custom_stock_count", 0),
            "is_new_arrival": bool(it.get("custom_is_new_arrival")),

            "gender": it.get("custom_gender"),
            "occasion_primary": occasion_tags[0] if occasion_tags else None,
            "occasion_tags": occasion_tags,
            "style": _split_csv(it.get("custom_style_tags")),

            "specific_color": it.get("custom_color_primary"),
            "color_family": [
                c for c in [
                    it.get("custom_color_primary"),
                    it.get("custom_color_secondary"),
                ] if c and c.strip() not in ("", "—", "-")
            ],
            "color_tone": it.get("custom_color_tone"),

            "fabric_category": it.get("custom_fabric"),
            "silhouettes": _split_csv(it.get("custom_body_type_fit")),
            "body_type_fit": _split_csv(it.get("custom_body_type_fit")),
            "skin_tone_match": _split_csv(it.get("custom_skin_tone_match")),
            "age_tags": _split_csv(it.get("custom_age_group_fit")),

            "trend_score": it.get("custom_trend_score", 0.5),
            "bestseller_score": it.get("custom_bestseller_score", 0.5),
            "margin_score": it.get("custom_margin_score", 0.5),
            "inventory_urgency": it.get("custom_inventory_urgency", 0.0),
        })

    return products


def _reshape_item(it):
    """Same reshape logic as fetch_products_from_erp, for a single ERPNext doc."""
    occasion_tags = _split_csv(it.get("custom_occasion_tags"))
    return {
        "sku_id": it.get("item_code") or it.get("name"),
        "name": it.get("item_name"),
        "item_group": it.get("item_group"),
        "brand": it.get("brand"),
        "disabled": it.get("disabled", 0),

        "price": it.get("custom_price_inr", 0),
        "available_sizes": _split_csv(it.get("custom_available_sizes")),
        "stock_count": it.get("custom_stock_count", 0),
        "is_new_arrival": bool(it.get("custom_is_new_arrival")),

        "gender": it.get("custom_gender"),
        "occasion_primary": occasion_tags[0] if occasion_tags else None,
        "occasion_tags": occasion_tags,
        "style": _split_csv(it.get("custom_style_tags")),

        "specific_color": it.get("custom_color_primary"),
        "color_family": [
            c for c in [
                it.get("custom_color_primary"),
                it.get("custom_color_secondary"),
            ] if c and c.strip() not in ("", "—", "-")
        ],
        "color_tone": it.get("custom_color_tone"),

        "fabric_category": it.get("custom_fabric"),
        "silhouettes": _split_csv(it.get("custom_body_type_fit")),
        "body_type_fit": _split_csv(it.get("custom_body_type_fit")),
        "skin_tone_match": _split_csv(it.get("custom_skin_tone_match")),
        "age_tags": _split_csv(it.get("custom_age_group_fit")),

        "trend_score": it.get("custom_trend_score", 0.5),
        "bestseller_score": it.get("custom_bestseller_score", 0.5),
        "margin_score": it.get("custom_margin_score", 0.5),
        "inventory_urgency": it.get("custom_inventory_urgency", 0.0),
    }


def fetch_single_product(item_code: str):
    """Fetch ONE product from ERPNext by Item Code — used for incremental webhook updates."""
    if not ERP_API_KEY or not ERP_API_SECRET:
        raise RuntimeError("ERP_API_KEY / ERP_API_SECRET missing in .env")

    url = f"{ERP_BASE_URL}/api/resource/Item/{item_code}"
    headers = {"Authorization": f"token {ERP_API_KEY}:{ERP_API_SECRET}"}

    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    raw_item = resp.json().get("data", {})

    if not raw_item:
        return None

    return _reshape_item(raw_item)


if __name__ == "__main__":
    # quick manual test: python erp_fetch.py
    items = fetch_products_from_erp()
    print(f"Fetched {len(items)} products from ERPNext")
    if items:
        print("Sample product:", items[0])
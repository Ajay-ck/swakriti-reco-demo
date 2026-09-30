
import json


def extract_item_code(payload):
    if not payload:
        return None

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    for candidate in (payload.get("data"), payload):
        if not isinstance(candidate, dict):
            continue
        for key in ("item_code", "name", "docname", "item", "doc"):
            value = candidate.get(key)
            if value:
                return value

    return None


def handle_erp_webhook(payload, ensure_index, update_single_product, delete_product):
    """
    Parses the ERPNext webhook payload, extracts the item_code, and applies
    the update/delete against the Qdrant index for just that one product.

    Returns (item_code, action) on success. Raises ValueError if item_code
    could not be found (caller should turn this into a 400 response).
    """
    item_code = extract_item_code(payload)

    if not item_code:
        raise ValueError("item_code not found in payload. Expected one of: item_code, name, docname")

    doc = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), dict) else payload
    if isinstance(doc, dict):
        is_disabled = doc.get("disabled")
    else:
        is_disabled = False

    if is_disabled:
        delete_product(item_code)
        action = "deleted"
    else:
        ensure_index()
        update_single_product(item_code)
        action = "updated"

    print(f"[erp_webhook] {action} -> {item_code}")
    return item_code, action
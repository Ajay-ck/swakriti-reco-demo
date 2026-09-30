"""Bounded image fetch for the demo UI; only Google image IDs are accepted."""
import re
from functools import lru_cache
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter()
MAX_BYTES = 10 * 1024 * 1024

@lru_cache(maxsize=8)
def fetch_image(file_id):
    with requests.get(
        "https://lh3.googleusercontent.com/d/" + file_id,
        stream=True, timeout=(10, 60),
    ) as upstream:
        upstream.raise_for_status()
        mime = upstream.headers.get("Content-Type", "").split(";")[0].lower()
        if mime not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            raise ValueError("Image provider returned non-image content")
        parts = []
        total = 0
        for chunk in upstream.iter_content(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("Image exceeds size limit")
            parts.append(chunk)
        data = b"".join(parts)
        if not (data.startswith((bytes.fromhex("89504e47"), bytes.fromhex("ffd8"), b"GIF")) or (data.startswith(b"RIFF") and data[8:12] == b"WEBP")):
            raise ValueError("Invalid image signature")
        return data, mime

@router.get("/product-image/{file_id}")
def product_image(file_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,150}", file_id):
        raise HTTPException(status_code=400, detail="Invalid image ID")
    try:
        data, mime = fetch_image(file_id)
    except (requests.RequestException, ValueError):
        raise HTTPException(status_code=502, detail="Product image unavailable")
    return Response(content=data, media_type=mime,
                    headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff"})



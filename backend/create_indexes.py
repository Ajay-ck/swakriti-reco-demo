import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

client = QdrantClient(
    url=os.environ.get("QDRANT_URL"),
    api_key=os.environ.get("QDRANT_API_KEY"),
    timeout=60,
)

COLLECTION = "skus"

# Fields your search() filters on in recommend_engine.py
fields_to_index = {
    "in_stock": PayloadSchemaType.BOOL,
    "is_active": PayloadSchemaType.BOOL,
    "gender": PayloadSchemaType.KEYWORD,
    "category": PayloadSchemaType.KEYWORD,
    "sizes": PayloadSchemaType.KEYWORD,
    "price": PayloadSchemaType.FLOAT,
}

for field_name, schema in fields_to_index.items():
    try:
        client.create_payload_index(
            collection_name=COLLECTION,
            field_name=field_name,
            field_schema=schema,
        )
        print(f"Created index on '{field_name}' ({schema})")
    except Exception as e:
        print(f"Skipped '{field_name}': {e}")

print("\nDone.")
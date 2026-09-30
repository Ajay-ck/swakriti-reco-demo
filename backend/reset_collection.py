import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()
client = QdrantClient(url=os.environ.get("QDRANT_URL"), api_key=os.environ.get("QDRANT_API_KEY"), timeout=60)
client.delete_collection("skus")
print("Collection deleted. It will rebuild on next backend startup.")
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1     FASTEMBED_CACHE_PATH=/app/model-cache     DATA_SOURCE=excel     PRODUCT_MASTER_PATH=Swakriti_Womens_Dresses_Product_Master_Top35_v4.csv     DISABLE_ERP_WEBHOOK=true
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5'); SparseTextEmbedding('Qdrant/bm25')"
COPY backend backend
COPY index.html start_backend.py Swakriti_Womens_Dresses_Product_Master_Top35_v4.csv ./
CMD ["python", "start_backend.py"]

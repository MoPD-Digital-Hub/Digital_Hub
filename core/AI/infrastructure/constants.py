import os
import re

COLLECTION_NAME = "admas_data"
DEFAULT_MILVUS_URI = "http://localhost:19530"
INDICATOR_CODE_PATTERN = re.compile(r"\b\d+(?:\.[A-Za-z0-9]+){1,}\b")

# Vector size of the embedding model (bge-m3 = 1024, bge-base-en-v1.5 = 768).
# Changing the embedding model requires dropping and re-ingesting the
# collection: `manage.py reindex_documents --drop-collection`.
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

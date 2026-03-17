import re

COLLECTION_NAME = "admas_data"
DEFAULT_MILVUS_URI = "http://localhost:19530"
INDICATOR_CODE_PATTERN = re.compile(r"\b\d+(?:\.[A-Za-z0-9]+){1,}\b")

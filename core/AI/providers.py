import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import APIConnectionError, APITimeoutError

_llm_cache = None
_embeddings_cache = None

def get_llm_instance():
    """Returns the cached LLM instance or creates a new one."""
    global _llm_cache
    if _llm_cache is not None:
        return _llm_cache

    VLLM_URL = os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
    VLLM_MODEL = os.getenv("VLLM_MODEL", "openai/gpt-oss-20b")

    try:
        _llm_cache = ChatOpenAI(
            openai_api_base=VLLM_URL,
            openai_api_key="EMPTY",
            model=VLLM_MODEL,
            streaming=False,
            temperature=0,
            request_timeout=60, 
            max_retries=3
        )
        return _llm_cache
    except (APIConnectionError, APITimeoutError) as e:
        print(f"❌ Could not connect to vLLM server: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected error initializing LLM: {e}")
    
    return None

def get_remote_embeddings():
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache

    EMBED_URL = os.getenv("EMBEDDING_API_BASE", "http://196.189.61.160:4001/v1")

    try:
        _embeddings_cache = OpenAIEmbeddings(
            model="BAAI/bge-base-en-v1.5", 
            api_key="empty",  
            base_url=EMBED_URL,
            timeout=60, 
            tiktoken_enabled=False, 
            check_embedding_ctx_length=False
        )
        return _embeddings_cache
    except Exception as e:
        print(f"⚠️ Failed to initialize Remote Embeddings: {str(e)}")
    
    return None
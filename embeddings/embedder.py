from functools import lru_cache

from config.settings import EMBEDDING_MODEL

# BGE retrieval models expect this prefix on QUERIES only (never on documents).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache(maxsize=1)
def get_bge_embeddings():
    """Load the embedding model once per process. HF_TOKEN (if set) is picked up automatically."""
    from langchain_huggingface import HuggingFaceEmbeddings  # lazy: heavy import

    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

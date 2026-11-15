from config.settings import TOP_K
from rag.answer_generator import generate_answer, label_docs
from rag.citation_validator import validate_and_format_citations
from rag.query_expansion import expand_query
from vectorstore.retriever import retrieve


def run_rag_pipeline(query: str, doc_id: str, k: int = TOP_K) -> dict:
    """Question -> hybrid retrieval -> grounded answer -> validated citations + confidence."""
    docs = retrieve(expand_query(query), doc_id, k)  # the model still sees the original question
    if not docs:
        return {"query": query, "answer": "No relevant passages were found in this tender.",
                "sources": [], "confidence": {"score": 0.0, "label": "low"},
                "citations": {"total": 0, "valid": 0}}
    labels = label_docs(docs)
    raw = generate_answer(query, labels)
    result = validate_and_format_citations(raw, labels)
    result["query"] = query
    return result

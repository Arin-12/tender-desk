from rag.query_expansion import expand_query
from vectorstore.retriever import retrieve

tests = {
    "NCRA-02": "What is the EMD amount specified in the tender notice?",
    "NCRA-03": "How must bidders submit the technical bid and price bid?",
    "NCRA-05": "Which documents must be included in the technical bid?",
}

for name, question in tests.items():
    expanded = expand_query(question)

    print("\n" + "=" * 100)
    print(name)
    print("Original:", question)
    print("Expanded:", expanded)

    docs = retrieve(expanded, "tender18mtfinalp", k=10)

    print("\nTOP 10 RETRIEVED CHUNKS")

    for rank, doc in enumerate(docs, 1):
        print(
            rank,
            doc.metadata.get("chunk_id"),
            "Page:", doc.metadata.get("page"),
            "RRF:", doc.metadata.get("rrf_score")
        )
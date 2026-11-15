from rag.query_expansion import expand_query
from vectorstore.retriever import retrieve

questions = {
    "NCRA-02": "What is the EMD amount specified in the tender notice?",
    "NCRA-03": "How must bidders submit the technical bid and price bid?",
    "NCRA-05": "Which documents must be included in the technical bid?",
}

for name, question in questions.items():
    expanded = expand_query(question)

    print("\n" + "=" * 90)
    print(name)
    print("Original :", question)
    print("Expanded :", expanded)

    docs = retrieve(expanded, "tender18mtfinalp", k=10)

    for rank, doc in enumerate(docs, 1):
        print(
            f"\nRank: {rank}"
            f" | Page: {doc.metadata.get('page')}"
            f" | Chunk: {doc.metadata.get('chunk_id')}"
            f" | RRF: {doc.metadata.get('rrf_score')}"
        )
        print(doc.page_content[:500].replace("\n", " "))

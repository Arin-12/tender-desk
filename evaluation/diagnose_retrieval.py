from vectorstore.retriever import retrieve, keyword_search

DOC_ID = "tender18mtfinalp"


queries = {
    "NCRA-02": "What is the EMD amount specified in the tender notice?",
    "NCRA-03": "How are the technical and price bids submitted?",
    "NCRA-05": "What documents are required in the technical bid?",
}


for name, query in queries.items():
    print("\n" + "=" * 100)
    print(name)
    print("QUERY:", query)

    for method, results in [
        ("HYBRID", retrieve(query, DOC_ID, k=6)),
        ("BM25", keyword_search(query, DOC_ID, k=10)),
    ]:
        print(f"\n--- {method} RESULTS ---")
        for rank, doc in enumerate(results, 1):
            m = doc.metadata
            print(
                f"\nRank {rank} | Page {m.get('page')} | "
                f"Chunk: {m.get('chunk_id')} | "
                f"Similarity: {m.get('similarity')} | "
                f"BM25: {m.get('bm25_score', m.get('keyword_score'))} | "
                f"RRF: {m.get('rrf_score')}"
            )
            print(doc.page_content[:1200].replace("\n", " "))

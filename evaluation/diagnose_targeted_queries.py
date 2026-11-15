from vectorstore.retriever import retrieve

tests = {
    "NCRA-02": [
        "EMD amount earnest money deposit tender notice estimated cost"
    ],
    "NCRA-03": [
        "Two bid system technical bid price bid uploaded separately on portal"
    ],
    "NCRA-05": [
        "Technical bid checklist registration PAN similar works experience testimonials work orders completion certificates bank solvency GST income tax machinery technical staff"
    ],
}

for name, queries in tests.items():
    for query in queries:
        print("\n" + "=" * 90)
        print(name, "|", query)

        docs = retrieve(query, "tender18mtfinalp", k=10)

        for rank, doc in enumerate(docs, 1):
            print(
                rank,
                doc.metadata.get("chunk_id"),
                "Page:", doc.metadata.get("page"),
                "RRF:", doc.metadata.get("rrf_score")
            )

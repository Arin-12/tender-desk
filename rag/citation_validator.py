import re

TAG = re.compile(r"\[([^\[\]]*\bS\d+\b[^\[\]]*)\]")  # [S1] [S1, S2] [Source: S1]
BARE = re.compile(r"(?<![\w\[])S(\d+)(?![\w\]])")


def source_dict(ref_id, label, doc):
    m = doc.metadata
    text = doc.page_content.strip()
    return {
        "ref_id": ref_id,
        "label": label,
        "chunk_id": m.get("chunk_id"),
        "page": m.get("page"),
        "section": m.get("section"),
        "chunk_type": m.get("chunk_type", "text"),
        "similarity": m.get("similarity"),
        "text": text[:1500],
    }


class SourceBook:
    """Maps the LLM's labels (S1, S2) to numbered references in order of first use."""

    def __init__(self, labels):
        self.labels = labels
        self.order = []

    def refs(self, raw):
        text = " ".join(map(str, raw)) if isinstance(raw, (list, tuple)) else str(raw or "")
        out = []
        for lb in re.findall(r"S\d+", text):
            if lb in self.labels:
                if lb not in self.order:
                    self.order.append(lb)
                rid = self.order.index(lb) + 1
                if rid not in out:
                    out.append(rid)
        return out

    def sources(self):
        return [source_dict(i + 1, lb, self.labels[lb]) for i, lb in enumerate(self.order)]

    def _docs(self, ref_ids):
        return [self.labels[self.order[r - 1]] for r in ref_ids]

    def pages(self, ref_ids):
        return sorted({d.metadata.get("page") for d in self._docs(ref_ids)
                       if d.metadata.get("page") is not None})

    def best_similarity(self, ref_ids):
        sims = [d.metadata.get("similarity", 0) for d in self._docs(ref_ids)]
        return max(sims) if sims else 0.0


def confidence_score(similarity, citation_ratio):
    """0.6 * retrieval similarity of the cited passages + 0.4 * share of valid citations.
    A transparent heuristic, not a probability. Thresholds are in the report's evaluation."""
    score = round(0.6 * min(max(similarity, 0), 1) + 0.4 * citation_ratio, 2)
    label = "high" if score >= 0.7 else "medium" if score >= 0.5 else "low"
    return {"score": score, "label": label}


def validate_and_format_citations(llm_answer, labels):
    """Replace [S#] tags by numbered references, drop invented ones, compute confidence."""
    text = llm_answer.replace("【", "[").replace("】", "]")
    book = SourceBook(labels)
    stats = {"total": 0, "valid": 0}

    def sub(match):
        found = re.findall(r"S\d+", match.group(1))
        stats["total"] += len(found)
        stats["valid"] += sum(1 for f in found if f in labels)
        return "".join(f"[{i}]" for i in book.refs(found))

    cleaned = TAG.sub(sub, text)

    # Models sometimes write a bare label (for example in a table column "Source"): S1, S2 ...
    def sub_bare(match):
        label = "S" + match.group(1)
        if label not in labels:
            return match.group(0)
        stats["total"] += 1
        stats["valid"] += 1
        return f"[{book.refs([label])[0]}]"

    cleaned = BARE.sub(sub_bare, cleaned)

    if book.order:
        similarity = sum(labels[l].metadata.get("similarity", 0) for l in book.order) / len(book.order)
    else:
        top = list(labels.values())[:3]
        similarity = sum(d.metadata.get("similarity", 0) for d in top) / max(len(top), 1)
    ratio = stats["valid"] / stats["total"] if stats["total"] else 0.0

    return {
        "answer": cleaned,
        "sources": book.sources(),
        "confidence": confidence_score(similarity, ratio),
        "citations": {"total": stats["total"], "valid": stats["valid"]},
    }

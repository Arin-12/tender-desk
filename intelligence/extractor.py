import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage

from intelligence.cache import cache_get, cache_set
from intelligence.catalog import GROUPS
from llm.groq_client import get_llm, invoke_json, invoke_with_retry
from llm.prompts import SUMMARY_SYSTEM, extraction_system
from rag.answer_generator import build_context, label_docs
from rag.citation_validator import (SourceBook, confidence_score,
                                    validate_and_format_citations)
from vectorstore.retriever import retrieve_multi

# ---- speed settings (all optional, set in .env) -------------------------------------------
EXTRACT_MAX_PASSAGES = int(os.getenv("EXTRACT_MAX_PASSAGES", "20"))   # fewer passages = fewer tokens = faster
EXTRACT_MODEL = os.getenv("GROQ_EXTRACT_MODEL", "").strip() or None    # e.g. a smaller, faster model
PREFETCH = [x.strip() for x in os.getenv("PREFETCH_ANALYSES", "key_info,eligibility,risks,boq").split(",") if x.strip()]
WARM_WORKERS = int(os.getenv("WARM_WORKERS", "2"))                     # parallel LLM calls (mind your rate limit)

_locks, _locks_guard = {}, threading.Lock()
_warming, _warm_guard = set(), threading.Lock()


def _lock_for(key):
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _n(text):
    """Normalise for comparing figures: lower-case, no commas or spaces (32,96,951 == 3296951)."""
    return re.sub(r"[,\s]", "", str(text).lower())


def ground_labels(value, raw_refs, labels):
    """
    Keep only the cited passages that actually contain the figures/dates in `value`.
    If none of the cited ones do, look through all retrieved passages. Returns (labels, verified).
    A value without figures cannot be checked this way and is returned unchanged.
    """
    tokens = {_n(t) for t in re.findall(r"\d[\d,.:/-]*\d", str(value))}
    tokens = {t for t in tokens if len(t) >= 3}
    cited = re.findall(r"S\d+", " ".join(map(str, raw_refs)) if isinstance(raw_refs, (list, tuple)) else str(raw_refs or ""))
    cited = [c for c in cited if c in labels]
    if not tokens:
        return cited, True

    def holds(label):
        text = _n(labels[label].page_content)
        return any(t in text for t in tokens)

    good = [c for c in cited if holds(c)]
    if not good:
        good = [lb for lb in labels if holds(lb)][:2]
    return good, bool(good)


def _compute_group(doc_id, group_key):
    group = GROUPS[group_key]
    docs = retrieve_multi([f["query"] for f in group["fields"]], doc_id,
                          k_each=group["k_each"], max_total=min(group["max_total"], EXTRACT_MAX_PASSAGES))
    labels = label_docs(docs)
    messages = [
        SystemMessage(content=extraction_system(group, build_context(labels))),
        HumanMessage(content="Extract the fields now. Keep each value under 60 words "
                             "(boq_items under 120 words). Copy figures exactly as written. "
                             "If a clause applies only to some bidders, say which. If the tender leaves an amount "
                             "blank (dots), write 'amount left blank in the tender' instead of repeating the dots. "
                             "Do not use general knowledge. Return the JSON object only."),
    ]
    data = invoke_json(messages, model=EXTRACT_MODEL)

    book = SourceBook(labels)
    fields = []
    for f in group["fields"]:
        item = data.get(f["key"])
        if isinstance(item, str):
            item = {"value": item, "refs": [], "found": True}
        item = item or {}
        found = bool(item.get("found", True)) and bool(str(item.get("value", "")).strip())
        value = str(item.get("value") or "Not specified in the provided pages")
        good, verified = ground_labels(value, item.get("refs", []), labels) if found else ([], True)
        refs = book.refs(good)
        if found and not verified:
            value += "\n\n*Check: these figures were not found in the retrieved passages.*"
        out = {
            "key": f["key"], "label": f["label"], "value": value,
            "found": found, "refs": refs, "pages": book.pages(refs), "verified": verified,
            "confidence": (confidence_score(book.best_similarity(refs), 1.0 if refs else 0.0)
                           if found and verified else ({"score": 0.2, "label": "low"} if found else None)),
        }
        if group["risk"]:
            level = str(item.get("risk", "")).lower()
            out["risk"] = level if level in ("low", "medium", "high") else None
            out["risk_reason"] = item.get("risk_reason", "")
        fields.append(out)

    return cache_set(doc_id, group_key, {
        "type": "fields", "group": group_key, "title": group["title"],
        "fields": fields, "sources": book.sources(),
        "coverage": {"found": sum(1 for f in fields if f["found"]), "total": len(fields)},
    })


def run_group(doc_id, group_key, refresh=False):
    """Structured extraction for one field group, cached on disk.
    A per-(tender, group) lock means that if the background warm-up is already computing it,
    a user request waits for that result instead of calling the model a second time."""
    if not refresh and (cached := cache_get(doc_id, group_key)):
        return cached
    with _lock_for((doc_id, group_key)):
        if not refresh and (cached := cache_get(doc_id, group_key)):
            return cached
        return _compute_group(doc_id, group_key)


def _compute_summary(doc_id):
    docs = retrieve_multi(
        ["project background objective of the work", "scope of work description of work",
         "location of work site details", "technical specifications standards materials"],
        doc_id, k_each=3, max_total=min(10, EXTRACT_MAX_PASSAGES))
    labels = label_docs(docs)
    messages = [SystemMessage(content=SUMMARY_SYSTEM.format(context=build_context(labels))),
                HumanMessage(content="Write the summary. Describe only what the passages state about THIS project. "
                                      "Do not present blank forms, proformas or templates as facts, and do not add "
                                      "general knowledge.")]
    raw = invoke_with_retry(get_llm(model=EXTRACT_MODEL), messages).content
    result = validate_and_format_citations(raw, labels)
    return cache_set(doc_id, "summary", {
        "type": "text", "title": "Executive summary", "content": result["answer"],
        "sources": result["sources"], "confidence": result["confidence"],
    })


def generate_summary(doc_id, refresh=False):
    if not refresh and (cached := cache_get(doc_id, "summary")):
        return cached
    with _lock_for((doc_id, "summary")):
        if not refresh and (cached := cache_get(doc_id, "summary")):
            return cached
        return _compute_summary(doc_id)


def run_analysis(doc_id, kind, refresh=False):
    if kind == "summary":
        result = generate_summary(doc_id, refresh)
    elif kind in GROUPS:
        result = run_group(doc_id, kind, refresh)
    else:
        raise ValueError(f"Unknown analysis '{kind}'. Choose from: summary, {', '.join(GROUPS)}")
    warm(doc_id)  # the user is clearly working with this tender: prepare the other sections
    return result


def _safe(doc_id, kind):
    try:
        run_analysis_no_warm(doc_id, kind)
    except Exception as error:
        print(f"[Warm-up] {doc_id}/{kind} skipped: {str(error)[:120]}")


def run_analysis_no_warm(doc_id, kind):
    return generate_summary(doc_id) if kind == "summary" else run_group(doc_id, kind)


def warm(doc_id, kinds=None):
    """Compute missing analyses in the background (2 calls at a time by default).
    Disable with PREFETCH_ANALYSES= (empty) in .env."""
    todo = [k for k in (kinds or PREFETCH) if (k == "summary" or k in GROUPS) and not cache_get(doc_id, k)]
    if not todo:
        return
    with _warm_guard:
        if doc_id in _warming:
            return
        _warming.add(doc_id)

    def work():
        try:
            with ThreadPoolExecutor(max_workers=WARM_WORKERS) as pool:
                for future in [pool.submit(_safe, doc_id, k) for k in todo]:
                    future.result()
        finally:
            with _warm_guard:
                _warming.discard(doc_id)

    threading.Thread(target=work, daemon=True).start()

import re
from concurrent.futures import ThreadPoolExecutor

from langchain_core.messages import HumanMessage, SystemMessage

from intelligence.extractor import run_group
from llm.groq_client import get_llm, invoke_with_retry

COMPARE_GROUPS = ["key_info", "eligibility", "risks"]
NOT_FOUND = "Not found in the passages read (check the tender manually)"

COMPARE_SYSTEM = """You compare two construction tenders for a contractor deciding where to bid.

DIFFERING FIELDS (both tenders had a value):
{rows}

NOT EXTRACTED FOR ONE TENDER (unknown, NOT differences):
{missing}

Write a short Markdown list (at most 8 bullets) of the differences that matter to a bidder (cost, security, time, eligibility, risk). Call them Tender A and Tender B.
Rules: quote amounts exactly as shown and never convert units (a lakh is not a crore); never say a tender lacks or does not state something just because a field is listed as not extracted; do not invent facts."""


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def compare_tenders(doc_a, doc_b):
    """Field-by-field comparison of two tenders (also usable for two revisions of one tender).
    A field that could not be extracted for one tender is reported as 'not found', never as a difference."""
    jobs = [(d, g) for d in (doc_a, doc_b) for g in COMPARE_GROUPS]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = dict(zip(jobs, pool.map(lambda job: run_group(*job), jobs)))

    rows = []
    for group in COMPARE_GROUPS:
        ra, rb = results[(doc_a, group)], results[(doc_b, group)]
        fb = {f["key"]: f for f in rb["fields"]}
        for fa in ra["fields"]:
            other = fb.get(fa["key"])
            if not other:
                continue
            comparable = bool(fa["found"] and other["found"])
            rows.append({
                "group": ra["title"], "label": fa["label"],
                "a": fa["value"] if fa["found"] else NOT_FOUND,
                "b": other["value"] if other["found"] else NOT_FOUND,
                "pages_a": fa["pages"], "pages_b": other["pages"],
                "comparable": comparable,
                "same": comparable and _norm(fa["value"]) == _norm(other["value"]),
            })

    differing = [r for r in rows if r["comparable"] and not r["same"]][:20]
    missing = [r["label"] for r in rows if not r["comparable"]]
    summary = ""
    if differing:
        text = "\n".join(f'- {r["label"]}: A = {r["a"][:300]} | B = {r["b"][:300]}' for r in differing)
        messages = [SystemMessage(content=COMPARE_SYSTEM.format(rows=text, missing=", ".join(missing) or "none")),
                    HumanMessage(content="Summarise the differences.")]
        summary = invoke_with_retry(get_llm(), messages).content
    return {"rows": rows, "summary": summary,
            "note": "Values are compared as extracted text; different wording can appear as a difference. "
                    "Fields marked 'not found' were not extracted for one tender and are not compared."}

from langchain_core.messages import HumanMessage, SystemMessage

from intelligence.cache import cache_get, cache_set
from intelligence.extractor import run_group
from llm.groq_client import invoke_json
from rag.answer_generator import build_context, label_docs
from rag.citation_validator import SourceBook
from vectorstore.retriever import retrieve_multi

CRITERIA_QUERIES = [
    "minimum average annual turnover eligibility", "similar works experience completed value",
    "net worth solvency certificate", "contractor registration class enlistment",
    "enlistment valid on last date of submission of bids",
    "GST PAN EPF ESI registration", "registration with EPFO ESIC BOCW labour licence",
    "plant machinery equipment bidder must own", "list of testing equipment to be provided by the contractor at site lab",
    "key personnel engineer qualification", "valid class III digital signature certificate encryption key",
    "bid capacity joint venture eligibility", "near relative restriction contractor not permitted to bid",
    "affidavit similar works back to back integrity pact", "earnest money deposit instrument receipt documents to be uploaded",
]

CRITERIA_SYSTEM = """You list the bidder eligibility criteria and bid requirements of a construction tender. Use ONLY the CONTEXT.

CONTEXT:
{context}

Return ONE JSON object:
{{"criteria": [{{"category": "...", "criterion": "short name", "requirement": "...", "applies_to": "...", "blank_amount": false, "refs": ["S1"]}}]}}

category: financial | technical | statutory | registration | equipment | personnel | bid_document | other
  (bid_document = something uploaded or deposited WITH THE BID: the EMD instrument, EMD receipt, an affidavit, the integrity pact)
requirement: as written, figures exact. Do not copy rates of recovery or penalties into a requirement.
  If the tender leaves an amount blank (dots), set blank_amount to true and write "amount left blank in the tender".
applies_to: who or what the criterion applies to: "all bidders", "CPWD-enlisted contractors only", "non-CPWD contractors only",
  "EPC tenders only", or the exact condition stated in the tender.
Include every distinct requirement, up to 20. Do not invent criteria that are not in the context."""

BIDCHECK_SYSTEM = """You compare a contractor's profile with the requirements of one tender.

TENDER CONTEXT:
{context}

For EACH criterion choose one status:
- "met": the profile clearly satisfies it. Compare numbers explicitly (turnover, values, years).
- "not_met": the profile clearly does not satisfy it, and nothing stated in the criterion would fix it.
- "unclear": the profile does not give enough information; or the criterion can be satisfied by an alternative
  (for example an undertaking) that the profile does not mention.
- "not_applicable": the criterion applies only to bidders or tenders that this profile and this tender are not
  (for example "non-CPWD contractors only" when the profile says the firm is CPWD-enlisted, or "EPC tenders only"
  when the tender is a percentage-rate works contract).
- "to_prepare": a document or deposit submitted with the bid (category bid_document) that a firm profile cannot show.
  If the profile says it is ready, use "met".
Never assume facts that are not in the profile. Missing information means "unclear".

Return ONE JSON object: {{"results": [{{"id": "C1", "status": "met|not_met|unclear|not_applicable|to_prepare",
"evidence": "what in the profile supports the decision, or 'No information provided'", "action": "what to do (empty if met or not applicable)"}}]}}
Return one result for every criterion id.

CRITERIA:
{criteria}

CONTRACTOR PROFILE:
{profile}"""

PROFILE_LABELS = {
    "company": "Company name and type", "turnover": "Annual turnover (by financial year)",
    "net_worth": "Net worth / solvency", "similar_works": "Completed similar works (name, value, year, client)",
    "registrations": "Registrations and licences", "equipment": "Equipment owned or leased",
    "personnel": "Key personnel", "other": "Other certificates or notes",
}
STATUSES = ("met", "not_met", "unclear", "not_applicable", "to_prepare")


def get_criteria(doc_id, refresh=False):
    """Eligibility criteria and bid requirements extracted from the tender (cached)."""
    if not refresh and (cached := cache_get(doc_id, "criteria")):
        return cached
    docs = retrieve_multi(CRITERIA_QUERIES, doc_id, k_each=2, max_total=22)
    labels = label_docs(docs)
    messages = [SystemMessage(content=CRITERIA_SYSTEM.format(context=build_context(labels))),
                HumanMessage(content="List the criteria. Return the JSON object only.")]
    data = invoke_json(messages)

    book = SourceBook(labels)
    criteria = []
    for i, c in enumerate(data.get("criteria", [])[:20], start=1):
        refs = book.refs(c.get("refs", []))
        criteria.append({"id": f"C{i}", "category": c.get("category", "other"),
                         "criterion": c.get("criterion", ""), "requirement": c.get("requirement", ""),
                         "applies_to": c.get("applies_to", "all bidders"), "blank_amount": bool(c.get("blank_amount")),
                         "refs": refs, "pages": book.pages(refs)})
    return cache_set(doc_id, "criteria", {"criteria": criteria, "sources": book.sources()})


def format_profile(profile: dict) -> str:
    lines = [f"{PROFILE_LABELS[k]}: {str(profile.get(k, '')).strip()}"
             for k in PROFILE_LABELS if str(profile.get(k, "")).strip()]
    return "\n".join(lines)


def tender_context(doc_id):
    """Short description of the tender (type of work, who may bid) so the checker can judge applicability."""
    lines = []
    for group, keys in (("key_info", ("title", "estimated_cost")), ("eligibility", ("who_can_bid",))):
        try:
            for f in run_group(doc_id, group)["fields"]:
                if f["key"] in keys and f.get("found"):
                    lines.append(f"{f['label']}: {f['value']}")
        except Exception:
            pass
    return "\n".join(lines) or "Not available"


def check_eligibility(doc_id, profile: dict):
    """Per-criterion result with evidence. Deliberately NOT a probability.
    Extra statuses: not_applicable (clause does not apply to this firm or tender) and
    to_prepare (a document or deposit submitted with the bid)."""
    profile_text = format_profile(profile)
    if not profile_text:
        raise ValueError("Fill in at least one profile field before checking eligibility.")

    base = get_criteria(doc_id)
    criteria = base["criteria"]
    if not criteria:
        raise ValueError("No eligibility criteria could be found in this tender.")

    listing = "\n".join(
        f'{c["id"]} [{c["category"]}] {c["criterion"]}: {c["requirement"]} (applies to: {c.get("applies_to", "all bidders")})'
        for c in criteria)
    messages = [SystemMessage(content=BIDCHECK_SYSTEM.format(context=tender_context(doc_id), criteria=listing, profile=profile_text)),
                HumanMessage(content="Check each criterion. Return the JSON object only.")]
    data = invoke_json(messages)
    by_id = {r.get("id"): r for r in data.get("results", [])}

    rows, counts = [], dict.fromkeys(STATUSES, 0)
    for c in criteria:
        r = by_id.get(c["id"], {})
        status = r.get("status") if r.get("status") in STATUSES else "unclear"
        action = r.get("action", "")
        if c.get("category") == "bid_document" and status == "unclear":
            status = "to_prepare"
        if c.get("blank_amount") and status in ("met", "not_met"):
            status, action = "unclear", "The tender leaves the amount blank. Ask the department what applies to your firm."
        counts[status] += 1
        rows.append({**c, "status": status, "evidence": r.get("evidence") or "No information provided", "action": action})

    judged = counts["met"] + counts["not_met"] + counts["unclear"]
    verdict = ("not_eligible_as_stated" if counts["not_met"] else
               "needs_verification" if counts["unclear"] else "likely_eligible")
    return {
        "criteria": rows, "sources": base["sources"],
        "summary": {**counts, "total": len(rows), "judged": judged,
                    "readiness": round(100 * counts["met"] / judged) if judged else 0, "verdict": verdict},
        "disclaimer": "Decision support only. Verify every criterion against the original tender and your documents before bidding.",
    }

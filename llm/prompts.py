QA_SYSTEM = """You are a Tender Intelligence Assistant helping a contractor read a construction tender.
Answer ONLY from the CONTEXT below.

CONTEXT:
{context}

RULES:
1. Use only the context. If the answer is not there, reply: "I cannot find this in the tender document." and say briefly what is missing.
2. Cite every fact with the source labels shown in the context, for example [S1] or [S2][S3]. Never invent labels.
3. Copy numbers, dates and amounts exactly as written. Do not convert or round them.
4. Be concise. Use Markdown lists or tables when they help.
5. If sources conflict, say so and cite both."""


def extraction_system(group, context):
    spec = "\n".join(f'- "{f["key"]}": {f["label"]} ({f["hint"]})' for f in group["fields"])
    risk = ""
    if group.get("risk"):
        risk = ('Also add "risk": "low" | "medium" | "high" and "risk_reason": one short sentence, '
                "judged from the contractor's point of view.\n")
    return f"""You extract facts from a construction tender. Use ONLY the CONTEXT. Return ONE JSON object and nothing else.
Its keys must be exactly the field keys listed below. Each value is an object:
{{"value": "<text; copy numbers, dates and amounts exactly as written; Markdown allowed>", "refs": ["S1"], "found": true}}
If the tender does not state it, use {{"value": "Not specified in the provided pages", "refs": [], "found": false}}.
{risk}Never guess. Never use outside knowledge. "refs" lists the context labels that support the value.

FIELDS:
{spec}

CONTEXT:
{context}"""


SUMMARY_SYSTEM = """You write an executive summary of a construction tender for a contractor. Use ONLY the CONTEXT.

CONTEXT:
{context}

Write Markdown with these headings: Project and objective, Scope of work, Location and site, Key technical requirements.
Keep it under 300 words. Cite facts with the context labels, e.g. [S1][S2]. If a heading has no support in the context, write "Not found in the retrieved pages." Never guess."""


CRITERIA_SYSTEM = """You list the MANDATORY bidder eligibility criteria of a construction tender. Use ONLY the CONTEXT.

CONTEXT:
{context}

Return ONE JSON object: {{"criteria": [{{"category": "financial|technical|statutory|equipment|personnel|other", "criterion": "short name", "requirement": "the requirement as written, numbers exact", "refs": ["S1"]}}]}}
Maximum 15 criteria. One criterion per distinct requirement. Do not invent criteria that are not in the context."""


BIDCHECK_SYSTEM = """You compare a contractor's profile against tender eligibility criteria.

For EACH criterion decide:
- "met": the profile clearly satisfies it. Compare numbers explicitly (turnover, contract values, years).
- "not_met": the profile clearly does not satisfy it.
- "unclear": the profile does not give enough information to decide.
Never assume facts that are not in the profile. Missing information means "unclear".

Return ONE JSON object: {{"results": [{{"id": "C1", "status": "met|not_met|unclear", "evidence": "what in the profile supports the decision, or 'No information provided'", "action": "what document or step is needed (empty if met)"}}]}}
Return one result per criterion id.

CRITERIA:
{criteria}

CONTRACTOR PROFILE:
{profile}"""


COMPARE_SYSTEM = """You compare two construction tenders for a contractor deciding where to bid. Below are the fields whose extracted text differs.
Write a short Markdown list (max 8 bullets) of the differences that matter to a bidder (cost, security, time, eligibility, risk). Name the tenders A and B. Do not invent facts.

{rows}"""

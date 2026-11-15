from langchain_core.messages import HumanMessage, SystemMessage

from llm.groq_client import get_llm, invoke_with_retry
from llm.prompts import QA_SYSTEM


def label_docs(docs) -> dict:
    """Give each retrieved chunk a short label (S1, S2, ...). Short labels are far
    easier for the LLM to cite correctly than long chunk ids."""
    return {f"S{i}": d for i, d in enumerate(docs, start=1)}


def build_context(labels: dict) -> str:
    blocks = []
    for label, doc in labels.items():
        m = doc.metadata
        head = f"[{label}] Page {m.get('page')} | {m.get('section', '')} | {m.get('chunk_type', 'text')}"
        blocks.append(f"{head}\n{doc.page_content.strip()}")  # newlines kept: tables stay tables
    return "\n\n---\n\n".join(blocks)


def generate_answer(query: str, labels: dict) -> str:
    if not labels:
        return "I could not find relevant information in the tender document."
    messages = [
        SystemMessage(content=QA_SYSTEM.format(context=build_context(labels))),
        HumanMessage(content=(
            query + "\n\nUse only facts stated in the context. Do not add definitions or general knowledge. "
            "Cite every fact with its label in square brackets, e.g. [S1], never as a bare S1 and never in a "
            "separate 'Sources' list. If a clause applies only to some bidders, say which. If generic template wording (for example \"if bids are also open to non-CPWD contractors\" or both item-rate and percentage-rate language) conflicts with what the notice inviting tender states for THIS tender, give the tender-specific statement as the answer and mention the generic wording only briefly.")),
    ]
    return invoke_with_retry(get_llm(), messages).content

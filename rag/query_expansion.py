
"""Add tender-specific vocabulary to questions to improve hybrid retrieval."""

import re

SYNONYMS = [
    (
        r"\bboq\b|bill of quantit",
        "bill of quantities schedule of quantities schedule of quantity",
    ),

    # EMD amount retrieval
    (
        r"\bemd\b",
        "earnest money deposit amount tender notice estimated cost",
    ),

    (
        r"\bld\b|liquidated damage|penalt",
        "compensation for delay liquidated damages penalty",
    ),
    (
        r"\bpg\b|performance guarantee",
        "performance guarantee performance security",
    ),
    (
        r"\bsd\b|security deposit",
        "security deposit retention",
    ),
    (
        r"\bgcc\b",
        "general conditions of contract",
    ),
    (
        r"budget|total cost|total amount|total value",
        "estimated cost grand total amount",
    ),
    (
        r"turnover",
        "annual turnover financial eligibility",
    ),
    (
        r"\bjv\b|joint venture",
        "joint venture consortium",
    ),
    (
        r"validity",
        "bids remain open for acceptance days",
    ),

    # Two-bid submission retrieval
    (
        r"\btechnical bid\b.*\bprice bid\b|\bprice bid\b.*\btechnical bid\b",
        "two bid system technical bid price bid uploaded separately online CPP portal",
    ),

    # Technical-bid checklist retrieval
    (
        r"\btechnical bid\b.*\b(documents?|checklist|include|contain|required)\b"
        r"|\b(documents?|checklist)\b.*\btechnical bid\b",
        "technical bid checklist registration PAN similar works work orders  "
        "completion certificates bank solvency GST income tax "
        "plant machinery technical staff",
    ),
]


def expand_query(query: str) -> str:
    extra = [
        addition
        for pattern, addition in SYNONYMS
        if re.search(pattern, query, re.I)
    ]
    return query + (" " + " ".join(extra) if extra else "")


import sys
from pathlib import Path

# Add project root to Python import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import json
from collections import Counter

from config.settings import PROCESSED_DIR


DOCS = {
    "FMTTI": "final_nit_fmtti.json",
    "NCRA_TIFR": "tender18mtfinalp.json",
}

KEYWORDS = [
    "estimated cost",
    "1.45 crore",
    "earnest money",
    "emd",
    "tender fee",
    "completion",
    "monsoon",
    "performance guarantee",
    "security deposit",
    "bank solvency",
    "similar works",
    "technical bid",
    "price bid",
    "defect liability",
]

for name, filename in DOCS.items():
    path = PROCESSED_DIR / filename
    pages = json.loads(path.read_text(encoding="utf-8"))

    print("\n" + "=" * 65)
    print(f"{name}: {filename}")
    print("Passages:", len(pages))

    methods = Counter(
        p.get("extraction_method", "unknown") for p in pages
    )
    print("Extraction methods:", dict(methods))

    short_pages = [
        p.get("page")
        for p in pages
        if len((p.get("text") or "").strip()) < 50
    ]
    print("Pages with fewer than 50 characters:", short_pages)

    print("\nKeyword locations:")
    for keyword in KEYWORDS:
        matches = [
            p for p in pages
            if keyword.lower() in (p.get("text") or "").lower()
        ]

        if matches:
            print(
                f"\n{keyword}: "
                f"{[p.get('page') for p in matches]}"
            )
            for p in matches[:2]:
                text = " ".join((p.get("text") or "").split())
                print("  ", text[:250])

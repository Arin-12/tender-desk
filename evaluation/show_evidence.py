
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import PROCESSED_DIR

DOCS = {
    "FMTTI": {
        "file": "final_nit_fmtti.json",
        "pages": [3, 4, 7, 8, 9, 10, 31, 32, 33, 36, 44]
    },
    "NCRA_TIFR": {
        "file": "tender18mtfinalp.json",
        "pages": [3, 4, 6, 7, 8, 13, 16, 17, 24, 26, 29, 36, 37]
    }
}

for name, config in DOCS.items():
    path = PROCESSED_DIR / config["file"]
    pages = json.loads(path.read_text(encoding="utf-8"))

    print("\n" + "=" * 90)
    print(name)

    for page_no in config["pages"]:
        matches = [p for p in pages if int(p["page"]) == page_no]

        for p in matches:
            print("\n" + "-" * 70)
            print(f"PDF PAGE: {page_no}")
            print(f"METHOD: {p.get('extraction_method')}")
            print(p.get("text", ""))

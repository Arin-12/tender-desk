import re

MAJOR_KEYWORDS = [
    "NOTICE INVITING TENDER", "INSTRUCTIONS TO BIDDERS", "PRE-QUALIFICATION CRITERIA",
    "ELIGIBILITY CRITERIA", "CLAUSES OF CONTRACT", "SCOPE OF WORK", "SCOPE OF WORKS",
    "TECHNICAL SPECIFICATIONS", "SPECIAL CONDITIONS", "GENERAL CONDITIONS TO CONTRACT",
    "GENERAL CONDITIONS OF CONTRACT", "GENERAL GUIDELINES TO BIDDERS", "FORM AND FORMAT",
    "DRAWINGS", "ANNEXURES", "BILL OF QUANTITIES",
]

# Table-of-contents lines: "Scope of Work ..... 36" or "Scope of Work 36-37"
TOC_LINE = re.compile(r"\.{3,}\s*\d+\s*$|\s\d{1,3}\s*[-–]\s*\d{1,3}\s*$")
PART_RE = re.compile(r"^(PART|SECTION|ANNEXURE|APPENDIX)\s*[-–—:]?\s*(\d+|[IVXLC]+|[A-Z])\b", re.I)


def normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def is_major_section(line: str) -> bool:
    line = line.strip()
    if len(line) > 80 or "http" in line.lower() or "@" in line:
        return False
    if line.endswith(".") or TOC_LINE.search(line):
        return False
    if PART_RE.match(line) and (line.isupper() or len(line) <= 30):
        return True
    upper = line.upper()
    return any(k in upper and len(upper) <= len(k) + 15 for k in MAJOR_KEYWORDS)


def is_subsection(line: str) -> bool:
    line = line.strip()
    if len(line) > 60 or line.endswith(".") or TOC_LINE.search(line):
        return False
    if re.match(r"^[A-Z]\)\s+[A-Za-z]", line):        # A) General
        return True
    return bool(re.match(r"^\d+\.0\s+[A-Za-z]", line))  # 1.0 Tender Notice


def detect_section(text: str):
    """Return (section, subsection) found on a page; either may be None."""
    section = subsection = None
    for line in (l.strip() for l in text.splitlines() if l.strip()):
        if len(line) > 120:
            continue
        if is_major_section(line):
            section, subsection = normalize_heading(line), None
        elif is_subsection(line):
            subsection = normalize_heading(line)
    return section, subsection

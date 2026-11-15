import re
from collections import Counter


def fix_font_glitches(text: str) -> str:
    """
    Some tender PDFs use fonts whose quotes, apostrophes, dashes and dotted blanks come out of the
    text layer as other letters:  ôTextö -> "Text",  æFÆ -> 'F',  workerÆs -> worker's,
    Engineer ûin -> Engineer -in,  Rs. àààà -> Rs. ....  Only unambiguous patterns are repaired.
    """
    if not text:
        return ""
    text = re.sub(r"ô([^ôö\n]{1,200}?)ö", lambda m: "\u201c" + m.group(1) + "\u201d", text)   # ôquotedö
    text = re.sub(r"æ([^æÆ\n]{1,40}?)Æ", lambda m: "\u2018" + m.group(1) + "\u2019", text)   # æFÆ
    text = re.sub(r"(?<=[A-Za-z])Æ(?=[a-z])", "\u2019", text)                                # workerÆs
    text = re.sub(r"(?<=[\s(])û(?=[A-Za-z])", "-", text)                                      # ûin - Charge
    if text.count("à") >= 3:                                                                  # dotted blanks
        text = re.sub(r"à+", lambda m: "." * len(m.group()), text)
    return text


def clean_text(text: str) -> str:
    """Normalise whitespace. Keeps standalone numbers (BOQ quantities, rates);
    only a trailing page-number line is dropped."""
    if not text:
        return ""
    text = fix_font_glitches(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    lines = text.split("\n")
    if lines and re.fullmatch(r"\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*", lines[-1], re.I):
        lines.pop()
    return "\n".join(lines).strip()


def _norm(line: str) -> str:
    return re.sub(r"\d+", "#", line.strip().lower())


def find_repeated_lines(texts, edge=3, min_pages=8, ratio=0.4):
    """Lines that show up in the first/last few lines of >= 40% of pages
    (running headers/footers such as 'Tender No. 12 | Page 5 of 90')."""
    if len(texts) < min_pages:
        return set()
    counter = Counter()
    for text in texts:
        lines = [_norm(l) for l in text.splitlines() if l.strip()]
        counter.update(set(lines[:edge] + lines[-edge:]))
    return {l for l, n in counter.items() if n >= ratio * len(texts) and len(l) < 100}


def remove_repeated_lines(text: str, repeated, edge=3) -> str:
    if not repeated:
        return text
    lines = text.splitlines()
    nonempty = [i for i, l in enumerate(lines) if l.strip()]
    edge_idx = set(nonempty[:edge] + nonempty[-edge:])
    return "\n".join(l for i, l in enumerate(lines) if not (i in edge_idx and _norm(l) in repeated))

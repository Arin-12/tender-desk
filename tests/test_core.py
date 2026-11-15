from types import SimpleNamespace

from chunking.chunker import split_table
from preprocessing.section_detector import detect_section, is_major_section, is_subsection
from preprocessing.text_cleaner import clean_text, find_repeated_lines, remove_repeated_lines
from rag.citation_validator import validate_and_format_citations


def doc(page, sim=0.8):
    return SimpleNamespace(page_content="text", metadata={"chunk_id": f"c{page}", "page": page,
                                                          "section": "NIT", "similarity": sim})


def test_cleaner_keeps_standalone_numbers():
    assert "1500" in clean_text("Item\n1500\nRate\n250\n12")  # trailing page number removed
    assert not clean_text("Item\n1500\nRate\n250\n12").endswith("12")


def test_section_headings():
    assert is_major_section("SECTION 2") and is_major_section("PART - A")
    assert not is_major_section("Scope of Work ..... 36")
    assert is_subsection("1.0 Tender Notice") and is_subsection("A) General")
    assert not is_subsection("Scope 36-37")
    assert detect_section("SECTION 2\n1.0 Tender Notice\nbody text here.") == ("SECTION 2", "1.0 Tender Notice")


def test_repeated_headers_removed():
    pages = [f"Tender No 5 Page {i}\nbody {i}\nmore text" for i in range(10)]
    rep = find_repeated_lines(pages)
    assert "body" not in remove_repeated_lines(pages[3], rep).split("\n")[0]


def test_table_split_keeps_header():
    rows = [["Item", "Qty"]] + [[f"work {i}", str(i)] for i in range(200)]
    parts = split_table(rows, max_chars=500)
    assert len(parts) > 1 and all(p.startswith("| Item | Qty |") for p in parts)


def test_citations_multi_and_invalid():
    labels = {"S1": doc(3), "S2": doc(7)}
    r = validate_and_format_citations("EMD is 2.9 lakh [S1, S2]. Time 12 months [S2] [S9].", labels)
    assert r["answer"] == "EMD is 2.9 lakh [1][2]. Time 12 months [2] ."
    assert [s["page"] for s in r["sources"]] == [3, 7]
    assert r["citations"] == {"total": 4, "valid": 3}
    assert r["confidence"]["label"] in ("high", "medium", "low")


def test_no_citations_is_low_confidence():
    r = validate_and_format_citations("Some unsupported claim.", {"S1": doc(1)})
    assert r["confidence"]["label"] == "low"

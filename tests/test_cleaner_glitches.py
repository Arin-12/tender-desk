from preprocessing.text_cleaner import clean_text, fix_font_glitches


def test_glitches_from_the_fmtti_pdf():
    raw = ("ôRenovation of Residential Buildings (Electrical Work)ö at Assam. Case æFÆ shall be followed. "
           "list of workerÆs to be deployed. Engineer ûin - Charge. Three works each not less than Rs. àààààààà. Or two")
    out = fix_font_glitches(raw)
    assert "\u201cRenovation of Residential Buildings (Electrical Work)\u201d" in out
    assert "\u2018F\u2019" in out and "worker\u2019s" in out and "Engineer -in" in out
    assert "à" not in out and "Rs. ........." in out


def test_normal_text_is_untouched():
    plain = "Caf\u00e9 menu: Engineer-in-Charge, worker's list, Rs. 65,939/-. R\u00f4le is a name."
    assert fix_font_glitches(plain) == plain
    assert "65,939" in clean_text(plain)

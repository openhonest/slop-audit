"""Six lookups that answered for a key nobody wrote a rule for.

Rule 18 is exact about the harm: `table.get(key, default)` files an input nobody wrote a
rule for under an answer written for a different input, and the default re-opens the space
while the code still reads closed. What it asks instead is that an unknown key be recorded
as a gap in the table.

Three other sites in this package already do that, by using the key itself as the default,
so the unknown key comes back visible as itself. These six did not.

The worst is the card's band word. `_BAND_WORD` carries a real `"n/a": "No data"` row, so
`.get(band, "No data")` rendered a band the card does not recognise exactly like a
measurement that was refused. A reader cannot tell "this indicator declined to grade" from
"this indicator produced a grade nobody here has a word for".
"""

import ast

import pytest
from l1_analyzer import callmap, card, facets, indicators

# --------------------------------------------------------------------------
# The card's band word
# --------------------------------------------------------------------------

@pytest.mark.parametrize(("band", "word"), [
    ("Healthy", "Clean"), ("Not Healthy", "Caution"), ("Slop", "Slop"), ("n/a", "No data"),
])
def test_a_band_the_card_knows_gets_its_word(band, word):
    assert card.band_word(band) == word


def test_a_band_the_card_does_not_know_says_so_rather_than_borrowing_n_a():
    """The row for `n/a` means an indicator declined to grade. An unrecognised band is a
    different fact and has to read differently, or the card reports a refusal that never
    happened."""
    word = card.band_word("Radiant")
    assert word != "No data"
    assert "Radiant" in word


def test_an_empty_band_is_still_an_unknown_band():
    assert "No data" not in card.band_word("")


# --------------------------------------------------------------------------
# The call map's effect vocabulary
# --------------------------------------------------------------------------

def test_a_call_the_vocabulary_knows_names_its_source():
    fn = next(n for n in ast.walk(ast.parse("def f(p):\n    return p.read_text()\n"))
              if isinstance(n, ast.FunctionDef))
    assert callmap.effects(fn) == (["filesystem"], [])


def test_a_call_the_vocabulary_does_not_know_records_no_effect():
    """An unknown call is not a call that touches nothing. It is a call this vocabulary has
    no row for, and the map says so by leaving it out rather than by answering for it."""
    fn = next(n for n in ast.walk(ast.parse("def f(p):\n    return p.frobnicate()\n"))
              if isinstance(n, ast.FunctionDef))
    assert callmap.effects(fn) == ([], [])


# --------------------------------------------------------------------------
# The region table
# --------------------------------------------------------------------------

def test_a_type_with_a_region_table_yields_its_regions():
    fn = next(n for n in ast.walk(ast.parse("def f(n: int) -> None:\n    pass\n"))
              if isinstance(n, ast.FunctionDef))
    regions, _undeclared = facets._region_facets(fn, {})
    assert {f["detail"].rsplit(" ", 1)[-1] for f in regions} == {"zero", "positive", "negative"}


def test_a_type_with_no_region_table_is_read_by_membership_rather_than_by_default():
    """`Path` has no canonical boundary regions, which is a different fact from a type
    whose table happens to be empty. The membership test is what says which."""
    assert "Path" not in facets._REGIONS
    fn = next(n for n in ast.walk(ast.parse("def f(p: Path) -> None:\n    pass\n"))
              if isinstance(n, ast.FunctionDef))
    regions, undeclared = facets._region_facets(fn, {})
    assert regions == [] and undeclared == []


# --------------------------------------------------------------------------
# The god-file language table
# --------------------------------------------------------------------------

def test_a_known_extension_maps_to_its_grammar():
    assert indicators.god_file_language(".py") == "python"


def test_an_unknown_extension_has_no_grammar_rather_than_an_empty_one():
    """The empty string was standing in for both "this extension has no grammar" and a
    grammar key, and `_LITERAL_NODES` was then asked about it."""
    assert indicators.god_file_language(".frob") is None

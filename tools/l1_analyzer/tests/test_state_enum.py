"""The per-language instance-state dispatch table, and the row that reads nothing.

_INSTANCE_CANDS is subscripted, never `.get`: a language whose `instance_enum` names no row
must fail loudly rather than quietly enumerate no state. That choice is what makes the empty
row worth pinning. `_no_instance` is not an oversight and not a stub - it is the answer for
C and Go, whose state is not held in a class body at all, and it is what keeps the table
total so the subscript cannot raise.

A function that returns nothing still has two things a test can hold: that it returns
NOTHING (a row quietly growing a return value would double-count state that another walk
already reports), and that the languages routed to it do get their state read somewhere
else. Both are asserted below, so "reads nothing here" stays distinguishable from "reads
nothing anywhere", which is the failure an empty row would otherwise hide.
"""

import pytest
from l1_analyzer import state_enum
from l1_analyzer.indicators import LANG_CFG, _get_parser
from l1_analyzer.lang_spec import LANG_SPEC

_GO = b"""package m

type Cache struct { entries map[string]int }

func (c *Cache) Put(k string, v int) { c.entries[k] = v }
"""

_C = b"""
static int cache[256];
struct S { int n; };
int get(int i) { return cache[i]; }
"""


def _root(lang: str, src: bytes):
    return _get_parser(lang).parse(src).root_node


@pytest.mark.parametrize("lang,src", [("go", _GO), ("c", _C)])
def test_the_empty_row_reads_no_instance_state(lang, src):
    """Called directly, with a real node and a real spec, it yields an empty map. The row
    exists to say "this language holds no state where this walk looks", and an empty Cands
    is how the walk says that: no site visited, no key claimed."""
    assert state_enum._no_instance(_root(lang, src), LANG_SPEC[lang]) == {}


def test_the_empty_row_ignores_a_node_that_does_declare_fields():
    """Handed a C struct with a field in it, the row still reads nothing. That is the point:
    the field is read by record_state's c_struct_field walk, and a second reading here would
    publish the same slot twice and inflate every count computed over findings."""
    struct = next(n for n in _root("c", _C).named_children if n.type == "struct_specifier")
    assert state_enum._no_instance(struct, LANG_SPEC["c"]) == {}


@pytest.mark.parametrize("lang", ["c", "go"])
def test_the_dispatch_resolves_for_the_languages_routed_to_the_empty_row(lang):
    """Through instance_cands and instance_keys, not around them. The subscript on
    _INSTANCE_CANDS is what would raise if the row were deleted, so this is the assertion
    that the row is carrying its weight."""
    assert LANG_SPEC[lang]["instance_enum"] == "none"
    root = _root(lang, _GO if lang == "go" else _C)
    assert state_enum.instance_cands(root, LANG_SPEC[lang]) == {}
    assert state_enum.instance_keys(root, LANG_SPEC[lang]) == []


def test_every_language_names_a_row_that_exists():
    """Totality, checked over the spec table rather than over a hand-written list. A new
    language whose instance_enum is misspelled fails here instead of raising a KeyError in
    the middle of a scan."""
    named = {sp["instance_enum"] for sp in LANG_SPEC.values() if "instance_enum" in sp}
    assert named <= set(state_enum._INSTANCE_CANDS)
    assert state_enum._INSTANCE_CANDS["none"] is state_enum._no_instance


def test_go_state_is_read_by_the_receiver_walk_instead():
    """The other half of the claim. Go groups state by receiver type, not by class body, so
    `c.entries` is found by go_slots. If this ever went empty, the empty instance row would
    have become a real hole and the test above would no longer be measuring anything."""
    assert [s["state"] for s in state_enum.go_slots(_root("go", _GO))] == ["Cache.entries"]


def test_c_state_is_read_at_file_scope_instead():
    """And C's. `static int cache[256]` is module state to this reader, enumerated by the C
    module walk. Struct fields are read by record_state, which is a different module."""
    cands = state_enum.module_cands(_root("c", _C), LANG_SPEC["c"], LANG_CFG["c"])
    assert state_enum.keys_of(cands) == ["cache"]

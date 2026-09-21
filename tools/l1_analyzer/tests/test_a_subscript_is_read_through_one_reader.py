"""A grammar's subscript shape is read in one place, and a keyed store is seen in all nine.

Eight of the nine grammars name the two halves of `d[k]` with fields. Rust names neither:
its index expression holds the collection and the key by position. `sub_collection` and
`sub_key` exist to hide that difference, and four readers went round them and asked the
table for the field name directly.

What it cost: a Rust field written by key was invisible to three rules at once. A map
written on every call read as assigned once and never mutated, so the write-once rule
cleared it; a Rust counter passed the plain-stores check the counter rule exists to fail;
and a Rust cache read as one nothing ever writes. Python and Ruby saw all three. Nobody
noticed, because every rule kept answering and only one language's answers were wrong.

The same module held a second copy of a second reader. `_is_open_key` peeled its own list of
wrappers off a subscript key, and the cell reader peeled another, so the two disagreed about
`self.cache[(1)]` in Python and Java and `c.cache[&1]` in Rust: an open key to one and a
bounded value to the other. An open key is what KEEPS a finding, so a container indexed by a
constant was accused of being unbounded.

The tests here ask two different questions. Most are about behaviour, and would pass again
if somebody reintroduced a shortcut and happened to get the languages right. One is about
the shape: nothing outside ts_nodes may read the raw subscript keys at all, so the next
reader cannot make this mistake in a grammar nobody has added yet.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import state_bounds_filters as filters
from l1_analyzer import state_ref_reads as reads
from l1_analyzer.indicators import parser_for
from l1_analyzer.lang_spec import LANG_SPEC
from l1_analyzer.state_cells import is_unbounded_value
from l1_analyzer.ts_nodes import descendants, sub_key

PACKAGE = Path(__file__).resolve().parent.parent / "l1_analyzer"

# The raw table keys that say how one grammar spells a subscript. Reading them outside the
# two functions that exist to answer that question is what this test forbids.
RAW_KEYS = ("sub_value", "sub_index", "sub_positional")

# One class per language, each holding a map written by key and nothing else. The shape is
# the same program three ways, so the three answers have to be the same three answers.
A_MAP_WRITTEN_BY_KEY = {
    "python": (".py", """\
class C:
    def __init__(self):
        self.cache = {}
    def bump(self, k, n):
        self.cache[k] = n
""", "cache"),
    "ruby": (".rb", """\
class C
  def initialize
    @cache = {}
  end
  def bump(k, n)
    @cache[k] = n
  end
end
""", "@cache"),
    "rust": (".rs", """\
use std::collections::HashMap;
pub struct C { cache: HashMap<String, u32> }
impl C {
    pub fn new() -> Self { C { cache: HashMap::new() } }
    pub fn bump(&mut self, k: String, n: u32) { self.cache[&k] = n; }
}
""", "cache"),
}


def references(lang: str) -> tuple[list, dict, str]:
    """Every reference to the map in one language's copy of the program."""
    suffix, source, attr = A_MAP_WRITTEN_BY_KEY[lang]
    spec = LANG_SPEC[lang]
    root = parser_for(suffix, lang).parse(source.encode()).root_node
    refs = [n for n in descendants(root, "all")
            if reads.names_the_attribute(n, attr, spec)]
    assert refs, f"the {lang} fixture holds no reference to {attr}"
    return refs, spec, attr


def test_a_keyed_store_is_a_mutation_in_every_grammar() -> None:
    for lang in A_MAP_WRITTEN_BY_KEY:
        refs, spec, attr = references(lang)
        assert filters._mutated_in_place(refs, attr, spec), (
            f"{lang}: a map written at a key every call read as never mutated, "
            "so the write-once rule cleared it")


def test_a_keyed_store_is_a_store_in_every_grammar() -> None:
    for lang in A_MAP_WRITTEN_BY_KEY:
        refs, spec, _ = references(lang)
        assert filters._stores_into(refs, spec), (
            f"{lang}: a map written at a key read as one nothing ever writes")


def test_only_the_node_readers_know_how_a_subscript_is_spelled() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in ("ts_nodes.py", "lang_spec.py"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for key in RAW_KEYS:
            if f'"{key}"' in text or f"'{key}'" in text:
                offenders.append(f"{path.name} reads {key}")
    assert not offenders, (
        "read a subscript through sub_collection or sub_key, which already know that Rust "
        "holds both halves by position: " + "; ".join(offenders))


# A parenthesised literal and a borrowed literal are the same single compile-time value the
# bare literal is. The open-key guard peeled only unary operators and the cell reader peeled
# every wrapper, so the two called `self.cache[(1)]` different things: an open key here, a
# bounded value there. An open key is what KEEPS a finding, so the disagreement accused a
# container indexed by a constant.
A_LITERAL_IN_A_WRAPPER = [
    ("python", ".py", "x = self.cache[(1)]\n", "subscript"),
    ("python", ".py", "x = self.cache[-1]\n", "subscript"),
    ("java", ".java", "class C { void f() { int x = cache[(1)]; } }\n", "array_access"),
    ("rust", ".rs", "fn f(c: &C) { let x = c.cache[&1]; }\n", "index_expression"),
]

A_VARIABLE_IN_A_WRAPPER = [
    ("python", ".py", "x = self.cache[(k)]\n", "subscript"),
    ("rust", ".rs", "fn f(c: &C, k: u32) { let x = c.cache[&k]; }\n", "index_expression"),
]


def a_key(lang: str, suffix: str, source: str, kind: str):
    spec = LANG_SPEC[lang]
    root = parser_for(suffix, lang).parse(source.encode()).root_node
    subscript = next(n for n in descendants(root, "all") if n.type == kind)
    return sub_key(subscript, spec), spec


def test_a_wrapped_literal_is_not_an_open_key() -> None:
    for lang, suffix, source, kind in A_LITERAL_IN_A_WRAPPER:
        key, spec = a_key(lang, suffix, source, kind)
        assert not filters._is_open_key(key, spec), (
            f"{lang}: {source.strip()} indexes by a constant and was called an open key")
        assert not is_unbounded_value(key, spec), f"{lang}: the two readers disagree"


def test_a_wrapped_variable_is_still_an_open_key() -> None:
    for lang, suffix, source, kind in A_VARIABLE_IN_A_WRAPPER:
        key, spec = a_key(lang, suffix, source, kind)
        assert filters._is_open_key(key, spec), (
            f"{lang}: {source.strip()} indexes by a parameter and stopped being an open key")
        assert is_unbounded_value(key, spec), f"{lang}: the two readers disagree"

"""Two functions written twice, differing only in words the vocabulary already holds.

The thread-safety reader carries `_rust_method_receiver` and `_js_method_receiver`, and
`_rust_receivers_by_method` and `_js_receivers_by_method`. Each pair is one function. What
differs is four facts:

    rust        call_expression   field_expression    field      value    self
    javascript  call_expression   member_expression   property   object   this

Every one of those four is in the per-language vocabulary the clause checkers already read,
and has been since before this module was written. This module hardcoded them instead, so
adding a language here means writing the pair a third time rather than adding a row.

Our own duplication check put this file at the top of the list: 98 lines across 23 runs, the
largest single contributor left in the repository.
"""

import pytest
from l1_analyzer import thread_surface
from l1_analyzer.indicators import _get_parser
from l1_analyzer.lang_spec import LANG_SPEC

_CALLS = {
    "rust": ("fn go(&self) {\n    if self.count.load() { self.count.store(1); }\n}\n",
             "self.count"),
    "javascript": ("function go() {\n  if (this.count.has(k)) { this.count.set(k, 1); }\n}\n",
                   "this.count"),
}


def _root(source: str, lang: str):
    return _get_parser(lang).parse(source.encode()).root_node


@pytest.mark.parametrize("lang", list(_CALLS))
def test_the_receiver_of_a_method_call_is_read_in_every_language(lang):
    source, expected = _CALLS[lang]
    root = _root(source, lang)
    found = set()
    for node in thread_surface._walk(root):
        pair = thread_surface.method_receiver(node, LANG_SPEC[lang])
        if pair is not None:
            found.add(pair[1])
    assert expected in found, (lang, found)


@pytest.mark.parametrize("lang", list(_CALLS))
def test_receivers_are_collected_by_method_in_every_language(lang):
    source, expected = _CALLS[lang]
    methods = frozenset({"load", "has"})
    got = thread_surface.receivers_by_method(_root(source, lang), methods, LANG_SPEC[lang])
    assert got == {expected}, (lang, got)


@pytest.mark.parametrize("lang", list(_CALLS))
def test_a_receiver_that_is_not_the_object_itself_is_left_out(lang):
    """The rule both copies enforced: only state hanging off the object is shared state.
    A local variable's method call is not."""
    source = {"rust": "fn go(&self) {\n    let v = other.count.load();\n}\n",
              "javascript": "function go() {\n  const v = other.count.has(k);\n}\n"}[lang]
    got = thread_surface.receivers_by_method(_root(source, lang), frozenset({"load", "has"}),
                                             LANG_SPEC[lang])
    assert got == set(), (lang, got)


def test_no_language_keeps_its_own_copy():
    """The shape, asserted rather than described. A third copy is the duplication coming
    back, and it comes back one language at a time."""
    import inspect

    source = inspect.getsource(thread_surface)
    for gone in ("_rust_method_receiver", "_js_method_receiver",
                 "_rust_receivers_by_method", "_js_receivers_by_method"):
        assert f"def {gone}" not in source, gone


def test_the_four_facts_come_from_the_vocabulary():
    """Which is the point: a language is a row, not a pair of functions. All four were in
    the table before this module was written."""
    for lang in ("rust", "javascript", "python"):
        spec = LANG_SPEC[lang]
        assert spec["call_types"] and spec["member_types"]
        assert spec["mem_attr"] and spec["mem_object"] and spec["this_idents"]


def test_every_scanner_in_the_table_takes_the_vocabulary():
    """The gap an adopter found while this was half-converted, and named exactly.

    The call site hands three arguments to whichever scanner the language selects. Two of
    seven had been converted, so the other five crashed on any repository in those
    languages, and the tests above went green over it because they only cover the two.

    A test that walks the TABLE cannot do that: every row is checked, and a language added
    tomorrow is checked the day it is added."""
    import inspect

    for lang, scanner in thread_surface._SCANNERS.items():
        taken = list(inspect.signature(scanner).parameters)
        assert taken[-1] == "spec", (lang, scanner.__name__, taken)


def test_every_language_in_the_table_can_be_scanned():
    """The same gap from the other side, exercised rather than inspected. A signature that
    accepts the argument and a body that cannot use it are different things."""
    sources = {
        "rust": "fn go(&self) { self.n.store(1); }\n",
        "python": "count = {}\n\n\ndef go():\n    count['a'] = 1\n",
        "javascript": "function go() { this.n.set('a', 1) }\n",
        "typescript": "function go() { this.n.set('a', 1) }\n",
        "go": "func go() { m[\"a\"] = 1 }\n",
        "java": "class A { static int n; void go() { n = 1; } }\n",
        "ruby": "class A\n  @@n = 0\n  def go\n    @@n = 1\n  end\nend\n",
    }
    for lang, scanner in thread_surface._SCANNERS.items():
        root = _get_parser(lang).parse(sources[lang].encode()).root_node
        found = scanner(root, f"a.{lang}", LANG_SPEC[lang])
        assert isinstance(found, list), (lang, found)

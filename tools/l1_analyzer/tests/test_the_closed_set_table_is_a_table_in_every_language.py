"""Every language's reader is handed a table of closed sets, empty or not.

Python got `_collect_closed_sets(root)`, a mapping of name to bound. Every other language
got `set()`, under a parameter declared eight times over as a mapping of name to bound.

It does not crash today, and saying so is the point: three readers call `.get` on that
value, and a set has no `.get`, but the predicate gating each of them asks `name in
closed_sets` first and an empty set answers no to everything. The wrong shape is reachable
only through a gate that the wrong shape happens to close. Nothing about that is a design.

The branch was `sp is LANG_SPEC["python"]`, the language conditional welded into shared code
that this package removed from the function two hundred lines above this one and left here.
The comment there says why: a table row gets the rule for nine languages, an identity check
gets it for one.
"""

import pytest
from l1_analyzer import state_bounds
from l1_analyzer.lang_spec import LANG_SPEC

_JS = ("const cache = {};\nexport function f(k) {\n"
       "  if (cache[k]) { return 1; }\n  cache[k] = 2;\n  return 0;\n}\n")
_RUBY = "$cache = {}\ndef f(k)\n  return 1 if $cache[k]\n  $cache[k] = 2\n  0\nend\n"
_GO = ("package main\n\nvar cache = map[string]int{}\n\n"
       "func F(k string) int {\n\tif cache[k] > 0 {\n\t\treturn 1\n\t}\n"
       "\tcache[k] = 2\n\treturn 0\n}\n")

_KEYED_READ = {"javascript": ("a.js", _JS), "ruby": ("a.rb", _RUBY), "go": ("a.go", _GO)}


@pytest.mark.parametrize("lang", sorted(_KEYED_READ))
def test_a_keyed_read_in_another_language_does_not_raise(tmp_path, lang):
    name, source = _KEYED_READ[lang]
    (tmp_path / name).write_text(source)
    reading = state_bounds.classify(tmp_path, lang)
    assert reading["band"]


def test_every_language_declares_whether_it_has_a_closed_set_rule():
    """A table row rather than an identity check on one spec object. The rule the package
    states for itself: a language conditional welded into shared code gets the rule for one
    language, and a row gets it for nine."""
    for lang, spec in LANG_SPEC.items():
        assert "closed_set_rule" in spec, lang


def test_the_reader_no_longer_asks_which_spec_object_it_holds():
    import inspect

    source = inspect.getsource(state_bounds._analyze_file)
    assert 'LANG_SPEC["python"]' not in source, source

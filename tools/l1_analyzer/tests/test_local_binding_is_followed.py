"""A state copied into a local is followed through the local (L1.18b).

The largest family left in the corpus's silence, 194 sites: `var entries = _entries;`
and then whatever the method does with `entries`. Every one of them was reported as
`unmodeled_construct`, a rule we had not written.

I claimed this needed local dataflow the AST does not carry. That was wrong, and
checking it is what produced this file. The AST carries the link:

    java    variable_declarator  fields name AND value
    python  assignment           fields left AND right
    csharp  variable_declarator  field name; the initialiser is the last named child,
                                 present but unnamed

So the binding is there in all three, by field in two of them and by position in the
third. The classifier already finds references inside a scope, which is how it reads
class state. Following a local is that same walk, bounded to the enclosing function.

What the AST genuinely does NOT carry is whether the copy aliases: `var e = _entries`
shares the object for a reference type and copies it for a value type, and tree-sitter
resolves no types. That matters only for a WRITE through the local reaching the state.
For the question this classifier asks -- what does the state's value reach -- following
the local's reads is enough, and a write through the local keeps its own refusal.
"""

import pathlib
import tempfile

import pytest

from l1_analyzer import state_bounds

_CASES = {
    "java": ("M.java", "class A {\n"
                       "  java.util.Map<String,Integer> m;\n"
                       "  int q(String k) {\n"
                       "    var local = m;\n"
                       "    if (local.containsKey(k)) { return 1; }\n"
                       "    return 0;\n  }\n}\n", "m"),
    "csharp": ("m.cs", "class A {\n"
                       "  System.Collections.Generic.Dictionary<string,int> _m;\n"
                       "  int Q(string k) {\n"
                       "    var local = _m;\n"
                       "    if (local.ContainsKey(k)) { return 1; }\n"
                       "    return 0;\n  }\n}\n", "_m"),
}


def _finding(lang: str, state_ends: str) -> dict:
    filename, src, _ = _CASES[lang]
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d)
        (p / filename).write_text(src)
        r = state_bounds.classify(p, lang)
        return next((f for f in r["findings"] if f["state"].endswith(state_ends)), {})


@pytest.mark.parametrize("lang", sorted(_CASES))
def test_a_state_copied_into_a_local_is_not_reported_as_an_unread_construct(lang):
    f = _finding(lang, _CASES[lang][2])
    assert f, "the state should still be found"
    assert f["construct"] == "", f'still an unread construct: {f["construct"]!r}'

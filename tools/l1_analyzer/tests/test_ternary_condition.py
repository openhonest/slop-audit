"""A ternary condition is a condition (L1.18b).

`if (_f) { return 1; } return 0;` reads finite with two classes. `return _f ? 1 : 0;`
read undecided, construct `identifier in conditional_expression`. Same program, two
spellings, one of them read. That is the fifth instance of this shape found on
2026-08-18, after the Rust borrow wrapper, the quoted cast, the C# expression-bodied
member and the Python keyword argument.

The truthiness row already exists and already says the right thing: a state tested for
truth is the same two-class split wherever it is written, sharing one discriminator so
`if S:` in fifty methods is two classes and not fifty-one. A ternary is one of the
places it is written. The fix is the node type joining `branch_types`, and every
language whose grammar names a `condition` field gets it.

Python is deliberately NOT among them. Its `conditional_expression` carries no named
fields at all -- the condition is the second child of `X if C else Y` -- so adding it
would make the analyzer read the consequence as the condition. That needs its own rule
and has its own issue; two sites in the pinned corpus depend on it.
"""

import pathlib
import tempfile

import pytest

from tree_sitter import Parser

from l1_analyzer import state_bounds
from l1_analyzer.indicators import LANG_CFG


def _reach(lang: str, src: str, name: str, line: int) -> dict:
    parser = Parser()
    parser.language = LANG_CFG[lang]["language"]
    root = parser.parse(src.encode()).root_node
    spec = state_bounds.LANG_SPEC[lang]
    closed = state_bounds._collect_closed_sets(root)
    found = []

    def walk(node):
        if not node.children and state_bounds._text(node) == name \
                and node.start_point[0] + 1 == line:
            found.append(state_bounds._categorize(node, spec, closed, None))
        for child in node.children:
            walk(child)

    walk(root)
    assert found, f"no {name} reference on line {line}"
    return found[0]


_TERNARY = {
    "csharp": ("class A {\n  bool _f;\n  int Q() { return _f ? 1 : 0; }\n}\n", "_f", 3),
    "java": ("class A {\n  boolean f;\n  int q() { return f ? 1 : 0; }\n}\n", "f", 3),
    "c": ("struct A { int f; };\nint q(struct A *a) { return a->f ? 1 : 0; }\n", "f", 2),
    # Module-level state, not `this.f`: a property identifier inside a member expression is
    # a separate shape these grammars still leave unread, and a fixture using it would be
    # measuring that instead of the ternary.
    "javascript": ("let f = false;\nfunction q() { return f ? 1 : 0; }\n", "f", 2),
    "typescript": ("let f = false;\nfunction q() { return f ? 1 : 0; }\n", "f", 2),
    "ruby": ("class A\n  def initialize\n    @f = false\n  end\n  def q\n    @f ? 1 : 0\n  end\nend\n", "@f", 6),
}


@pytest.mark.parametrize("lang", sorted(_TERNARY))
def test_a_ternary_condition_is_the_same_two_class_split_as_an_if(lang):
    src, name, line = _TERNARY[lang]
    reach = _reach(lang, src, name, line)
    assert reach["kind"] == "finite", f'still {reach["kind"]}, construct {reach["construct"]!r}'
    assert reach["classes"] == 2


def test_an_arm_of_a_ternary_is_not_read_as_its_condition():
    """The guard. Only the condition decides; a state sitting in the consequence is a
    value being returned and must not be handed a truthiness split it never had."""
    src = "class A {\n  int _v;\n  int Q(bool c) { return c ? _v : 0; }\n}\n"
    reach = _reach("csharp", src, "_v", 3)
    assert not (reach["kind"] == "finite" and reach.get("key") == "truthy")

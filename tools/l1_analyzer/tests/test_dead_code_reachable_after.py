"""Every row of `dead_code._REACHABLE_AFTER` must be able to fire.

The table declares, per language, the node types that stay reachable after a `return` or a
`break` and therefore stop the unreachable-statement scan. A type that the grammar never
emits in that position spares nothing: the row reads as protection and does nothing, and a
reviewer who reads the table believes a guarantee the code does not give. Fifteen of the
sixteen jump-target names in it were exactly that until 2026-08-16 - the switch and match
arms of eight grammars, none of which is ever a sibling of a terminator, because only C
spells a switch body with the same node it uses for every other block.

So this test does not check the table against an opinion about the grammars. It parses one
fixture per language, collects the types that ACTUALLY follow a terminator inside one of that
language's block nodes, and fails on any row entry that never turns up. Adding an unfireable
row is then a red test rather than a comment nobody re-reads.
"""

from __future__ import annotations

import pytest
from l1_analyzer.dead_code import (
    _BLOCK_TYPES,
    _REACHABLE_AFTER,
    _TERMINATORS,
    _is_terminator,
    _skip_in_unreachable_scan,
    _unreachable_statements,
    parser,
)

# One fixture per language, written so that every type its row claims appears after a
# terminator inside a block. Nothing here has to be idiomatic or even compilable - the
# question is only what the grammar emits and where it puts it.
_FIXTURES: dict[tuple[str, str], str] = {
    ("python", "python"): """
def g(x):
    return 1
    def inner(): pass
    class C: pass
    y = 2
""",
    ("rust", "rust"): """
fn g(x: i32) -> i32 {
    return 0;
    fn inner() {}
    macro_rules! mac { () => {} }
    struct S { a: i32 }
    enum E { A }
    union U { a: i32 }
    const C: i32 = 1;
    static ST: i32 = 2;
    type Y = i32;
    use std::fmt;
    mod m {}
    trait T {}
    impl S {}
    extern "C" { fn ext(); }
}
""",
    ("c", "c"): """
int g(int x) {
  return 1;
  int y = 2;
label:
  return y;
}
int s(int x) {
  switch (x) {
    return 0;
    case 1:
      return 1;
    default:
      return 2;
  }
}
""",
    ("java", "java"): """
class A {
  int g(int x) {
    return 1;
    int y = 2;
  }
}
""",
    ("typescript", "typescript"): """
function g(x: number): number {
  return 1;
  function inner(): void {}
  class C {}
  function* gen(): Generator<number> { yield 1; }
  interface I { a: number }
  type T = number;
}
""",
    ("javascript", "javascript"): """
function g(x) {
  return 1;
  function inner() {}
  class C {}
  function* gen() { yield 1; }
}
""",
    ("csharp", "csharp"): """
class A {
  int G(int x) {
    return 1;
    label: x = 3;
    int Inner() { return 2; }
  }
}
""",
    ("ruby", "ruby"): """
def h(x)
  return 1
  def inner; end
  class C; end
  module M; end
rescue => e
  return 2
else
  puts 3
ensure
  puts 4
end
""",
    ("go", "go"): """
package main

func g(x int) int {
	return 1
label:
	return 2
}
""",
}


def _types_after_a_terminator(grammar: str, lang: str, source: str) -> set[str]:
    """The node types that actually sit after a terminator inside a block, by the same walk
    `_unreachable_statements` performs. Reading the real scan rather than a description of it
    is the whole point: a type the scan never reaches cannot be spared by naming it."""
    root = parser(grammar).parse(source.encode()).root_node
    assert not root.has_error, f"the {lang} fixture does not parse; fix the fixture, not the table"
    found: set[str] = set()

    def walk(node) -> None:
        if node.type in _BLOCK_TYPES[lang]:
            seen = False
            for child in node.named_children:
                if _skip_in_unreachable_scan(child.type):
                    continue
                if seen:
                    found.add(child.type)
                elif _is_terminator(child, _TERMINATORS[lang]):
                    seen = True
        for child in node.children:
            walk(child)

    walk(root)
    return found


@pytest.mark.parametrize(("grammar", "lang"), sorted(_FIXTURES))
def test_every_declared_reachable_type_can_follow_a_terminator(grammar: str, lang: str) -> None:
    observed = _types_after_a_terminator(grammar, lang, _FIXTURES[(grammar, lang)])
    dead_rows = sorted(_REACHABLE_AFTER[lang] - observed)
    assert not dead_rows, (
        f"{lang}: _REACHABLE_AFTER names {dead_rows}, which the grammar never puts after a "
        f"terminator inside {sorted(_BLOCK_TYPES[lang])}. Such a row spares nothing and reads "
        f"as protection. Observed after a terminator: {sorted(observed)}")


def test_the_table_covers_every_language_the_scan_runs_over() -> None:
    assert set(_REACHABLE_AFTER) == set(_BLOCK_TYPES) == set(_TERMINATORS)


def test_python_declares_no_reachable_type_rather_than_an_unfireable_one() -> None:
    """The row that named `case_clause` protected nothing: python puts the arms of a `match`
    in a block of their own, so no arm is ever a sibling of a terminator. The honest row is
    empty, and a `def` below a `return` is charged, because it never executes."""
    assert _REACHABLE_AFTER["python"] == frozenset()
    root = parser("python").parse(_FIXTURES[("python", "python")].encode()).root_node
    assert [u["line"] for u in _unreachable_statements(root, "python")] == [4, 5, 6]


def test_a_python_match_arm_is_not_charged_as_unreachable() -> None:
    """The guarantee the deleted `case_clause` row appeared to give, checked at the behaviour
    instead of at the table: a `case` below a `return` is not dead code, and it never was,
    because the arms are the only children of their own block."""
    source = """
def m(x):
    match x:
        case 1:
            return 1
        case 2:
            return 2
        case _:
            return 3
"""
    root = parser("python").parse(source.encode()).root_node
    assert _unreachable_statements(root, "python") == []


def test_a_c_case_after_a_return_is_spared_because_c_shares_its_block_node() -> None:
    """C is the one grammar that spells a switch body `compound_statement`, so a `case` really
    can be the sibling of a terminator there, and really does need the row. Removing
    `case_statement` from the C row would charge the rest of the switch as dead code."""
    source = """
int s(int x) {
  switch (x) {
    return 0;
    case 1:
      return 1;
    default:
      return 2;
  }
}
"""
    root = parser("c").parse(source.encode()).root_node
    assert _unreachable_statements(root, "c") == []


def test_a_label_below_a_terminator_is_spared_only_where_goto_can_reach_it() -> None:
    """Go has a forward `goto`, so a label below a `return` is a real entry point. JavaScript
    labels only `break label`, which is reached from inside the labeled statement, so a label
    below a `return` there is dead and is charged."""
    go_source = """
package main

func g(x int) int {
	if x > 0 {
		goto label
	}
	return 1
label:
	return 2
}
"""
    js_source = """
function g(x) {
  return 1;
  label: { x = 2; }
}
"""
    assert _unreachable_statements(parser("go").parse(go_source.encode()).root_node, "go") == []
    js = _unreachable_statements(parser("javascript").parse(js_source.encode()).root_node, "javascript")
    assert [u["line"] for u in js] == [4]

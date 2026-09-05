"""A tree walk must not run out of stack on code somebody else wrote.

Parse-tree depth is set by the file being audited, which is unbounded input. A walk that
recurses once per level therefore has a ceiling nobody chose, and Python's is a thousand
frames. On 2026-09-05 five repositories of the two hundred measured crashed with a recursion
error, and they were the five largest: the JDK, the dotnet runtime, GraalVM, Seata and
Remotion. The instrument could not read the codebases where its claim matters most.

`honest_code_read.walk` already had the right shape, an explicit stack and no recursion, and
the accessors here did not. One correct copy and twenty recursive ones is the two-owners
defect, and the crash is what it costs.

Order is the reason a swap is not free. `refs` promises source order, and a stack pops last
in first out, so children go on reversed to come off in order. The last test here holds
that, because a walk that returns the right nodes in the wrong order breaks every caller
that reads the first reference as the declaration.
"""

import pytest
from l1_analyzer.indicators import _get_parser
from l1_analyzer.ts_nodes import local_refs, refs


def _deep(levels: int) -> str:
    """A Python expression nested `levels` deep. Each level is one parse-tree level."""
    return "x = " + "(" * levels + "1" + ")" * levels + "\n"


def _tree(source: str):
    return _get_parser("python").parse(source.encode()).root_node


@pytest.mark.parametrize("levels", [100, 2000])
def test_a_deeply_nested_file_is_walked_rather_than_crashing(levels):
    """Two thousand levels is past Python's default frame limit and well inside what a
    generated file or a long chained expression reaches."""
    found = refs(_tree(_deep(levels)), lambda n: n.type == "integer")
    assert len(found) == 1


def test_the_scoped_walk_survives_the_same_depth():
    found = local_refs(_tree(_deep(2000)), lambda n: n.type == "integer", stop=("class_definition",))
    assert len(found) == 1


def test_references_come_back_in_source_order():
    """The promise `refs` makes, and the one a stack breaks if children go on unreversed.
    A caller reading the first reference as the declaration gets the last one instead."""
    source = "a = 1\nb = 2\nc = 3\n"
    names = [n.text.decode() for n in refs(_tree(source), lambda n: n.type == "identifier")]
    assert names == ["a", "b", "c"]


def test_the_scoped_walk_keeps_source_order_too():
    source = "a = 1\nb = 2\nc = 3\n"
    names = [n.text.decode()
             for n in local_refs(_tree(source), lambda n: n.type == "identifier",
                                 stop=("class_definition",))]
    assert names == ["a", "b", "c"]


def test_the_scoped_walk_still_refuses_to_enter_a_nested_record():
    """The rule it exists for. An inner class owns its own fields, and an enclosing class
    that harvested them would count the same state twice."""
    source = "class Outer:\n    a = 1\n\n    class Inner:\n        b = 2\n"
    names = [n.text.decode()
             for n in local_refs(_tree(source), lambda n: n.type == "identifier",
                                 stop=("class_definition",))]
    assert "b" not in names

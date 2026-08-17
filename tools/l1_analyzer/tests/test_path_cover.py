"""Tests for the minimum end-to-end path cover (the Eulerian walk count).

The graph-math cases are hand-checked; the CFG cases parse real Python and assert
the attainable number of runs that cover every branch. Pure assertions, no mocks.
"""

import itertools

from l1_analyzer.indicators import _BODY_NODE_TYPES, LANG_CFG, _get_parser
from l1_analyzer.path_cover import _cfg_match, function_cover, min_path_cover

S, T = "entry", "exit"


def test_straight_line_needs_one():
    assert min_path_cover([(S, T)], S, T) == 1


def test_if_else_needs_two():
    assert min_path_cover([(S, "x"), (S, "y"), ("x", T), ("y", T)], S, T) == 2


def test_single_if_needs_two():
    # then-edge and skip-edge both must be walked.
    assert min_path_cover([(S, "x"), ("x", "m"), (S, "m"), ("m", T)], S, T) == 2


def test_sequential_ifs_pair_up_to_two():
    edges = [(S, "a1"), (S, "a2"), ("a1", "m1"), ("a2", "m1"),
             ("m1", "b1"), ("m1", "b2"), ("b1", "m2"), ("b2", "m2"), ("m2", T)]
    assert min_path_cover(edges, S, T) == 2


def test_nested_if_needs_three():
    edges = [(S, "a1"), (S, "a2"), ("a1", "x1"), ("a1", "x2"),
             ("x1", "mi"), ("x2", "mi"), ("mi", "m"), ("a2", "m"), ("m", T)]
    assert min_path_cover(edges, S, T) == 3


def test_three_way_switch_needs_three():
    edges = [(S, "a"), (S, "b"), (S, "c"), ("a", T), ("b", T), ("c", T)]
    assert min_path_cover(edges, S, T) == 3


def _first_function_body(src):
    parser = _get_parser("python")
    root = parser.parse(src.encode()).root_node

    def find(n):
        if n.type in LANG_CFG["python"]["function_types"]:
            return next((c for c in n.children if c.type in _BODY_NODE_TYPES), None)
        for c in n.children:
            got = find(c)
            if got is not None:
                return got
        return None

    return find(root)


def _cover(src):
    return function_cover(_first_function_body(src))


def test_pure_no_branch_is_one():
    assert _cover("def f(a, b):\n    return a + b\n") == 1


def test_one_if_is_two():
    assert _cover("def f(a):\n    if a > 0:\n        return 1\n    return 0\n") == 2


def test_if_elif_else_is_three():
    src = "def f(a):\n    if a > 0:\n        return 1\n    elif a < 0:\n        return -1\n    else:\n        return 0\n"
    assert _cover(src) == 3


def test_two_sequential_ifs_pair_to_two():
    src = "def f(a, b):\n    x = 0\n    if a:\n        x = 1\n    if b:\n        x = 2\n    return x\n"
    assert _cover(src) == 2


def test_simple_loop_is_one():
    # One run that enters the loop and then exits walks both the enter-edge and
    # the exit-edge, so edge coverage needs a single end-to-end run.
    src = "def f(items):\n    total = 0\n    for it in items:\n        total += it\n    return total\n"
    assert _cover(src) == 1


def test_repo_cover_sums_per_function(tmp_path):
    from l1_analyzer.path_cover import cover_paths
    # pure_add -> 1, one_if -> 2, elif -> 3. Total 6 across 3 functions.
    (tmp_path / "m.py").write_text(
        "def pure_add(a, b):\n    return a + b\n\n"
        "def one_if(a):\n    if a > 0:\n        return 1\n    return 0\n\n"
        "def elif_(a):\n    if a > 0:\n        return 1\n    elif a < 0:\n        return -1\n    else:\n        return 0\n"
    )
    r = cover_paths(tmp_path, "python")
    assert r["functions"] == 3
    assert r["value"] == 6


def test_repo_cover_non_python_is_na(tmp_path):
    from l1_analyzer.path_cover import cover_paths
    assert cover_paths(tmp_path, "go")["value"] == "n/a"


# --- match statements: one arm, one edge -----------------------------------
#
# _cfg_match is the builder the arm count runs through, and the arm count is what the
# path cover turns on: n arms out of one control point are n walks, because no single
# run can take two of them. The builder is called directly here so the edges it emits
# are visible, rather than only their flow-network summary.

def _match_statement(src):
    """The first match_statement in the first function of `src`."""
    body = _first_function_body(src)
    return next(c for c in body.named_children if c.type == "match_statement")


def _built(src, cur="entry", brk=None, cont=None):
    """(returned control point, edges) from building one match statement. Ids come from
    a fresh counter, so merge is 1 and the arms are 2, 3, ... in source order."""
    edges = []
    out = _cfg_match(edges, itertools.count(1), _match_statement(src), cur, brk, cont)
    return out, edges


_THREE_ARMS = ("def f(x):\n    match x:\n        case 1:\n            a = 1\n"
               "        case 2:\n            return 2\n        case _:\n            b = 3\n")


def test_each_arm_gets_its_own_edge_from_the_match_and_rejoins_at_the_merge():
    out, edges = _built(_THREE_ARMS)
    assert out == 1                                     # the merge block, freshly numbered
    assert ("entry", 2) in edges and ("entry", 3) in edges and ("entry", 4) in edges
    assert (2, 1) in edges and (4, 1) in edges          # the two arms that fall through


def test_an_arm_that_returns_reaches_the_exit_and_not_the_merge():
    """Arm 2 is `return 2`. _build_block hands back None for control that does not fall
    through, and _cfg_edge drops an edge with a None end, so the arm joins no merge."""
    _out, edges = _built(_THREE_ARMS)
    assert (3, "exit") in edges
    assert (3, 1) not in edges


def test_the_match_emits_a_no_case_matched_edge_even_with_a_wildcard_arm():
    """Real behaviour, and it costs a walk. `case _` matches everything, so falling past
    every arm is impossible here, but the builder adds the cur->merge edge unconditionally.
    Edge coverage therefore asks for a fourth run over a three-arm exhaustive match. The
    number is honest about the graph and conservative about the code: it over-counts, it
    never reports a branch as covered that no run reaches."""
    _out, edges = _built(_THREE_ARMS)
    assert ("entry", 1) in edges
    assert function_cover(_first_function_body(_THREE_ARMS)) == 4


def test_a_match_with_no_case_clauses_adds_nothing_and_leaves_control_where_it_was():
    """A match whose body holds no case_clause is not a branch. The builder returns `cur`
    unchanged rather than the merge it had already numbered, so the following statement
    hangs off the same control point and no phantom edge enters the cover."""
    src = "def g(x):\n    match x:\n        pass\n"
    stmt = _match_statement(src)
    assert not [c for c in stmt.child_by_field_name("body").named_children if c.type == "case_clause"]
    out, edges = _built(src)
    assert out == "entry"
    assert edges == []


def test_an_arm_that_breaks_uses_the_enclosing_loop_targets():
    """brk and cont are threaded through to the arm bodies, so a `break` inside a case arm
    leaves for the loop exit the caller supplied and not for the match's own merge."""
    src = ("def f(xs):\n    for x in xs:\n        match x:\n            case 1:\n"
           "                break\n            case _:\n                pass\n")
    body = _first_function_body(src)
    loop = next(c for c in body.named_children if c.type == "for_statement")
    stmt = next(c for c in loop.child_by_field_name("body").named_children if c.type == "match_statement")
    edges = []
    _cfg_match(edges, itertools.count(1), stmt, "entry", brk="after-loop", cont="header")
    assert (2, "after-loop") in edges
    assert (2, 1) not in edges


def test_more_arms_means_more_walks():
    """The cover is the arm count plus the fall-past edge, which is the whole reason the
    builder numbers a block per arm instead of collapsing the match."""
    def cover_with(n):
        arms = "".join(f"        case {i}:\n            a = {i}\n" for i in range(n))
        return _cover(f"def f(x):\n    match x:\n{arms}    return a\n")

    assert [cover_with(n) for n in (1, 2, 3)] == [2, 3, 4]

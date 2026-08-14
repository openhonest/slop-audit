"""Tests for the minimum end-to-end path cover (the Eulerian walk count).

The graph-math cases are hand-checked; the CFG cases parse real Python and assert
the attainable number of runs that cover every branch. Pure assertions, no mocks.
"""

from l1_analyzer.indicators import _BODY_NODE_TYPES, LANG_CFG, _get_parser
from l1_analyzer.path_cover import function_cover, min_path_cover

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

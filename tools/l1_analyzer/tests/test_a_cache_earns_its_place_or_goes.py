"""The last four Honest Code findings in this package, and what each one turned out to be.

Rule 9 says profile before you cache. Two `lru_cache` decorators were flagged and measuring
them separated one from the other completely.

Building a tree-sitter parser costs about a hundredth of a millisecond, and the cache was
hit once per file, so it saved a few milliseconds across an entire audit. Its own docstring
says it was never added for speed: it replaced a module-level dict that L1.18 flagged as
written external state. A plain call does the same job with no cache and no global.

Walking a directory to decide whether it holds tests costs 1.8 milliseconds over this
project's 464 test-tree entries, and it is called once per file being scoped. Without the
cache that one directory costs 464 walks, and the cost grows as the square of the tree. That
cache earns its place, and the test below measures it rather than asserting it, so the
justification cannot quietly stop being true.

Rule 11 was a type check the signature had already made, and the repair is the one the rule
names: resolve the untyped payload once at the boundary, then let the interior trust it.
"""

import time

import pytest
from l1_analyzer import dead_code, report, scope

# --------------------------------------------------------------------------
# The cache that did not earn its place
# --------------------------------------------------------------------------

def test_a_parser_is_built_on_demand_rather_than_cached():
    """Measured before removing it: about a hundredth of a millisecond per build, hit once
    per file. A cache that saves milliseconds across a whole audit is paying an
    invalidation risk for nothing."""
    assert not hasattr(dead_code.parser, "cache_info"), (
        "the parser is cached again; measure the build cost before adding one back")


def test_building_a_parser_is_cheap_enough_to_do_every_time():
    """The measurement the removal rests on, kept so it stays true. If a grammar ever
    becomes expensive to load, this fails and the decision gets made again with a number."""
    started = time.perf_counter()
    for _ in range(50):
        dead_code.parser("python")
    each = (time.perf_counter() - started) / 50
    assert each < 0.002, f"{each * 1000:.2f}ms per parser build is no longer negligible"


def test_the_parser_still_parses():
    tree = dead_code.parser("python").parse(b"def f():\n    return 1\n")
    assert tree.root_node.type == "module"


# --------------------------------------------------------------------------
# The cache that does
# --------------------------------------------------------------------------

def test_the_directory_walk_is_expensive_enough_to_cache(tmp_path):
    """The justification, measured rather than argued. A directory holding many files is
    walked once per file scoped underneath it, so the uncached cost is quadratic.

    This is the evidence rule 9 asks for before a cache is added, and keeping it here means
    the claim cannot quietly stop being true."""
    for n in range(300):
        (tmp_path / f"test_{n}.py").write_text("def test_x():\n    assert True\n")
    uncached = scope._test_dir_corroborated.__wrapped__

    started = time.perf_counter()
    uncached(tmp_path)
    one_walk = time.perf_counter() - started

    scope._test_dir_corroborated(tmp_path)
    started = time.perf_counter()
    for _ in range(50):
        scope._test_dir_corroborated(tmp_path)
    cached = (time.perf_counter() - started) / 50

    assert one_walk > cached * 100, (
        f"one walk costs {one_walk * 1000:.2f}ms against {cached * 1000:.4f}ms cached, "
        "which is no longer the margin this cache was kept for")
    assert one_walk * 300 > 0.05, (
        "walking this directory once per file underneath it is no longer expensive, so "
        "the cache should go the way the parser's did")


def test_the_directory_answer_is_the_same_either_way(tmp_path):
    """A cache that changes the answer is not a cache."""
    (tmp_path / "test_a.py").write_text("def test_x():\n    assert True\n")
    assert scope._test_dir_corroborated.__wrapped__(tmp_path) is True
    assert scope._test_dir_corroborated(tmp_path) is True


# --------------------------------------------------------------------------
# The check the signature had already made
# --------------------------------------------------------------------------

def test_the_grade_reader_trusts_its_own_type():
    """`isinstance(l18b, dict)` re-checked what the signature declares, so a caller passing
    a string got a quiet False instead of an error.

    Trusting the contract means a wrong type raises here rather than being absorbed. That
    is the behaviour change, and asserting only the two good inputs would have passed
    before the fix as well as after it."""
    assert report._meter_ran({"resolvable_fraction": 0.5}) is True
    assert report._meter_ran({}) is False
    with pytest.raises(AttributeError):
        report._meter_ran("n/a")


def test_the_boundary_resolves_the_payload_once():
    """Four isinstance checks on one value in one function was the smell that said the
    resolve was missing. One remains, where the untyped payload arrives."""
    import inspect
    source = inspect.getsource(report.grade_summary)
    assert source.count("isinstance(l18b") <= 1, (
        "the payload is being re-checked by each reader instead of resolved where it "
        "arrives")


@pytest.mark.parametrize("malformed", [None, "n/a", 7, [], "not a dict at all"])
def test_a_malformed_payload_is_resolved_once_where_it_arrives(malformed):
    """The boundary handles it, so nothing downstream has to. Four separate isinstance
    checks in one function were the smell that said the resolve was missing."""
    summary = report.grade_summary({"L1.18": {"band": "n/a"}, "L1.18b": malformed}, None)
    assert summary["status"] in ("can", "cannot", "coarse", "na")


def test_a_well_formed_payload_still_reaches_the_grade():
    results = {"L1.18": {"band": "Healthy"},
               "L1.18b": {"counts": {"neutral": 2, "promiscuous": 0, "unresolved": 0},
                          "resolvable_fraction": 1.0, "findings": []}}
    assert report.grade_summary(results, None)["status"] == "can"

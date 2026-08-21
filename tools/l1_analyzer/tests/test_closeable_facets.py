"""Closeable facets and the Silence index, for one module and its test file.

Umbra's core measurement, brought into Slop Audit. The two tools already share a discipline
and a retention gate; what Slop Audit had was a repository panel, which cannot tell anyone
which function in which module carries an unasserted branch.

The vocabulary is Umbra's own, taken from its glossary rather than reinvented:

  closeable facet    one deterministic audit opportunity the suite can close with evidence
  closeable silence  a closeable facet for which the current suite lacks that evidence
  Silence index      the percentage of closeable facets that are closeable silences

Five kinds of facet. An unexercised branch, a candidate input region, an unasserted return
contract, an exception path, and a runtime property. This module covers the four that are
decidable from the source and the coverage run; runtime properties need the suite to be
watched executing and come next.

Coverage and silence are different measures and the distinction is the point: coverage
records what RAN, silence records evidence the suite LACKS. A branch that ran and was never
asserted on is covered and silent at once, and only the second number says so.
"""

import textwrap

import pytest
from l1_analyzer import facets

MODULE = textwrap.dedent('''
    def band(n: int) -> str:
        """Three arms, and a caller can reach all of them."""
        if n > 10:
            return "high"
        if n > 5:
            return "mid"
        return "low"


    def divide(numerator: int, denominator: int) -> float:
        if denominator == 0:
            raise ValueError("no denominator")
        return numerator / denominator


    def collect(items: list) -> list:
        items.append("added")
        return items
''').lstrip("\n")

TESTS = textwrap.dedent('''
    from m import band, divide

    def test_high():
        assert band(20) == "high"

    def test_divide():
        divide(1, 2)
''').lstrip("\n")


@pytest.fixture(scope="module")
def audited(tmp_path_factory) -> facets.Audit:
    root = tmp_path_factory.mktemp("facets")
    (root / "m.py").write_text(MODULE)
    (root / "test_m.py").write_text(TESTS)
    return facets.audit(root / "m.py", root / "test_m.py")


# --------------------------------------------------------------------------
# The vocabulary itself
# --------------------------------------------------------------------------

def test_the_five_facet_kinds_are_named():
    """Named as a closed set, so a facet nobody wrote a rule for cannot be silently absent
    from the denominator."""
    assert facets.FACET_KINDS == (
        "unexercised_branch",
        "candidate_input_region",
        "unasserted_return_contract",
        "exception_path",
        "runtime_property",
    )


# --------------------------------------------------------------------------
# Unexercised branches
# --------------------------------------------------------------------------

def test_a_branch_no_test_reaches_is_a_silence(audited):
    """`band`'s `mid` arm: reachable, and no test enters it."""
    silent = {(f["function"], f["line"]) for f in audited["facets"]
              if f["kind"] == "unexercised_branch" and f["silent"]}
    assert any(fn == "band" for fn, _ in silent), audited["facets"]


def test_a_branch_a_test_does_reach_is_closed(audited):
    """`band(20)` enters the `high` arm, so that facet has its evidence."""
    closed = [f for f in audited["facets"]
              if f["kind"] == "unexercised_branch" and not f["silent"]]
    assert closed, "no branch was recorded as closed, so coverage was not read"


# --------------------------------------------------------------------------
# Unasserted return contracts
# --------------------------------------------------------------------------

def test_a_call_whose_result_is_never_asserted_is_a_silence(audited):
    """`divide(1, 2)` is called and its result is dropped. The function declares `-> float`,
    so there is a contract and no evidence for it."""
    silent = {f["function"] for f in audited["facets"]
              if f["kind"] == "unasserted_return_contract" and f["silent"]}
    assert "divide" in silent, audited["facets"]


def test_a_call_whose_result_is_asserted_is_closed(audited):
    """`assert band(20) == "high"` is the evidence."""
    closed = {f["function"] for f in audited["facets"]
              if f["kind"] == "unasserted_return_contract" and not f["silent"]}
    assert "band" in closed


# --------------------------------------------------------------------------
# Exception paths
# --------------------------------------------------------------------------

def test_an_explicit_raise_nobody_asserts_is_a_silence(audited):
    """`divide` raises ValueError and no test asserts it does."""
    silent = [f for f in audited["facets"]
              if f["kind"] == "exception_path" and f["silent"] and f["function"] == "divide"]
    assert silent, audited["facets"]


def test_an_exception_a_test_expects_is_closed(tmp_path):
    """`pytest.raises` around the call is the evidence, and it is what closes the facet."""
    (tmp_path / "m.py").write_text(MODULE)
    (tmp_path / "test_m.py").write_text(textwrap.dedent('''
        import pytest
        from m import divide

        def test_raises():
            with pytest.raises(ValueError):
                divide(1, 0)
    ''').lstrip("\n"))
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    closed = [f for f in result["facets"]
              if f["kind"] == "exception_path" and not f["silent"] and f["function"] == "divide"]
    assert closed, result["facets"]


# --------------------------------------------------------------------------
# Candidate input regions
# --------------------------------------------------------------------------

def test_a_region_a_test_supplies_a_value_in_is_closed(tmp_path):
    """A region is closed by a test passing a value that LANDS in it. The first version
    marked every region silent and disclosed that, which is honest and useless: it put the
    index at 90% on a fully tested module and told a reader nothing about which regions
    were actually missing.

    `band(20)` is a positive int and `band(0)` is zero, so those two regions have evidence
    and `negative` does not."""
    (tmp_path / "m.py").write_text("def band(n: int) -> str:\n    return 'high' if n > 10 else 'low'\n")
    (tmp_path / "test_m.py").write_text(
        "from m import band\n\n\n"
        "def test_positive():\n    assert band(20) == 'high'\n\n\n"
        "def test_zero():\n    assert band(0) == 'low'\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    regions = {f["detail"].split("region ")[-1]: f["silent"]
               for f in result["facets"] if f["kind"] == "candidate_input_region"}
    assert regions == {"zero": False, "positive": False, "negative": True}, regions


def test_a_region_supplied_through_parametrize_is_closed(tmp_path):
    """A parametrised test supplies its literals in the decorator, not at the call.

    The first version read call-site literals only, so it reported `region zero` silent on
    a function whose own test passes zero four times. Most well-tested suites are
    parametrised, so that systematically overstated silence and pointed a reader at regions
    that were already covered - which is worse than a number that is merely high, because
    it sends them to fix something that is not broken."""
    (tmp_path / "m.py").write_text("def band(n: int) -> str:\n    return 'high' if n > 10 else 'low'\n")
    (tmp_path / "test_m.py").write_text(
        "import pytest\nfrom m import band\n\n\n"
        '@pytest.mark.parametrize(("n", "expected"), [(20, "high"), (0, "low"), (-5, "low")])\n'
        "def test_band(n, expected):\n    assert band(n) == expected\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    regions = {f["detail"].split("region ")[-1]: f["silent"]
               for f in result["facets"] if f["kind"] == "candidate_input_region"}
    assert regions == {"zero": False, "positive": False, "negative": False}, regions


def test_a_region_supplied_through_a_local_binding_is_closed(tmp_path):
    """The same reasoning one step smaller: a literal bound to a name and then passed."""
    (tmp_path / "m.py").write_text("def band(n: int) -> str:\n    return 'x'\n")
    (tmp_path / "test_m.py").write_text(
        "from m import band\n\n\n"
        "def test_band():\n    value = 0\n    assert band(value) == 'x'\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    zero = next(f for f in result["facets"]
                if f["kind"] == "candidate_input_region" and f["detail"].endswith("region zero"))
    assert zero["silent"] is False


def test_a_region_reached_only_through_a_variable_stays_silent(tmp_path):
    """Evidence has to be readable. A value assembled at runtime cannot be attributed to a
    region from the source, and guessing which region it lands in would be counting
    evidence nobody produced."""
    (tmp_path / "m.py").write_text("def band(n: int) -> str:\n    return 'x'\n")
    (tmp_path / "test_m.py").write_text(
        "import random\nfrom m import band\n\n\n"
        "def test_something():\n    assert band(random.randint(1, 9)) == 'x'\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    silent = [f for f in result["facets"] if f["kind"] == "candidate_input_region" and f["silent"]]
    assert len(silent) == 3, [f["detail"] for f in silent]


def test_a_declared_parameter_carries_boundary_regions(audited):
    """A canonical boundary-bearing part of a parameter's declared value space. An `int`
    has a zero, a negative and a positive; a `list` has empty and non-empty."""
    regions = [f for f in audited["facets"] if f["kind"] == "candidate_input_region"]
    assert regions, "no input regions were enumerated at all"
    assert {f["function"] for f in regions} >= {"band", "divide", "collect"}


def test_an_undeclared_parameter_is_not_counted_as_a_silence(tmp_path):
    """Umbra's `undeclared domain`: an argument the code never gives a type. You close it by
    declaring a type, not by adding a test, so counting it as a testing silence would blame
    the suite for a gap in the signature."""
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    (tmp_path / "test_m.py").write_text("from m import f\n\n\ndef test_f():\n    assert f(1) == 1\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    regions = [f for f in result["facets"] if f["kind"] == "candidate_input_region"]
    assert regions == [], "an untyped parameter was counted as a testable region"
    assert any(u["kind"] == "undeclared_domain" for u in result["undeclared"]), result


# --------------------------------------------------------------------------
# The Silence index
# --------------------------------------------------------------------------

def test_the_silence_index_is_the_share_of_facets_that_are_silent(audited):
    total = len(audited["facets"])
    silent = len([f for f in audited["facets"] if f["silent"]])
    assert audited["total_checkable_facets"] == total
    assert audited["closeable_silence_sites"] == silent
    assert audited["silence_index"] == pytest.approx(round(silent / total * 100, 1))


def test_a_module_with_no_facets_reports_no_index(tmp_path):
    """A share over no facets is absent, not zero, and zero is the CLEAN end of this scale:
    a module nobody could enumerate must not read as fully evidenced."""
    (tmp_path / "m.py").write_text("X = 1\n")
    (tmp_path / "test_m.py").write_text("def test_nothing():\n    assert True\n")
    result = facets.audit(tmp_path / "m.py", tmp_path / "test_m.py")
    assert result["total_checkable_facets"] == 0
    assert result["silence_index"] is None
    assert result["unusable_reason"]


def test_coverage_and_silence_are_reported_side_by_side(audited):
    """The distinction the glossary names: coverage records what ran, silence records
    evidence the suite lacks. A branch that ran and was never asserted on is covered and
    silent at once, and only the second number says so."""
    assert audited["coverage_percent"] is not None
    assert audited["silence_index"] is not None
    assert audited["coverage_percent"] != audited["silence_index"]

"""Behavioural spec for L1.19 (decision-space coverage) and L1.20 (test determinism),
wired to the REAL analyzer. Each Given builds a real module and test suite under a tmp
repo and returns it as `repo`; each When runs pytest_trace and returns `result`. The old
steps reimplemented the coverage arithmetic in the test; these run the real tracer.
"""

import pytest
from l1_analyzer import pytest_trace
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_19.feature")
scenarios("../features/l1_20.feature")

CLASSIFIER = (
    "def classify(x):\n"
    "    if x == 0:\n"
    "        return 'a'\n"
    "    elif x == 1:\n"
    "        return 'b'\n"
    "    elif x == 2:\n"
    "        return 'c'\n"
    "    return 'd'\n"
)


# --- L1.19 ------------------------------------------------------------------

@given(parsers.parse("a 4-arm classifier whose tests exercise {k:d} of 4 arms"), target_fixture="repo")
def given_classifier(k, tmp_path):
    (tmp_path / "m.py").write_text(CLASSIFIER)
    tests = "from m import classify\n" + "".join(
        f"def test_{i}():\n    classify({i})\n" for i in range(k)
    )
    (tmp_path / "test_m.py").write_text(tests)
    return tmp_path


@when("I compute L1.19", target_fixture="result")
def when_19(repo):
    return pytest_trace.decision_space_coverage(repo, "python", 60.0, python_executable=None)


@then(parsers.parse("L1.19 is {val:f}"))
def then_19(result, val):
    assert result["value"] == pytest.approx(val, abs=0.1)


# --- L1.20 ------------------------------------------------------------------

@given("a test suite with no shared mutable state between tests", target_fixture="repo")
def given_pure(tmp_path):
    (tmp_path / "m.py").write_text("def f(x):\n    return x\n")
    (tmp_path / "test_p.py").write_text(
        "from m import f\n"
        "def test_a():\n    assert f(1) == 1\n"
        "def test_b():\n    assert f(2) == 2\n"
    )
    return tmp_path


@given("a chain of tests that each depend on state set by the previous test", target_fixture="repo")
def given_chain(tmp_path):
    # Only the exact order [0..4] passes; any other order fails. Over 5 randomized
    # runs a fully clean run is vanishingly unlikely ((1/120)^5), so this is
    # reliably < 5/5 without asserting a specific flaky count.
    (tmp_path / "test_chain.py").write_text(
        "_s = [0]\n" + "".join(
            f"def test_{i}():\n    assert _s[0] == {i}\n    _s[0] = {i + 1}\n" for i in range(5)
        )
    )
    return tmp_path


@when("I measure L1.20 determinism", target_fixture="result")
def when_20(repo):
    return pytest_trace.test_determinism(repo, "python", 5, 60.0, python_executable=None)


@then("all 5 runs pass")
def then_all5(result):
    assert result["value"] == "5/5"


@then("fewer than 5 of 5 runs pass")
def then_fewer(result):
    assert result["value"] != "5/5"


# --- shared -----------------------------------------------------------------

@then(parsers.parse("the band is {band}"))
def then_band(result, band):
    assert result["band"] == band

"""No coverage or determinism harness invents a number when its toolchain is absent.

Every one of the nine reads a tool off PATH before it can measure anything. With that tool
missing there is nothing to measure, and the only honest answer is a refusal carrying the
reason. A zero would be the same lie in nine places: 0.0% coverage reads as measured and
terrible, and 0/5 determinism reads as measured and broken, when neither was measured at all.

Held across all nine at once, and through the tables the audit itself dispatches on, because
the failure this guards is not one harness getting it wrong. It is a tenth harness arriving
later, or one of these nine growing an early return, with nobody thinking to write the
refusal test again. A table-driven guard catches the new language the day it is added.

These refusals were proved by stand-ins until the 2026-08-17 sweep removed them, and by
nothing after. They were the least reached lines of the least reached files.
"""

import pytest
from l1_analyzer.indicators import _COVERAGE_HARNESS, _DETERMINISM_HARNESS

_LANGUAGES = sorted(set(_COVERAGE_HARNESS) & set(_DETERMINISM_HARNESS))


@pytest.fixture
def no_toolchain(tmp_path, monkeypatch):
    """An empty PATH, so no harness can find the tool it needs.

    Scoped by pytest rather than assigned, because PATH is the process's own state and a
    test that changes it for good would decide the result of every test after it."""
    empty = tmp_path / "empty-bin"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    return tmp_path


@pytest.mark.parametrize("lang", _LANGUAGES)
def test_coverage_refuses_rather_than_publishing_a_share(lang, no_toolchain):
    result = _COVERAGE_HARNESS[lang](no_toolchain, 5.0, None)
    assert result["band"] == "n/a", lang
    assert result["value"] == "n/a", lang


@pytest.mark.parametrize("lang", _LANGUAGES)
def test_determinism_refuses_rather_than_publishing_a_score(lang, no_toolchain):
    result = _DETERMINISM_HARNESS[lang](no_toolchain, 5.0, None)
    assert result["band"] == "n/a", lang
    assert result["value"] == "n/a", lang


@pytest.mark.parametrize("lang", _LANGUAGES)
def test_every_refusal_carries_a_reason_and_no_score(lang, no_toolchain):
    """A refusal with no reason sends a reader to the source to find out what happened, and a
    refusal carrying a figure invites them to read it as one.

    The first draft of this matched for the words "needs" or "not" and failed on Python,
    whose refusal reads "pytest collected no tests". That is a perfectly good reason and the
    test was measuring prose. What can be checked is that a reason is there and that no
    number went out beside it."""
    for result in (_COVERAGE_HARNESS[lang](no_toolchain, 5.0, None),
                   _DETERMINISM_HARNESS[lang](no_toolchain, 5.0, None)):
        assert len(result["details"].strip()) > 15, (lang, result["details"])
        assert "%" not in result["details"], (lang, result["details"])
        assert "/5" not in str(result["value"]), (lang, result["value"])


def test_the_python_harness_measures_with_its_own_interpreter_rather_than_one_on_path(
        no_toolchain):
    """Python is the one that does not refuse for a missing interpreter, and that is right.
    It runs under the interpreter the analyzer is already running under, so an empty PATH
    takes nothing away from it. It refuses for the next reason instead, that the directory
    holds no tests, which is a fact about the repository rather than about the machine."""
    result = _COVERAGE_HARNESS["python"](no_toolchain, 5.0, None)
    assert result["band"] == "n/a"
    assert "no tests" in result["details"]


def test_the_two_tables_cover_the_same_languages():
    """A language in one table and not the other is a half-measured audit, and the loops
    above would pass over it in silence."""
    assert set(_COVERAGE_HARNESS) == set(_DETERMINISM_HARNESS)

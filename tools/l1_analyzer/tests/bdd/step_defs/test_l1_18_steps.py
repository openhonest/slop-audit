"""Behavioural spec for L1.18 (mutable-state ratio), wired to the REAL analyzer.

Every step runs l1_analyzer on a real temp file and asserts its real output. There
is no in-memory simulation and no substring ladder: if the analyzer cannot be
imported the suite fails loudly at import time, because a suite that stays green
without the system under test is a lie (Honest Code applies to tests too).

Each Given returns the `Tree` it built and the When returns the `Analysis` of it, so
every step names its inputs and its output in its own signature. Nothing is shared
between scenarios (which is exactly what L1.20 measures).

Rewiring these steps to real code once surfaced two contradictions the old fabricated
steps hid. Both are now resolved rather than tolerated:
  - the IO-boundary exclusion was withdrawn on 2026-08-15 (it could not be done by
    analysis), and the scenario now asserts the withdrawal instead of the promise;
  - the analyzer's own source scored 11.7% and now scores 0.0, after the path_cover
    refactor recorded in research/amendments/amendment-2026-08-02-self-clean-path-cover.md.
"""

import textwrap
from pathlib import Path
from typing import TypedDict

import l1_analyzer
import pytest
from l1_analyzer.indicators import (
    analyze_mutable_state,
    module_mutable_names,
    mutable_function_names,
)
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/l1_18.feature")

ANALYZER_SRC = Path(l1_analyzer.__file__).parent
_EXT = {"python": "py", "rust": "rs", "c": "c"}

_IO_BOUNDARY = {
    "python": "CACHE = []\ndef handler():\n    # honest: boundary\n    print(CACHE)\n    return len(CACHE)\n",
    "rust": "static mut CACHE: Vec<i32> = Vec::new();\nfn handler() {\n    // honest: boundary\n    unsafe { println!(\"{:?}\", CACHE); }\n}\n",
    "c": "int global_state = 0;\nint handler() {\n    // honest: boundary\n    printf(\"%d\", global_state);\n    return global_state;\n}\n",
}


class Tree(TypedDict):
    """The source tree a scenario states, and the language it is written in."""
    repo: Path
    lang: str


class Analysis(TypedDict):
    """The three real analyzer readings a scenario asserts against."""
    result: dict
    names: list[str]
    module_mutables: list[str]


# --- given ------------------------------------------------------------------

@given("the L1.18 analyzer is available via import or CLI")
def given_available():
    # Guaranteed by the top-of-module import; if it failed, collection failed loudly.
    assert analyze_mutable_state is not None


@given(parsers.parse("a {lang} source file with:"), target_fixture="tree")
def given_source(lang, docstring, tmp_path) -> Tree:
    lang = lang.lower()
    (tmp_path / f"m.{_EXT[lang]}").write_text(textwrap.dedent(docstring).strip() + "\n")
    return {"repo": tmp_path, "lang": lang}


@given(
    parsers.parse("a {lang} source file containing an IO boundary function that also touches global state"),
    target_fixture="tree",
)
def given_io_boundary(lang, tmp_path) -> Tree:
    lang = lang.lower()
    (tmp_path / f"m.{_EXT[lang]}").write_text(_IO_BOUNDARY[lang])
    return {"repo": tmp_path, "lang": lang}


@given("the L1.18 analyzer source itself", target_fixture="tree")
def given_analyzer_source() -> Tree:
    return {"repo": ANALYZER_SRC, "lang": "python"}


# --- when (all three phrasings run the real analyzer; "amended" is the default
#     bound-literal behaviour, so it is the same call) --------------------------

@when("I run L1.18 analysis on it", target_fixture="analysis")
@when("I run L1.18 analysis in amended mode", target_fixture="analysis")
@when("I run L1.18 analysis in amended mode on it", target_fixture="analysis")
def when_run(tree) -> Analysis:
    repo, lang = tree["repo"], tree["lang"]
    return {
        "result": analyze_mutable_state(repo, lang),
        "names": mutable_function_names(repo, lang),
        "module_mutables": module_mutable_names(repo, lang),
    }


# --- then -------------------------------------------------------------------

@then(parsers.parse("the mutable state ratio is {ratio:f}"))
def then_ratio(analysis, ratio):
    # The feature states a 0..1 ratio; the analyzer reports a 0..100 percentage.
    assert analysis["result"]["value"] == pytest.approx(ratio * 100, abs=0.05)


@then("no functions are flagged as mutable")
def then_no_flags(analysis):
    assert analysis["names"] == []


@then(parsers.parse('the function "{name}" is flagged'))
def then_function_flagged(analysis, name):
    assert name in analysis["names"], f"{name!r} not in {analysis['names']}"


@then(parsers.parse('the method "{name}" is flagged'))
def then_method_flagged(analysis, name):
    assert name in analysis["names"], f"{name!r} not in {analysis['names']}"


@then(parsers.parse('the binding "{name}" is recognized as a bound literal'))
def then_bound_literal(analysis, name):
    # A binding is a bound literal exactly when the analyzer excludes it from
    # module mutable state.
    assert name not in analysis["module_mutables"], \
        f"{name!r} counted as mutable: {analysis['module_mutables']}"


@then("the IO boundary function is counted like any other function")
def then_io_counted(analysis):
    # The claim was dropped, so the marked function is counted. Each fixture holds
    # exactly one function and it touches unbounded global state, so the ratio is 100.
    assert analysis["result"]["value"] == 100.0

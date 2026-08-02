"""Behavioural spec for L1.18 (mutable-state ratio), wired to the REAL analyzer.

Every step runs l1_analyzer on a real temp file and asserts its real output. There
is no in-memory simulation and no substring ladder: if the analyzer cannot be
imported the suite fails loudly at import time, because a suite that stays green
without the system under test is a lie (Honest Code applies to tests too).

State is threaded through a per-scenario `ctx` fixture, not module globals, so no
mutable state is shared between scenarios (which is exactly what L1.20 measures).

Rewiring these steps to real code surfaced two contradictions the old fabricated
steps hid; both are tagged @xfail in l1_18.feature with the reason:
  - the analyzer implements no IO-boundary exclusion (Scenario: IO boundary ...);
  - its own source scores 11.7%, not the 0.0 the bootstrap scenario claims.
"""

import textwrap
from pathlib import Path

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


@pytest.fixture
def ctx():
    return {}


def _run(ctx):
    repo, lang = ctx["repo"], ctx["lang"]
    ctx["result"] = analyze_mutable_state(repo, lang)
    ctx["names"] = mutable_function_names(repo, lang)
    ctx["module_mutables"] = module_mutable_names(repo, lang)


# --- given ------------------------------------------------------------------

@given("the L1.18 analyzer is available via import or CLI")
def given_available():
    # Guaranteed by the top-of-module import; if it failed, collection failed loudly.
    assert analyze_mutable_state is not None


@given(parsers.parse("a {lang} source file with:"))
def given_source(ctx, lang, docstring, tmp_path):
    lang = lang.lower()
    (tmp_path / f"m.{_EXT[lang]}").write_text(textwrap.dedent(docstring).strip() + "\n")
    ctx["repo"], ctx["lang"] = tmp_path, lang


@given(parsers.parse("a {lang} source file containing an IO boundary function that also touches global state"))
def given_io_boundary(ctx, lang, tmp_path):
    lang = lang.lower()
    (tmp_path / f"m.{_EXT[lang]}").write_text(_IO_BOUNDARY[lang])
    ctx["repo"], ctx["lang"] = tmp_path, lang


@given("the L1.18 analyzer source itself")
def given_analyzer_source(ctx):
    ctx["repo"], ctx["lang"] = ANALYZER_SRC, "python"


# --- when (all three phrasings run the real analyzer; "amended" is the default
#     bound-literal behaviour, so it is the same call) --------------------------

@when("I run L1.18 analysis on it")
@when("I run L1.18 analysis in amended mode")
@when("I run L1.18 analysis in amended mode on it")
def when_run(ctx):
    _run(ctx)


# --- then -------------------------------------------------------------------

@then(parsers.parse("the mutable state ratio is {ratio:f}"))
def then_ratio(ctx, ratio):
    # The feature states a 0..1 ratio; the analyzer reports a 0..100 percentage.
    assert ctx["result"]["value"] == pytest.approx(ratio * 100, abs=0.05)


@then("no functions are flagged as mutable")
def then_no_flags(ctx):
    assert ctx["names"] == []


@then(parsers.parse('the function "{name}" is flagged'))
def then_function_flagged(ctx, name):
    assert name in ctx["names"], f"{name!r} not in {ctx['names']}"


@then(parsers.parse('the method "{name}" is flagged'))
def then_method_flagged(ctx, name):
    assert name in ctx["names"], f"{name!r} not in {ctx['names']}"


@then(parsers.parse('the binding "{name}" is recognized as a bound literal'))
def then_bound_literal(ctx, name):
    # A binding is a bound literal exactly when the analyzer excludes it from
    # module mutable state.
    assert name not in ctx["module_mutables"], f"{name!r} counted as mutable: {ctx['module_mutables']}"


@then("the IO boundary function is excluded from the mutable state ratio")
def then_io_excluded(ctx):
    # xfail: the analyzer implements no IO-boundary exclusion, so the boundary
    # function is counted and the ratio is not zero. This assertion states the
    # feature's intent; it fails until exclusion is implemented or the claim dropped.
    assert ctx["result"]["value"] == 0.0

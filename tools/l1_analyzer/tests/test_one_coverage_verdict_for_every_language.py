"""Seven copies of one decision, one per language.

Our duplication check reports 8.61 per cent of this repository inside a repeated window, and
a chunk of it is here: `_coverage_verdict` is written seven times, once in each language
runner. The bodies are not identical, and reading them together is what shows they are the
same function.

Each one asks the same four questions in the same order. Did the suite time out. Did the
coverage tool write a report at all. Did it find anything with a branch in it. What share was
covered, and what band is that.

What genuinely differs is the words and one piece of arithmetic. Java's tool reports covered
and MISSED, so the total is their sum; C#'s reports covered and VALID, where valid is already
the total. Every other difference is a sentence naming that language's tool and its remedy,
which is exactly what a table row holds.

So the caller keeps its own words and does its own extraction, and hands the shared decision
one pair of numbers and three sentences.
"""

import pytest
from l1_analyzer import pytest_trace


def _verdict(**kwargs):
    return pytest_trace.coverage_verdict(**kwargs)


_WORDS = {
    "no_report": "Java branch coverage needs the JaCoCo plugin in the build",
    "nothing_to_cover": "no enumerable decision branches found",
    "how": "JaCoCo BRANCH counters",
    "toolchain": "openjdk 21",
}


def test_a_timeout_is_reported_as_a_timeout():
    result = _verdict(covered=None, total=None, returncode=124, **_WORDS)
    assert result["band"] == "n/a"
    assert "timed out" in result["details"]


def test_no_report_at_all_names_the_missing_tool():
    result = _verdict(covered=None, total=None, returncode=0, **_WORDS)
    assert result["band"] == "n/a"
    assert "JaCoCo plugin" in result["details"]


def test_a_report_with_nothing_to_cover_is_its_own_answer():
    """Different from no report, and it has to stay different: one means the tool is not in
    the build, the other means it ran and found nothing with a branch in it."""
    result = _verdict(covered=0, total=0, returncode=0, **_WORDS)
    assert result["band"] == "n/a"
    assert "no enumerable decision branches" in result["details"]


def test_a_measured_run_carries_the_share_and_the_band():
    result = _verdict(covered=211, total=250, returncode=0, **_WORDS)
    assert result["value"] == 84.4
    assert result["band"] == pytest_trace.coverage_band(84.4)
    assert "211/250" in result["details"]
    assert "JaCoCo BRANCH counters" in result["details"]
    assert "openjdk 21" in result["details"]


def test_a_failing_suite_still_reports_its_coverage_and_says_the_suite_failed():
    """The number is still true. A reader has to be told the suite did not pass, because
    coverage from a red suite is not the same evidence as coverage from a green one."""
    result = _verdict(covered=211, total=250, returncode=1, **_WORDS)
    assert result["value"] == 84.4
    assert "suite exit 1" in result["details"]


def test_a_passing_suite_says_so():
    assert "suite passed" in _verdict(covered=1, total=2, returncode=0, **_WORDS)["details"]


@pytest.mark.parametrize("module", ["java_trace", "csharp_trace", "ruby_trace"])
def test_a_runner_whose_tool_gives_a_pair_decides_nothing_itself(module):
    """The shape, asserted rather than described. A fourth copy of the decision is the
    duplication coming back, and it comes back one language at a time.

    Each runner keeps a function of its own, and should: that is where its arithmetic and
    its sentences live, and only it knows which tool it ran. What it must not keep is the
    decision, so its body hands the numbers over rather than banding them."""
    import ast
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"l1_analyzer.{module}"))
    node = next(n for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.FunctionDef) and n.name == "_coverage_verdict")
    body = ast.unparse(node)
    assert "coverage_verdict(" in body, module
    assert "coverage_band(" not in body, f"{module} still bands it itself"
    assert "suite passed" not in body, f"{module} still writes the shared sentence"


@pytest.mark.parametrize("module", ["go_trace", "js_trace", "c_trace"])
def test_a_runner_whose_tool_asks_more_keeps_its_own(module):
    """Three do not fold in, and forcing them would be worse than the duplication.

    Go has to ask whether any test ran at all and whether the profile carried a total. C has
    to find the gcov summary and ask whether the instrumented build produced any lines.
    Neither question exists for the other languages. All three are handed a percentage by
    their tool rather than a covered-and-total pair, so the arithmetic the shared function
    does is arithmetic they have no numbers for.

    Recorded so the next reader sees a decision rather than three modules nobody got to."""
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(f"l1_analyzer.{module}"))
    assert "def _coverage_verdict" in source, module

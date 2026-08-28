"""A step written `async def`, which the runner calls and then throws away.

Reported by a peer working on a neighbouring project on 2026-08-27. pytest-bdd calls a step
function and discards what it returns. Write the step `async def` and you get back a
coroutine nobody runs, so the step body never executes. Python prints a RuntimeWarning and
pytest does not fail.

Seven of their scenarios went red at once, and only because each asserted that something had
CHANGED. A scenario asserting an ABSENCE passes: "no pass ran" reads an untouched context and
finds an empty list, which is exactly what it wanted. So every "nothing happened", "no error
was raised", "it was not called" scenario stays green and proves nothing. Those are the
negative controls, which is the half you would most want to trust.

This lands under One Gherkin Per Function. That clause is about a bijection between functions
and scenarios, and a step that cannot run satisfies the bijection on paper while exercising
nothing. The clause already reads step length as a readout on the code; this is a second
thing the same file can be read for.

Python only, and the vocabulary says so. JavaScript and Ruby runners await what a step
returns, so writing one async there is fine and reporting it would be wrong.
"""

import pytest
from l1_analyzer import honest_code_markers as markers
from l1_analyzer import honest_code_read as read
from l1_analyzer.lang_spec import LANG_SPEC

_ASYNC_STEP = '''from pytest_bdd import when


@when("replicate runs one pass")
async def _when_replicate(ctx):
    ctx["answer"] = await replicate(ctx["db"])
'''

_PLAIN_STEP = '''from pytest_bdd import when


@when("replicate runs one pass")
def _when_replicate(ctx):
    ctx["answer"] = replicate(ctx["db"])
'''


def _found(source: str, lang: str = "python") -> list[dict]:
    return markers.heavy_step_definitions(read.read_tree(source, lang)) or []


def test_an_async_step_is_reported():
    found = _found(_ASYNC_STEP)
    assert [f["symbol"] for f in found] == ["_when_replicate"], found


def test_the_report_says_the_step_never_runs():
    detail = _found(_ASYNC_STEP)[0]["detail"]
    assert "never runs" in detail or "never ran" in detail


def test_it_names_the_scenarios_that_stay_green():
    """A reader who fixes only the red scenarios leaves the vacuous ones behind, and those
    are the ones the shape hides."""
    assert "absence" in _found(_ASYNC_STEP)[0]["instead"].lower()


def test_an_ordinary_step_is_left_alone():
    assert _found(_PLAIN_STEP) == []


def test_an_async_function_that_is_not_a_step_is_left_alone():
    """The rule is about what the runner does with the result, not about async."""
    assert _found("async def fetch(url):\n    return await get(url)\n") == []


def test_a_long_async_step_is_reported_once_for_the_thing_that_matters():
    """Length stops mattering when the body never runs. Two findings on one site would
    send a reader to shorten a step that does nothing."""
    body = "\n".join(f"    step_{i}()" for i in range(35))
    found = _found('@when("a store")\nasync def _when(ctx):\n' + body + "\n")
    assert len(found) == 1, found
    assert "never runs" in found[0]["detail"]


@pytest.mark.parametrize("lang", ["javascript", "typescript", "ruby"])
def test_a_language_whose_runner_waits_is_not_reported(lang):
    """Reporting these would ask an author to break working tests."""
    assert LANG_SPEC[lang]["steps_discard_the_result"] is False


def test_python_is_the_one_that_discards_it():
    assert LANG_SPEC["python"]["steps_discard_the_result"] is True

"""Two defaults that answered a question the caller was supposed to answer.

Swept out after the same class of defect appeared twice in one day: a collaborator
defaulted to the real thing in `prove_hazard`, which `python_coverage_prove` had already
fixed and documented. A third instance is not worth waiting for, so every defaulted
parameter in the package was read.

`race_harness._na(reason, tool="tsan")` builds a refusal that names the instrument that
did not run, and there are two instruments: ThreadSanitizer and the stress runner. Five
call sites pass `tool="stress"` and six take the default. A stress-path refusal that
forgot the argument would tell a reader ThreadSanitizer produced no reading, and
ThreadSanitizer was never started. That is the input-side of silent failure exactly: the
function cannot tell "chose tsan" from "forgot to say".

`state_bounds._verdict(reaches, refs=None)` had one production caller and it always passes
`refs`. A default nobody takes is a second, untested code path kept alive by its own
signature, and it is the path where the silence reason has no reference to point at.
"""

import ast
import inspect
import pathlib

import pytest
from l1_analyzer import race_harness, state_bounds


def test_the_race_refusal_asks_which_instrument_did_not_run():
    parameter = inspect.signature(race_harness._na).parameters["tool"]
    assert parameter.default is inspect.Parameter.empty, (
        "the refusal defaults to naming ThreadSanitizer, so a stress-path caller that "
        "forgot the argument reports an instrument that was never started"
    )


def test_every_race_refusal_names_its_own_instrument():
    """Read from the source rather than by running each path: the two arms of this module
    refuse in eleven places, and a reader of any one of them is owed the right name."""
    source = pathlib.Path(race_harness.__file__).read_text()
    calls = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "_na"]
    assert calls, "no refusals found; this test is reading the wrong thing"
    for call in calls:
        named = {kw.arg for kw in call.keywords} | {"reason"} if call.args else {kw.arg for kw in call.keywords}
        assert "tool" in named, f"a refusal at line {call.lineno} does not say which instrument"


@pytest.mark.parametrize("tool", ["tsan", "stress"])
def test_the_refusal_carries_the_instrument_it_was_given(tool):
    assert race_harness._na("nothing ran", tool)["tool"] == tool


def test_the_state_verdict_asks_for_the_references_it_reports_on():
    """`refs` is what the silence reason points at. Defaulting it to nothing kept a second
    path alive that no production caller takes and no test covers, and it is the path where
    a reader is sent to a site the finding cannot name."""
    parameter = inspect.signature(state_bounds._verdict).parameters["refs"]
    assert parameter.default is inspect.Parameter.empty

"""The concurrency loop takes its model call and its runner as required arguments.

`prove_hazard` defaulted both to the real thing: `model_call=None` meant the real
generator and `run_generated=None` meant writing a crate and building it. A test that
forgot either argument reached a paid API and a `cargo build` instead of failing, and it
would look like it was testing the loop.

`python_coverage_prove._prove_one` had the same shape and had already fixed it, with the
reason written at the site: "Required, not defaulted. A default would put the real model
call and a real subprocess one forgotten argument away from a test, which is the open-input
failure this repository refuses everywhere else." One module learned that and the other did
not, which is the same class of defect twice in one package.

The convenience the default bought is real and belongs at the boundary. `cli.py` is the
only production caller, and it is the place that knows a run is meant to spend money.
"""

import inspect

from l1_analyzer import prove, python_coverage_prove


def test_neither_collaborator_has_a_default():
    parameters = inspect.signature(prove.prove_hazard).parameters
    for name in ("model_call", "run_generated"):
        assert parameters[name].default is inspect.Parameter.empty, (
            f"{name} defaults to the real thing, so a test that forgets it reaches a paid "
            "API or a real build instead of failing"
        )


def test_the_coverage_loop_still_has_none_either():
    """The module that learned it first, asserted beside the one that just did, so the two
    cannot drift apart again."""
    parameters = inspect.signature(python_coverage_prove._prove_one).parameters
    for name in ("propose_fn", "repair_fn", "run_fn"):
        assert parameters[name].default is inspect.Parameter.empty


def test_the_real_generator_and_runner_are_named_at_the_boundary():
    """Where the convenience went. The CLI is the one caller that knows a run is meant to
    spend money, so it is the one place that names the real collaborators."""
    source = inspect.getsource(__import__("l1_analyzer.cli", fromlist=["cli"]))
    assert "prove.generate" in source
    assert "write_crate_and_stress" in source

"""The prove loop's orchestration, tested without a mock in sight.

The paths deleted in the 2026-08-17 fixture sweep and never replaced: propose returning
nothing, a divergence retained, a setup error repaired and reclassified, a pass that is
not retained, and the repair round cap. Every one had been covered by patching module
globals, which is why they went: a test that reaches into the module under test to
replace its collaborators is asserting against its own fixture.

`prove.prove` already showed the shape. It takes `model_call` and `run_generated` as
explicit parameters, so a caller injects them and a test hands it pure functions. The
coverage loops reached for module-level `propose`, `repair` and `_run` instead, which is
what made them untestable without patching.

They are parameters now, required rather than defaulted: a default would put the real
model call one forgotten argument away from a test, which is the same open-input failure
this repository refuses everywhere else.

Nothing here mocks anything. Every collaborator is a small pure function that returns
what the real one would, and the assertions are about what the ORCHESTRATION did with
those returns: which bucket it counted, what it retained, how many times it repaired.
"""

import pathlib

from l1_analyzer import python_coverage_prove as pcp

_GAP = {"function": "f", "line": 3, "branch": "if x > 3"}

# Pytest's real summary lines. My first draft used the `E       AssertionError` form from
# the traceback body, which `_classify` does not read: it matches the FAILED summary line
# and its exception name. The fixtures were shaped like output rather than being it, and
# three tests failed for a reason unrelated to the orchestration they were testing.
_FAILED_ASSERT = "FAILED t.py::proof_0 - AssertionError: boom"
_FAILED_IMPORT = "FAILED t.py::proof_0 - ImportError: no module named x"


def _proposal(body="assert False"):
    return {"body": body, "explanation": "why"}


def test_a_proposal_nobody_returns_is_declined_and_counted():
    """It used to be "skipped" and counted nowhere, which this test asserted by name.

    The first live sweep, 2026-08-19, found what that cost. Two gaps were handed to a model
    that returned nothing usable, both were dropped before the tally, and the run reported
    "no proof-ready uncovered branches located" over a module with 154 of them. A model
    call that produced nothing still cost money, so it lands in a bucket."""
    bucket, proposal, source = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 3, 1.0,
        propose_fn=lambda gap, path: None,
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (0, ""))
    assert (bucket, proposal, source) == ("declined", None, "")


def test_a_divergence_is_retained_on_the_first_run():
    bucket, proposal, source = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 3, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (1, _FAILED_ASSERT))
    assert bucket == "divergence"
    assert proposal["explanation"] == "why"
    assert "assert False" in source


def test_a_setup_error_is_repaired_then_reclassified():
    """The path that carries the whole point of a repair round: the first run is noise,
    the repair fixes it, and the SECOND run is what gets counted."""
    runs = iter([(1, _FAILED_IMPORT), (1, _FAILED_ASSERT)])
    bucket, _got, _src = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 3, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=lambda *a: _proposal("assert False  # repaired"),
        run_fn=lambda *a: next(runs))
    assert bucket == "divergence"


def test_the_repair_round_cap_is_honoured():
    """Every run is noise and repair always succeeds, so only the cap stops it."""
    calls = []

    def repair(*_args):
        calls.append(1)
        return _proposal("assert False  # again")

    bucket, _got, _src = pcp._prove_one(
        pathlib.Path("."), "python3", _GAP, "m", 2, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=repair,
        run_fn=lambda *a: (1, _FAILED_IMPORT))
    assert bucket == "incidental"
    assert len(calls) == 2, f"repaired {len(calls)} times against a cap of 2"


def test_a_pass_is_not_retained():
    retained, outcomes = pcp._prove_module(
        pathlib.Path("."), "m.py", "python3", [_GAP], 3, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (0, "1 passed"))
    assert retained == []
    assert outcomes["pass"] == 1
    assert outcomes["divergence"] == 0


def test_a_divergence_reaches_the_retained_list_with_its_location():
    retained, outcomes = pcp._prove_module(
        pathlib.Path("."), "pkg/m.py", "python3", [_GAP], 3, 1.0,
        propose_fn=lambda gap, path: _proposal(),
        repair_fn=lambda *a: None,
        run_fn=lambda *a: (1, _FAILED_ASSERT))
    assert outcomes["divergence"] == 1
    assert len(retained) == 1
    assert retained[0]["location"] == "pkg/m.py:3"
    assert retained[0]["language"] == "python"

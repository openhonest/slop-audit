"""Behavioural spec for the concurrency prove loop, wired to the REAL prove module with
the model call and the execution injected. This tests the honesty property directly:
retain iff demonstrated.

Every scenario states its runner. There is no fallback runner, because a fallback that
returns a verdict on a scenario's behalf lets a scenario that never states one pass on a
fabricated result.
"""

from typing import TypedDict

from l1_analyzer import prove
from pytest_bdd import given, scenarios, then, when

scenarios("../features/prove_loop.feature")

_HAZARD = {"kind": "check_then_act", "file": "src/wal.rs", "line": 3498, "symbol": "self.nbackfills"}
_TEST = "#[test] fn proof() { /* threaded test */ }"


class Hazard(TypedDict):
    """What the Given states: the located hazard, and the model that answers for it."""
    request: prove.ProofRequest
    model_call: prove.ConcurrencyModelCall


def _runner_must_not_be_called(test: str) -> prove.RunResult:
    raise AssertionError("the runner was called although no test was generated")


@given("a located hazard and a model that writes a test for it", target_fixture="hazard")
def given_hazard_and_model() -> Hazard:
    return {
        "request": prove.proof_request(_HAZARD, context="fn advance(&self) { ... }"),
        "model_call": lambda req: _TEST,
    }


@given("a located hazard and no model available", target_fixture="hazard")
def given_hazard_no_model() -> Hazard:
    return {
        "request": prove.proof_request(_HAZARD, context="fn advance(&self) { ... }"),
        "model_call": lambda req: None,
    }


@given("the generated test fires a race when run", target_fixture="run_generated")
def given_fires():
    return lambda test: {"verdict": "race-observed", "detail": "panic on 2/8 runs"}


@given("the generated test runs clean when run", target_fixture="run_generated")
def given_clean():
    return lambda test: {"verdict": "no-race-in-stress", "detail": "8/8 passed"}


@given("the generated test cannot be built or run", target_fixture="run_generated")
def given_cannot_run():
    return lambda test: {"verdict": "n/a", "detail": "could not build the suite"}


@given("no test is generated, so the runner is never reached", target_fixture="run_generated")
def given_runner_never_reached():
    # Not a stub standing in for a result: it asserts the loop never asks for one.
    return _runner_must_not_be_called


@when("I run the prove loop", target_fixture="outcome")
def when_prove(hazard, run_generated):
    return prove.prove(hazard["request"], hazard["model_call"], run_generated)


@when("I run the production prove loop with those injected", target_fixture="outcome")
def when_prove_hazard(hazard, run_generated):
    # prove_hazard is the production wrapper; handing it a model call and a runner proves
    # it delegates through the same honesty gate without an API key or a build.
    #
    # `work_dir="/unused"` used to sit here, which is what a defaulted collaborator looks
    # like from the caller's side: a path that means nothing, passed so the real runner it
    # would otherwise have built would have somewhere to go. Both collaborators are
    # required now, so there is nothing to say about a directory this test never uses.
    return prove.prove_hazard(hazard["request"], hazard["model_call"], run_generated)


@then("the hazard is demonstrated")
def then_demonstrated(outcome):
    assert outcome["verdict"] == prove.DEMONSTRATED


@then("the hazard is not demonstrated")
def then_not_demonstrated(outcome):
    assert outcome["verdict"] == prove.NOT_DEMONSTRATED


@then("the hazard is not generated")
def then_not_generated(outcome):
    assert outcome["verdict"] == prove.NOT_GENERATED


@then("the hazard is not run")
def then_not_run(outcome):
    assert outcome["verdict"] == prove.NOT_RUN


@then("the proof is retained")
def then_retained(outcome):
    assert prove.retained([outcome]) == [outcome]


@then("the proof is not retained")
def then_not_retained(outcome):
    assert prove.retained([outcome]) == []

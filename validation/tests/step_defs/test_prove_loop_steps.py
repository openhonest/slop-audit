"""Behavioural spec for the concurrency prove loop, wired to the REAL prove module with
the model call and the execution injected. This tests the honesty property directly:
retain iff demonstrated. State threads through a `ctx` fixture.
"""

import pytest
from l1_analyzer import prove
from pytest_bdd import given, scenarios, then, when

scenarios("../features/prove_loop.feature")

_HAZARD = {"kind": "check_then_act", "file": "src/wal.rs", "line": 3498, "symbol": "self.nbackfills"}
_TEST = "#[test] fn proof() { /* threaded test */ }"


@pytest.fixture
def ctx():
    return {}


@given("a located hazard and a model that writes a test for it")
def given_hazard_and_model(ctx):
    ctx["request"] = prove.proof_request(_HAZARD, context="fn advance(&self) { ... }")
    ctx["model_call"] = lambda req: _TEST


@given("a located hazard and no model available")
def given_hazard_no_model(ctx):
    ctx["request"] = prove.proof_request(_HAZARD, context="fn advance(&self) { ... }")
    ctx["model_call"] = lambda req: None


@given("the generated test fires a race when run")
def given_fires(ctx):
    ctx["run_generated"] = lambda test: {"verdict": "race-observed", "detail": "panic on 2/8 runs"}


@given("the generated test runs clean when run")
def given_clean(ctx):
    ctx["run_generated"] = lambda test: {"verdict": "no-race-in-stress", "detail": "8/8 passed"}


@given("the generated test cannot be built or run")
def given_cannot_run(ctx):
    ctx["run_generated"] = lambda test: {"verdict": "n/a", "detail": "could not build the suite"}


@when("I run the prove loop")
def when_prove(ctx):
    run = ctx.get("run_generated", lambda test: {"verdict": "n/a", "detail": "no runner"})
    ctx["outcome"] = prove.prove(ctx["request"], ctx["model_call"], run)


@then("the hazard is demonstrated")
def then_demonstrated(ctx):
    assert ctx["outcome"]["verdict"] == prove.DEMONSTRATED


@then("the hazard is not demonstrated")
def then_not_demonstrated(ctx):
    assert ctx["outcome"]["verdict"] == prove.NOT_DEMONSTRATED


@then("the hazard is not generated")
def then_not_generated(ctx):
    assert ctx["outcome"]["verdict"] == prove.NOT_GENERATED


@then("the hazard is not run")
def then_not_run(ctx):
    assert ctx["outcome"]["verdict"] == prove.NOT_RUN


@then("the proof is retained")
def then_retained(ctx):
    assert prove.retained([ctx["outcome"]]) == [ctx["outcome"]]


@then("the proof is not retained")
def then_not_retained(ctx):
    assert prove.retained([ctx["outcome"]]) == []

"""Behavioural spec for the Stress concurrency runner, wired to the REAL race_harness.
The parser scenarios feed genuine Rust panic output (both formats); the n/a scenario
calls the real runner. State threads through a `ctx` fixture.
"""

import pytest
from l1_analyzer import race_harness
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/stress_runner.feature")

_OLD = (
    "running 3 tests\n"
    "thread 'wal::tests::concurrent' panicked at 'assertion failed: "
    "frame_watermark >= nbackfills', src/storage/wal.rs:3498:9\n"
    "test wal::tests::concurrent ... FAILED\n"
)

_NEW = (
    "running 3 tests\n"
    "thread 'wal::tests::concurrent' panicked at src/storage/wal.rs:3498:9:\n"
    "assertion failed: frame_watermark >= nbackfills\n"
    "note: run with `RUST_BACKTRACE=1` ...\n"
)

_TWO = _OLD + (
    "thread 'pager::tests::race' panicked at 'index out of bounds', src/storage/pager.rs:210:4\n"
)


@pytest.fixture
def ctx():
    return {}


@given("stress output where a test panicked on an assertion (old format)")
def given_old(ctx):
    ctx["output"] = _OLD


@given("stress output where a test panicked on an assertion (new format)")
def given_new(ctx):
    ctx["output"] = _NEW


@given("stress output with two distinct panics")
def given_two(ctx):
    ctx["output"] = _TWO


@when("I parse the panic output")
def when_parse(ctx):
    ctx["panics"] = race_harness.parse_panic(ctx["output"])


@then(parsers.parse('a panic is surfaced at "{fname}" line {line:d}'))
def then_location(ctx, fname, line):
    assert any(p["file"] == fname and p["line"] == line for p in ctx["panics"]), ctx["panics"]


@then("the panic message mentions the failed invariant")
def then_message(ctx):
    assert any("frame_watermark" in p["message"] for p in ctx["panics"]), ctx["panics"]


@then("two panics are surfaced")
def then_two(ctx):
    assert len(ctx["panics"]) == 2


@given("a repository whose language the stress runner does not support")
def given_unsupported(ctx, tmp_path):
    ctx["repo"], ctx["lang"] = tmp_path, "python"


@when("I run the stress runner")
def when_run(ctx):
    ctx["result"] = race_harness.stress_races(ctx["repo"], ctx["lang"], 3, 5.0)


@then("the stress verdict is n/a")
def then_na(ctx):
    assert ctx["result"]["verdict"] == race_harness.NA
    assert ctx["result"]["tool"] == "stress"
    assert ctx["result"]["findings"] == []

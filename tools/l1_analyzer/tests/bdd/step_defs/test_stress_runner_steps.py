"""Behavioural spec for the Stress concurrency runner, wired to the REAL race_harness.
The parser scenarios feed genuine Rust panic output (both formats); the n/a scenario
calls the real runner. Each step returns its one output as a named fixture.
"""

from pathlib import Path
from typing import TypedDict

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


class Tree(TypedDict):
    """A repository the runner is pointed at, and the language it is told it is."""
    repo: Path
    lang: str


@given("stress output where a test panicked on an assertion (old format)", target_fixture="output")
def given_old():
    return _OLD


@given("stress output where a test panicked on an assertion (new format)", target_fixture="output")
def given_new():
    return _NEW


@given("stress output with two distinct panics", target_fixture="output")
def given_two():
    return _TWO


@when("I parse the panic output", target_fixture="panics")
def when_parse(output):
    return race_harness.parse_panic(output)


@then(parsers.parse('a panic is surfaced at "{fname}" line {line:d}'))
def then_location(panics, fname, line):
    assert any(p["file"] == fname and p["line"] == line for p in panics), panics


@then("the panic message mentions the failed invariant")
def then_message(panics):
    assert any("frame_watermark" in p["message"] for p in panics), panics


@then("two panics are surfaced")
def then_two(panics):
    assert len(panics) == 2


@given("a repository whose language the stress runner does not support", target_fixture="tree")
def given_unsupported(tmp_path) -> Tree:
    return {"repo": tmp_path, "lang": "python"}


@when("I run the stress runner", target_fixture="result")
def when_run(tree):
    return race_harness.stress_races(tree["repo"], tree["lang"], 3, 5.0)


@then("the stress verdict is n/a")
def then_na(result):
    assert result["verdict"] == race_harness.NA
    assert result["tool"] == "stress"
    assert result["findings"] == []

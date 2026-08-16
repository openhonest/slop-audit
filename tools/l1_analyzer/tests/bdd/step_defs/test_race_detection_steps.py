"""Behavioural spec for the runtime thread-safety harness, wired to the REAL
race_harness. The parser scenarios feed genuine ThreadSanitizer output (modelled on
the turso free-threaded WAL race); the verdict/n-a scenarios call the real functions.
State threads through a per-scenario `ctx` fixture, not module globals.
"""

import pytest
from l1_analyzer import race_harness
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/race_detection.feature")

# A real ThreadSanitizer data-race report, shaped exactly as TSan emits: a banner, two
# conflicting accesses each with a source frame, and a SUMMARY line. Modelled on the
# turso race the static meter pointed at (publish_backfill advancing nbackfills while a
# watermark read holds a frame in find_frame).
_ONE_RACE = """\
==================
WARNING: ThreadSanitizer: data race (pid=54321)
  Write of size 8 at 0x7b0800000900 by thread T3:
    #0 turso_core::storage::shared_wal_coordination::publish_backfill::h9f src/storage/shared_wal_coordination.rs:1386:24 (turso_core+0x2f1a4c)
    #1 turso_core::storage::wal::checkpoint::h12 src/storage/wal.rs:4018:9 (turso_core+0x2c9b10)

  Previous read of size 8 at 0x7b0800000900 by thread T7:
    #0 turso_core::storage::wal::find_frame::hab src/storage/wal.rs:3498:16 (turso_core+0x2caf30)

  Location is heap block of size 128 at 0x7b0800000900 allocated by main thread:
    #0 malloc <null> (turso_core+0x44b1c8)

  Thread T3 (tid=1001, running) created by main thread at:
    #0 pthread_create <null> (turso_core+0x42d0aa)

SUMMARY: ThreadSanitizer: data race src/storage/shared_wal_coordination.rs:1386:24 in turso_core::storage::shared_wal_coordination::publish_backfill
==================
"""

_SECOND_RACE = """\
WARNING: ThreadSanitizer: data race (pid=54321)
  Atomic write of size 8 at 0x7b04000010c0 by thread T2:
    #0 turso_core::storage::page_cache::insert::h55 src/storage/page_cache.rs:210:12 (turso_core+0x1aa0bb)
  Previous read of size 8 at 0x7b04000010c0 by thread T5:
    #0 turso_core::storage::page_cache::get::h88 src/storage/page_cache.rs:180:9 (turso_core+0x1aa9cc)
SUMMARY: ThreadSanitizer: data race src/storage/page_cache.rs:210:12 in turso_core::storage::page_cache::insert
==================
"""

_CLEAN = "running 812 tests\ntest result: ok. 812 passed; 0 failed; 0 ignored\n"


@pytest.fixture
def ctx():
    return {}


# --- parser scenarios -------------------------------------------------------

@given("ThreadSanitizer output reporting a data race in publish_backfill")
def given_one_race(ctx):
    ctx["output"] = _ONE_RACE


@given("ThreadSanitizer output reporting two data races")
def given_two_races(ctx):
    ctx["output"] = _ONE_RACE + _SECOND_RACE


@when("I parse the ThreadSanitizer report")
def when_parse(ctx):
    ctx["findings"] = race_harness.parse_tsan(ctx["output"])


@then("one data race is surfaced")
def then_one(ctx):
    assert len(ctx["findings"]) == 1


@then("two data races are surfaced")
def then_two(ctx):
    assert len(ctx["findings"]) == 2


@then(parsers.parse('the race points at "{fname}" line {line:d}'))
def then_location(ctx, fname, line):
    f = ctx["findings"][0]
    assert f["file"].endswith(fname), f["file"]
    assert f["line"] == line


@then("both conflicting access sites are recorded")
def then_accesses(ctx):
    # The write (shared_wal_coordination.rs:1386) and the read (wal.rs:3498).
    accesses = ctx["findings"][0]["accesses"]
    assert ("src/storage/shared_wal_coordination.rs", 1386) in accesses
    assert ("src/storage/wal.rs", 3498) in accesses


# --- verdict / n-a scenarios ------------------------------------------------

@given("a suite that ran under ThreadSanitizer with no race reported")
def given_clean(ctx):
    ctx["findings"] = race_harness.parse_tsan(_CLEAN)


@when("I read the verdict")
def when_verdict(ctx):
    verdict, band, value = race_harness._verdict(ctx["findings"])
    ctx["verdict"], ctx["band"], ctx["value"] = verdict, band, value


@then("the verdict is no-race-in-tests")
def then_no_race(ctx):
    assert ctx["verdict"] == race_harness.NO_RACE_IN_TESTS


@then("the details disclose that the result is bounded by the test suite")
def then_bounded(ctx):
    assert "bounded by the test suite" in ctx["value"]


@given("a repository whose language the race harness does not support")
def given_unsupported(ctx, tmp_path):
    ctx["repo"], ctx["lang"] = tmp_path, "java"


@when("I run the race harness")
def when_run(ctx):
    ctx["result"] = race_harness.detect_races(ctx["repo"], ctx["lang"], 5.0)


@then("the verdict is n/a")
def then_na(ctx):
    assert ctx["result"]["verdict"] == race_harness.NA


@then("no race is claimed either way")
def then_no_claim(ctx):
    assert ctx["result"]["findings"] == []
    assert ctx["result"]["band"] == "n/a"


# --- cross-reference scenario ----------------------------------------------

@given(parsers.parse('the static surface meter flagged "{path}"'))
def given_flagged(ctx, path):
    ctx["surface_files"] = {path}


@when("I cross-reference the observed races against the flagged surface")
def when_xref(ctx):
    findings = race_harness.parse_tsan(ctx["output"])
    ctx["confirmed"] = race_harness.confirmed_surface(findings, ctx["surface_files"])


@then("the race is confirmed against the flagged surface")
def then_confirmed(ctx):
    assert len(ctx["confirmed"]) == 1
    assert ctx["confirmed"][0]["file"].endswith("shared_wal_coordination.rs")

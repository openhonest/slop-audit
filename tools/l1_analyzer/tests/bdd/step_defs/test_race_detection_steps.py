"""Behavioural spec for the runtime thread-safety harness, wired to the REAL
race_harness. The parser scenarios feed genuine ThreadSanitizer output (modelled on the
turso free-threaded WAL race); the verdict/n-a scenarios call the real functions. Each
step returns its one output as a named fixture, so a missing producer is an error rather
than a KeyError midway through a scenario.
"""

from pathlib import Path
from typing import TypedDict

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


class Tree(TypedDict):
    """A repository the harness is pointed at, and the language it is told it is."""
    repo: Path
    lang: str


class Verdict(TypedDict):
    """The three things race_harness._verdict returns, named."""
    verdict: str
    band: str
    value: str


# --- parser scenarios -------------------------------------------------------

@given("ThreadSanitizer output reporting a data race in publish_backfill", target_fixture="output")
def given_one_race():
    return _ONE_RACE


@given("ThreadSanitizer output reporting two data races", target_fixture="output")
def given_two_races():
    return _ONE_RACE + _SECOND_RACE


@when("I parse the ThreadSanitizer report", target_fixture="findings")
def when_parse(output):
    return race_harness.parse_tsan(output)


@then("one data race is surfaced")
def then_one(findings):
    assert len(findings) == 1


@then("two data races are surfaced")
def then_two(findings):
    assert len(findings) == 2


@then(parsers.parse('the race points at "{fname}" line {line:d}'))
def then_location(findings, fname, line):
    f = findings[0]
    assert f["file"].endswith(fname), f["file"]
    assert f["line"] == line


@then("both conflicting access sites are recorded")
def then_accesses(findings):
    # The write (shared_wal_coordination.rs:1386) and the read (wal.rs:3498).
    accesses = findings[0]["accesses"]
    assert ("src/storage/shared_wal_coordination.rs", 1386) in accesses
    assert ("src/storage/wal.rs", 3498) in accesses


# --- verdict / n-a scenarios ------------------------------------------------

@given("a suite that ran under ThreadSanitizer with no race reported", target_fixture="findings")
def given_clean():
    return race_harness.parse_tsan(_CLEAN)


@when("I read the verdict", target_fixture="reading")
def when_verdict(findings) -> Verdict:
    verdict, band, value = race_harness._verdict(findings)
    return {"verdict": verdict, "band": band, "value": value}


@then("the verdict is no-race-in-tests")
def then_no_race(reading):
    assert reading["verdict"] == race_harness.NO_RACE_IN_TESTS


@then("the details disclose that the result is bounded by the test suite")
def then_bounded(reading):
    assert "bounded by the test suite" in reading["value"]


@given("a repository whose language the race harness does not support", target_fixture="tree")
def given_unsupported(tmp_path) -> Tree:
    return {"repo": tmp_path, "lang": "java"}


@when("I run the race harness", target_fixture="result")
def when_run(tree):
    return race_harness.detect_races(tree["repo"], tree["lang"], 5.0)


@then("the verdict is n/a")
def then_na(result):
    assert result["verdict"] == race_harness.NA


@then("no race is claimed either way")
def then_no_claim(result):
    assert result["findings"] == []
    assert result["band"] == "n/a"


# --- cross-reference scenario ----------------------------------------------

@given(parsers.parse('the static surface meter flagged "{path}"'), target_fixture="surface_files")
def given_flagged(path):
    return {path}


@when("I cross-reference the observed races against the flagged surface", target_fixture="confirmed")
def when_xref(output, surface_files):
    return race_harness.confirmed_surface(race_harness.parse_tsan(output), surface_files)


@then("the race is confirmed against the flagged surface")
def then_confirmed(confirmed):
    assert len(confirmed) == 1
    assert confirmed[0]["file"].endswith("shared_wal_coordination.rs")

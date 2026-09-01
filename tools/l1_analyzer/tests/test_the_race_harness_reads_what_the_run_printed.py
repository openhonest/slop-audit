"""What a race run means, read from what it printed, on a machine with no Rust.

Two stages watch a Rust suite run: a thread sanitizer, and a stress runner that runs the
suite many times looking for a panic that fires on some runs and not others. Both are
boundaries. Both decided what they had seen inside the same function that ran the
subprocess, so their verdicts could only be exercised on a machine with a nightly Rust
toolchain, which is not the machine this suite runs on.

Fifty-seven per cent of that module was unmeasured and both verdicts were inside it. This
module already knew the answer: `toolchain_reason_in` and `host_target_in` were lifted out
of their probes for exactly this reason, and its docstring says so. The two verdicts had not
followed.

Every case here is a distinction between "we did not measure" and "we measured and found
nothing", which is the reading this instrument exists to refuse.
"""

from l1_analyzer import race_harness

_RACE = """==================
WARNING: ThreadSanitizer: data race (pid=1)
  Write of size 8 at 0x7b0400000010 by thread T2:
    #0 counter::bump::h1 src/lib.rs:12 (app+0x1)
  Previous read of size 8 at 0x7b0400000010 by main thread:
    #0 counter::read::h2 src/lib.rs:20 (app+0x2)
SUMMARY: ThreadSanitizer: data race src/lib.rs:12 in counter::bump
==================
"""
_CLEAN = "running 4 tests\ntest result: ok. 4 passed; 0 failed\n"
_BUILD_FAILED = "error[E0432]: unresolved import `tokio`\n  --> src/lib.rs:1:5\n"


# --------------------------------------------------------------------------
# The sanitizer
# --------------------------------------------------------------------------

def test_a_race_the_sanitizer_saw_is_proven():
    """The one verdict here that is a proof. The sanitizer watched two threads touch the
    same address and one of them wrote."""
    result = race_harness.tsan_verdict(_RACE, returncode=101)
    assert result["verdict"] == race_harness.RACE_OBSERVED
    assert result["findings"]


def test_a_suite_that_ran_clean_is_bounded_by_the_suite_and_says_so():
    """Not a proof of safety. The sanitizer sees a race only on a pair of accesses the
    suite actually made, so a clean run bounds the answer by what the tests exercise."""
    result = race_harness.tsan_verdict(_CLEAN, returncode=0)
    assert result["findings"] == []
    assert result["verdict"] != race_harness.RACE_OBSERVED
    assert "suite passed" in result["details"]


def test_a_suite_that_would_not_build_is_not_a_clean_suite():
    """The distinction the whole module turns on. Nothing ran, so nothing was measured, and
    reporting it beside a suite that ran clean is the failure this tool reports in other
    people's code."""
    result = race_harness.tsan_verdict(_BUILD_FAILED, returncode=101)
    assert result["verdict"] == "n/a"
    assert "could not build" in result["details"]
    assert "E0432" in result["details"] or "tokio" in result["details"]


def test_a_race_found_before_the_timeout_still_counts():
    """The sanitizer prints the race when it sees it, not at the end. A run killed after
    that has still proven the race, and throwing it away because the suite did not finish
    would discard the one result that is certain."""
    result = race_harness.tsan_verdict(_RACE, returncode=124)
    assert result["verdict"] == race_harness.RACE_OBSERVED
    assert "timed out" in result["details"]


def test_a_timeout_with_nothing_printed_measured_nothing():
    result = race_harness.tsan_verdict(_CLEAN, returncode=124)
    assert result["verdict"] == "n/a"
    assert "timed out" in result["details"]


def test_a_suite_that_failed_for_its_own_reasons_is_still_a_reading():
    """A failing test is not a race and not a refusal. The sanitizer ran, saw no race, and
    the exit code is reported so a reader knows the suite was not green."""
    result = race_harness.tsan_verdict(_CLEAN, returncode=101)
    assert result["verdict"] != "n/a"
    assert "exit 101" in result["details"]


# --------------------------------------------------------------------------
# The stress runner
# --------------------------------------------------------------------------

_PANIC = ("running 4 tests\n"
          "thread 'worker' panicked at src/lib.rs:33:9:\n"
          "assertion failed: total == 100\n"
          "test result: FAILED. 3 passed; 1 failed\n")


def test_a_panic_on_some_runs_and_not_others_is_a_proven_race():
    """The only verdict this stage can prove. The suite's own assertion caught it, and it
    caught it on some runs and not others, which is what makes it a race rather than a bug
    that fires every time."""
    result = race_harness.stress_verdict(passed=7, runs=10, panics=race_harness.parse_panic(_PANIC))
    assert result["verdict"] == race_harness.RACE_OBSERVED
    assert result["findings"]
    assert "3 of 10" in result["details"]


def test_every_run_passing_is_bounded_by_the_suite_and_the_run_count():
    """Ten clean runs is evidence and not a proof. The details say what bounds it, because
    a reader who takes it for a proof stops looking."""
    result = race_harness.stress_verdict(passed=10, runs=10, panics=[])
    assert result["verdict"] == race_harness.NO_RACE_IN_STRESS
    assert "bounded by the suite" in result["details"]


def test_every_run_failing_the_same_way_is_not_a_race():
    """A failure that fires every time is deterministic. Calling it a race sends someone
    looking for a concurrency bug that is not there, and the suite is broken either way."""
    result = race_harness.stress_verdict(passed=0, runs=10, panics=race_harness.parse_panic(_PANIC))
    assert result["verdict"] == "n/a"
    assert "deterministic" in result["details"]


def test_two_panics_at_one_place_are_reported_once():
    """Ten runs of one racy assertion is one finding. Listing it ten times would make the
    count read as ten separate races."""
    twice = race_harness.parse_panic(_PANIC) + race_harness.parse_panic(_PANIC)
    result = race_harness.stress_verdict(passed=5, runs=10, panics=twice)
    assert len(result["findings"]) == 1


def test_a_mixed_run_with_no_panic_located_still_reports_the_race():
    """The runs disagreed, which is the finding. A panic whose place could not be read
    leaves the verdict standing and the location empty, rather than downgrading a real
    nondeterministic failure to a clean sweep because the output was not parsed."""
    result = race_harness.stress_verdict(passed=5, runs=10, panics=[])
    assert result["verdict"] == race_harness.RACE_OBSERVED

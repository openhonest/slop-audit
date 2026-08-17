"""The C# runtime harness (L1.19 Cobertura branch coverage, L1.20 repeat-run determinism).

Pure values in, verdict out. No fixture, no stub, no monkeypatch.

The old tests replaced _dotnet and _run_untrusted with a fake that both answered
`dotnet --version` and wrote the Cobertura report the module then read back, so the parser was
proved against the test's own XML and `dotnet test` could have been invoked with any flags at
all. The decisions those tests defended are now extracted: `_coverage_verdict(branches,
returncode, sdk)` and `_determinism_verdict(outcomes, sdk)` take plain values and return the
L1Result, so the bands, the not-run guard and the two coverage refusals are asserted directly.
What still needs a real .NET SDK and a real project fixture is the I/O half: that `dotnet test`
is invoked with the flags the docstring claims, in the repository, and that the report is found
where the collector writes it.
"""

from l1_analyzer import csharp_trace


def test_ran_tests_detects_execution():
    assert csharp_trace._ran_tests("Passed!  - Failed: 0, Total: 5")
    assert csharp_trace._ran_tests("Failed!  - Failed: 2, Total: 5")
    assert not csharp_trace._ran_tests("Build FAILED. error CS0246")


# --- the L1.19 verdict, extracted so it can be asserted without faking a run ---------------
#
# Written before `_coverage_verdict` exists. The deleted tests replaced both `_dotnet` and
# `_run_untrusted` with a fake that answered `dotnet --version` and wrote the Cobertura report
# the module then read back, so the band table was proved against the test's own XML and
# `dotnet test` could have been invoked with any flags at all. The claims are real and are
# restated here as values.

def test_a_completed_run_yields_the_covered_share_and_its_band():
    r = csharp_trace._coverage_verdict((38, 40), 0, "dotnet 8.0.401")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "38/40 branches" in r["details"]
    assert "suite passed" in r["details"] and "dotnet 8.0.401" in r["details"]


def test_a_failing_but_valid_run_is_still_measured():
    r = csharp_trace._coverage_verdict((7, 10), 1, "dotnet 8")
    assert r["value"] == 70.0 and r["band"] == "Not Healthy"
    assert "suite exit 1" in r["details"]


def test_the_coverage_band_boundaries_follow_the_spec():
    def band(covered, valid):
        return csharp_trace._coverage_verdict((covered, valid), 0, "d")["band"]
    assert band(95, 100) == "Healthy"        # above 90
    assert band(90, 100) == "Not Healthy"    # 90 exactly is not above 90
    assert band(60, 100) == "Not Healthy"    # 60 exactly is the floor
    assert band(59, 100) == "Slop"           # just under the floor


def test_a_timed_out_run_is_named_rather_than_scored():
    r = csharp_trace._coverage_verdict((38, 40), 124, "d")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"]


def test_a_run_that_wrote_no_cobertura_report_names_the_missing_collector():
    # No report means the collector was never referenced, NOT that coverage is 0.
    r = csharp_trace._coverage_verdict(None, 0, "d")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "coverlet.collector" in r["details"]
    assert "coverage.cobertura.xml not produced" in r["details"]


def test_branches_valid_of_zero_is_absent_not_zero_percent_and_carries_its_remedy():
    # Nothing had a branch to cover, usually because the code under test sits in the test
    # assembly. 0.0 here would band Slop and read as measured-and-terrible.
    r = csharp_trace._coverage_verdict((0, 0), 0, "d")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "test assembly" in r["details"] and "separate project" in r["details"]


# --- the L1.20 verdict, extracted so the per-run outcomes can be asserted ------------------

_PASSED = "Passed!  - Failed: 0, Passed: 5, Skipped: 0, Total: 5\n"
_FAILED = "Failed!  - Failed: 2, Passed: 3, Skipped: 0, Total: 5\n"


def test_every_run_passing_is_healthy():
    r = csharp_trace._determinism_verdict([(0, _PASSED)] * 5, "dotnet 8.0.401")
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "dotnet 8.0.401" in r["details"]


def test_the_detail_says_the_order_was_scheduler_varied_not_seed_controlled():
    # dotnet test takes no seed, so claiming a controlled shuffle would overstate the measure.
    r = csharp_trace._determinism_verdict([(0, _PASSED)] * 5, "d")
    assert "scheduler-varied" in r["details"] and "not seed-controlled" in r["details"]


def test_one_failing_run_is_not_healthy_and_the_run_carries_its_first_line():
    outcomes = [(0, _PASSED), (0, _PASSED), (1, _FAILED), (0, _PASSED), (0, _PASSED)]
    r = csharp_trace._determinism_verdict(outcomes, "d")
    assert r["value"] == "4/5" and r["band"] == "Not Healthy"
    assert "run 3: Failed!  - Failed: 2, Passed: 3, Skipped: 0, Total: 5" in r["details"]


def test_two_failing_runs_are_slop():
    outcomes = [(0, _PASSED), (1, _FAILED), (1, _FAILED), (0, _PASSED), (0, _PASSED)]
    assert csharp_trace._determinism_verdict(outcomes, "d")["band"] == "Slop"


def test_at_most_three_failing_runs_are_named():
    r = csharp_trace._determinism_verdict([(1, _FAILED)] * 5, "d")
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert r["details"].count("run ") == 3


def test_a_run_where_the_suite_never_executed_is_not_a_determinism_result():
    # A build error is not flakiness. 0/5 here would read as a flaky suite.
    outcomes = [(0, _PASSED), (1, "Build FAILED. error CS0246: type or namespace not found")]
    r = csharp_trace._determinism_verdict(outcomes, "dotnet 8")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "run 2" in r["details"] and "did not run" in r["details"]
    assert "dotnet 8" in r["details"]


def test_a_timed_out_run_stops_the_count_and_names_its_run():
    r = csharp_trace._determinism_verdict([(0, _PASSED), (0, _PASSED), (124, "")], "d")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"] and "run 3" in r["details"]


def test_a_terminal_run_stops_the_remaining_runs_from_being_made():
    # The harness hands the outcomes over lazily, so the verdict returning at run 1 is what
    # stops runs 2 and 3 from each burning a full timeout.
    made = []

    def outcomes():
        for attempt, pair in enumerate([(124, ""), (0, _PASSED), (0, _PASSED)], start=1):
            made.append(attempt)
            yield pair

    csharp_trace._determinism_verdict(outcomes(), "d")
    assert made == [1]


def test_no_runs_at_all_is_absent_not_a_clean_sweep():
    # 0 of 0 satisfies "every run passed". It must not band Healthy.
    r = csharp_trace._determinism_verdict([], "d")
    assert r["band"] == "n/a" and r["value"] == "n/a"

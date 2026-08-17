"""The Go runtime harness (L1.19 statement coverage, L1.20 shuffle determinism).

decision_space_coverage and test_determinism run the module's own suite, so they stay unproved
here: their old tests replaced _go and _run_untrusted with a fake that both answered `go
version` and wrote the coverage profile the module then read back, so the total parser was
proved against the test's own string, and the fake's unrecognised-command branch returned a
canned success, so any command it did not know about was filed under an answer written for a
different one. Proving those two needs a real Go toolchain and a real module fixture.

The decisions they used to hide are now values. _coverage_verdict and _determinism_verdict
take plain arguments and return the result, so the band tables, the three not-measured
coverage reasons and the three not-measured determinism reasons are asserted directly, with no
subprocess in sight.
"""

from l1_analyzer import go_trace


def test_ran_tests_detects_execution():
    assert go_trace._ran_tests("ok  pkg 0.1s")
    assert go_trace._ran_tests("--- FAIL: TestX")
    assert not go_trace._ran_tests("build failed: cannot find package")


def _func_output(pct: str) -> str:
    """Real `go tool cover -func` output: one line per function, then the tab-separated total
    line the parser reads."""
    return ("github.com/acme/widget/widget.go:12:\tNew\t\t100.0%\n"
            "github.com/acme/widget/widget.go:31:\tResize\t\t62.5%\n"
            f"total:\t\t\t\t\t\t\t(statements)\t{pct}%\n")


# --- L1.19: the cover tool's total read as a value ---------------------------

def test_a_profile_with_a_total_yields_the_statement_share_and_its_band():
    r = go_trace._coverage_verdict(_func_output("95.0"), True, 0, "", "go version go1.24.0 darwin/arm64")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "suite passed" in r["details"] and "go version go1.24.0 darwin/arm64" in r["details"]


def test_the_details_disclose_that_go_publishes_statement_coverage_not_branch_coverage():
    # L1.19 carries branch coverage for Python. The Go toolchain instruments statements, so
    # statement coverage is substituted into the same field. The value and the band cannot say
    # so; the detail line must.
    r = go_trace._coverage_verdict(_func_output("72.0"), True, 0, "", "go1.24.0")
    assert "statement coverage" in r["details"].lower()


def test_the_band_boundaries_follow_the_spec():
    band = lambda pct: go_trace._coverage_verdict(_func_output(pct), True, 0, "", "go1.24.0")["band"]
    assert band("90.1") == "Healthy"        # above 90
    assert band("90.0") == "Not Healthy"    # 90 exactly is not above 90
    assert band("60.0") == "Not Healthy"    # 60 exactly is the floor
    assert band("59.9") == "Slop"


def test_a_failing_suite_that_still_wrote_a_profile_is_measured():
    # The toolchain writes the profile for every package that built and ran, so a failing
    # suite is a real coverage reading and says which exit produced it.
    r = go_trace._coverage_verdict(_func_output("64.0"), True, 1, "FAIL\tacme/widget\t0.3s", "go1.24.0")
    assert r["value"] == 64.0 and r["band"] == "Not Healthy"
    assert "suite exit 1" in r["details"]


def test_a_timed_out_suite_is_named_rather_than_scored():
    r = go_trace._coverage_verdict("", False, 124, "timed out", "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"]


def test_a_profile_that_was_never_written_names_the_run_that_should_have_written_it():
    r = go_trace._coverage_verdict("", False, 1, "widget.go:9:2: undefined: helper\nFAIL\tacme/widget [build failed]",
                                   "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "no data" in r["details"] and "go test exit 1" in r["details"]
    assert "widget.go:9:2: undefined: helper" in r["details"]
    # It must not borrow the wording of the profile that existed but carried no total.
    assert "no statement total" not in r["details"]


def test_a_profile_carrying_no_total_is_its_own_reason():
    r = go_trace._coverage_verdict("mode: set\n", True, 0, "", "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "no statement total" in r["details"]


# --- L1.20: the shuffled runs counted from their outcomes --------------------

def _clean(seed: int) -> tuple[int, int, str]:
    return (seed, 0, f"ok  \tacme/widget\t0.2{seed}s\n")


def _failed(seed: int) -> tuple[int, int, str]:
    return (seed, 1, f"--- FAIL: TestResize (seed {seed})\nFAIL\tacme/widget\t0.3s\n")


def test_every_shuffled_run_passing_is_healthy():
    r = go_trace._determinism_verdict([_clean(s) for s in range(1, 6)], 5, "go1.24.0")
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "go1.24.0" in r["details"]


def test_one_short_of_every_run_is_not_healthy_and_names_the_seed_that_failed():
    outcomes = [_clean(1), _clean(2), _failed(3), _clean(4), _clean(5)]
    r = go_trace._determinism_verdict(outcomes, 5, "go1.24.0")
    assert r["value"] == "4/5" and r["band"] == "Not Healthy"
    # A bare 4/5 is a score with no reason. The failing seed and its own first line are what
    # let a reader start chasing the flake.
    assert "seed 3" in r["details"] and "--- FAIL: TestResize (seed 3)" in r["details"]


def test_two_failing_runs_are_slop():
    outcomes = [_clean(1), _failed(2), _failed(3), _clean(4), _clean(5)]
    r = go_trace._determinism_verdict(outcomes, 5, "go1.24.0")
    assert r["value"] == "3/5" and r["band"] == "Slop"


def test_at_most_three_failing_seeds_are_quoted():
    r = go_trace._determinism_verdict([_failed(s) for s in range(1, 6)], 5, "go1.24.0")
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert "seed 4" not in r["details"] and "seed 5" not in r["details"]
    assert "seed 1" in r["details"] and "seed 3" in r["details"]


def test_a_timed_out_run_is_not_a_failing_run():
    outcomes = [_clean(1), (2, 124, "panic: test timed out after 10m0s\ntimed out")]
    r = go_trace._determinism_verdict(outcomes, 5, "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "seed 2" in r["details"] and "timed out" in r["details"]
    assert "1/5" not in r["details"]


def test_a_suite_that_never_executed_is_not_a_suite_that_failed():
    # The not-run guard. A build error prints none of go's ran-a-package banners, and scoring
    # it 0/5 would read as a suite that falls over when shuffled rather than one that never
    # shuffled at all.
    outcomes = [(1, 1, "widget.go:9:2: undefined: helper\n")]
    r = go_trace._determinism_verdict(outcomes, 5, "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "seed 1" in r["details"] and "did not run" in r["details"]
    assert "go1.24.0" in r["details"] and "0/5" not in r["details"]


def test_fewer_outcomes_than_runs_promised_is_absent_not_a_low_score():
    # A short list with nothing in it to refuse over: the count it would band is a fraction
    # over runs that were never made, which is absent rather than bad.
    r = go_trace._determinism_verdict([_clean(1), _clean(2)], 5, "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "2 of 5" in r["details"]


def test_no_outcomes_at_all_is_absent_rather_than_nought_out_of_five():
    r = go_trace._determinism_verdict([], 5, "go1.24.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert r["value"] != "0/5"

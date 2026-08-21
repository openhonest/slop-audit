"""The C runtime harness (L1.19 best-effort gcov/lcov line coverage, L1.20 honest n/a - C has
no standard test-order randomizer).

Only the pure Makefile probe is tested here: a real Makefile on disk read by the real
_make_target. No stub, no monkeypatch.

decision_space_coverage and test_determinism drive a build, so they stay unproved here: their
old tests replaced _cc, _lcov and _run_untrusted with a fake that answered `cc --version`,
`make` and `lcov --summary` from strings the test author wrote, so the parser was proved
against its own input, and the fake's unrecognised-command branch returned a canned success,
so any command it did not know about was filed under an answer written for a different one.
Proving those two needs a real cc, make and lcov and a real C project fixture.

The decisions they used to hide are now values. _coverage_verdict and _determinism_verdict
take plain arguments and return the result, so the band table, the four not-measured reasons
and the permanent n/a for order-determinism are asserted directly, with no subprocess in
sight.
"""

from l1_analyzer import c_trace


def test_make_target_detects_test_and_check(tmp_path):
    """The reason travels with the absence. A bare None had the caller say "no Makefile
    test/check target found" for a Makefile it could not open, and the three ways of having
    no target send a reader to three different repairs."""
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\ncheck:\n\t./t\n")
    assert c_trace._make_target(tmp_path) == ("check", "")
    (tmp_path / "Makefile").write_text("all:\n\tgcc -o app main.c\n")
    target, why = c_trace._make_target(tmp_path)
    assert target is None and "declares no" in why
    (tmp_path / "Makefile").unlink()
    target, why = c_trace._make_target(tmp_path)
    assert target is None and "no Makefile" in why


def _summary(pct: str, covered: int, total: int) -> str:
    """A real `lcov --summary` block. The percentage lcov prints is the one the band reads, so
    the counts and the percentage are supplied together exactly as lcov supplies them."""
    return ("Reading tracefile cov.info\n"
            "Summary coverage rate:\n"
            f"  lines......: {pct}% ({covered} of {total} lines)\n"
            "  functions..: 90.0% (9 of 10 functions)\n"
            "  branches...: no data found\n")


# --- L1.19: the lcov summary read as a value ---------------------------------

def test_an_instrumented_run_yields_the_line_share_and_its_band():
    r = c_trace._coverage_verdict(_summary("95.0", 950, 1000), 0, "", "cc (GCC) 14.2.0", "check")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "950/1000 lines" in r["details"]
    assert "make check passed" in r["details"] and "cc (GCC) 14.2.0" in r["details"]


def test_the_details_disclose_that_c_publishes_line_coverage_not_branch_coverage():
    # L1.19 carries branch coverage for Python. C's toolchain has no standard branch-coverage
    # convention, so gcov LINE coverage is substituted into the same field. The value and the
    # band cannot say so; the detail line must.
    r = c_trace._coverage_verdict(_summary("72.0", 720, 1000), 0, "", "clang 18", "test")
    assert "line coverage" in r["details"].lower()
    assert "gcov" in r["details"].lower()


def test_the_band_boundaries_follow_the_spec():
    def band(pct):
        return c_trace._coverage_verdict(_summary(pct, 1, 1000), 0, "", "cc", "test")["band"]
    assert band("90.1") == "Healthy"        # above 90
    assert band("90.0") == "Not Healthy"    # 90 exactly is not above 90
    assert band("60.0") == "Not Healthy"    # 60 exactly is the floor
    assert band("59.9") == "Slop"


def test_a_failing_test_target_is_still_measured():
    # The gcov data is written by the instrumented run whether or not the tests passed, so a
    # non-zero make exit is a real coverage reading and says so.
    r = c_trace._coverage_verdict(_summary("64.0", 320, 500), 2, "make: *** [test] Error 1", "cc", "test")
    assert r["value"] == 64.0 and r["band"] == "Not Healthy"
    assert "make test exit 2" in r["details"]


def test_a_timed_out_build_is_named_rather_than_scored():
    r = c_trace._coverage_verdict("", 124, "timed out", "cc", "check")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"] and "make check" in r["details"]


def test_a_summary_with_no_line_reading_names_the_build_that_produced_it():
    r = c_trace._coverage_verdict("lcov: ERROR: no valid records found\n", 2,
                                  "cc: fatal error: no input files\nmake: *** [test] Error 1", "cc", "test")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "no gcov data" in r["details"] and "exit 2" in r["details"]
    assert "cc: fatal error: no input files" in r["details"]
    # It must not borrow the wording of the reading that did arrive but counted nothing.
    assert "no gcov lines" not in r["details"]


def test_nought_of_nought_lines_is_absent_not_nought_percent():
    # lcov prints 0.0% for an instrumented build that executed no instrumented code. A rate
    # over no lines is the absence of a measurement, not a measurement of zero.
    r = c_trace._coverage_verdict(_summary("0.0", 0, 0), 0, "", "cc (GCC) 14.2.0", "test")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert r["value"] != 0.0
    assert "no gcov lines" in r["details"] and "cc (GCC) 14.2.0" in r["details"]


def test_a_real_nought_percent_over_real_lines_is_still_a_measurement():
    # The mirror of the case above: 0 of 500 lines is a measured, terrible number and must be
    # banded Slop rather than swept into the same n/a.
    r = c_trace._coverage_verdict(_summary("0.0", 0, 500), 0, "", "cc", "test")
    assert r["value"] == 0.0 and r["band"] == "Slop"


# --- L1.20: a refusal C can never stop making --------------------------------

def test_determinism_for_c_is_a_permanent_declination_naming_the_compiler():
    # Not a gap in this harness: C ships no standard test-order randomiser, so there is no
    # shuffled run to count. The compiler is named so a reader sees a measurement declined for
    # the language rather than one that failed on this repository.
    r = c_trace._determinism_verdict("cc (GCC) 14.2.0")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "randomizer" in r["details"] and "cc (GCC) 14.2.0" in r["details"]
    assert "0/5" not in str(r["value"]) and "0 of 5" not in r["details"]

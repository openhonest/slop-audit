"""The Java runtime harness (L1.19 JaCoCo branch coverage, L1.20 Surefire random-order
determinism), tested at the two points where it is a pure function of its input.

What this file used to contain, and why it does not: eight tests that stubbed `_maven` and
`_run_untrusted`, fed `decision_space_coverage` and `test_determinism` a JaCoCo report and a
Surefire summary the test itself had written, and asserted the numbers back out. They proved
that the module returns what the test handed it. If Maven changed its output wording or
JaCoCo changed its report layout, every one of them stayed green while the harness broke in
the field. One of them, a `_maven` stub in the Gradle case, was verified dead: the module
returns the Gradle refusal before `_maven` is ever called.

The cause was module shape, not test care. `decision_space_coverage` probed the JDK, ran
`mvn test jacoco:report`, located the report, parsed it and decided the band inside one
function, so there was no value to assert against and a fake was the only way in. That
extraction is now done: `_coverage_verdict(branches, returncode, jdk)` and
`_determinism_verdict(outcomes, jdk)` take plain values and return the L1Result, so the bands,
the not-run guard, the coverage-missing n/a and the per-seed failure reason are asserted
below as values, with no stub anywhere in this file.
"""

import pytest
from l1_analyzer import java_trace


def _branch_xml(covered: int, missed: int) -> str:
    """A JaCoCo report carrying an INSTRUCTION counter and a BRANCH counter. Real report
    layout, so ElementTree parses it the way it parses Maven's own output."""
    return (f'<report name="x"><counter type="INSTRUCTION" missed="1" covered="9"/>'
            f'<counter type="BRANCH" missed="{missed}" covered="{covered}"/></report>')


# --- JaCoCo BRANCH-counter parsing --------------------------------------------

@pytest.mark.parametrize("covered,missed", [(12, 7), (95, 5), (40, 60), (0, 0)])
def test_branch_totals_reads_the_report_level_branch_counter(covered, missed):
    assert java_trace._branch_totals(_branch_xml(covered, missed)) == (covered, missed)


def test_branch_totals_ignores_the_instruction_counter():
    # The INSTRUCTION counter in the sample carries 9 covered and 1 missed. Reading the first
    # counter rather than the BRANCH one would return those numbers instead.
    assert java_trace._branch_totals(_branch_xml(12, 7)) == (12, 7)


def test_branch_totals_returns_zeroes_when_the_report_has_no_branch_counter():
    # A project with no branches to cover, and a report whose BRANCH counter never appeared,
    # produce the same (0, 0). The module cannot tell them apart, and neither can a reader of
    # the number. Recorded here because the conflation is real, not because it is right.
    xml = '<report name="x"><counter type="INSTRUCTION" missed="1" covered="9"/></report>'
    assert java_trace._branch_totals(xml) == (0, 0)


# --- the not-run guard --------------------------------------------------------

def test_ran_tests_detects_execution():
    assert java_trace._ran_tests("Tests run: 5, Failures: 0, Errors: 0")
    assert not java_trace._ran_tests("[ERROR] COMPILATION ERROR : cannot find symbol")


# --- the L1.19 verdict, extracted so it can be asserted without faking a build -------------
#
# Written before `_coverage_verdict` exists. The deleted tests proved this band table only
# through a replaced `_run_untrusted`, so Maven could have been invoked with the wrong goals
# in the wrong directory under the wrong JDK and every one of them would still have passed.
# The claims they defended are real and are restated here as values.

def test_a_completed_build_yields_the_covered_share_and_its_band():
    r = java_trace._coverage_verdict((38, 2), 0, "openjdk 21.0.2")
    assert r["value"] == 95.0 and r["band"] == "Healthy"
    assert "38/40 decision branches" in r["details"]
    assert "suite passed" in r["details"] and "openjdk 21.0.2" in r["details"]


def test_a_failing_but_valid_build_is_still_measured():
    # A non-zero exit means tests ran and some failed, which is a real coverage reading.
    r = java_trace._coverage_verdict((7, 3), 1, "openjdk 21")
    assert r["value"] == 70.0 and r["band"] == "Not Healthy"
    assert "suite exit 1" in r["details"]


def test_the_coverage_band_boundaries_follow_the_spec():
    def band(covered, missed):
        return java_trace._coverage_verdict((covered, missed), 0, "j")["band"]
    assert band(95, 5) == "Healthy"          # above 90
    assert band(90, 10) == "Not Healthy"     # 90 exactly is not above 90
    assert band(60, 40) == "Not Healthy"     # 60 exactly is the floor
    assert band(59, 41) == "Slop"            # just under the floor


def test_a_timed_out_build_is_named_rather_than_scored():
    r = java_trace._coverage_verdict((38, 2), 124, "j")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"]


def test_a_build_that_wrote_no_jacoco_report_names_the_missing_plugin():
    # No report means the coverage tool is not wired into the build, NOT that coverage is 0.
    r = java_trace._coverage_verdict(None, 0, "j")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "JaCoCo" in r["details"] and "jacoco.xml not produced" in r["details"]


def test_zero_enumerable_branches_is_absent_not_zero_percent():
    # A share of no branches is absent. 0.0 here would band Slop and read as measured.
    r = java_trace._coverage_verdict((0, 0), 0, "j")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "zero BRANCH" in r["details"]


# --- the refusals that decide a project cannot be measured here ---------------------------

def test_a_gradle_project_is_refused_by_name(tmp_path):
    # The deleted suite stubbed _maven for this case. The stub was dead: the Gradle refusal
    # is returned before _maven is ever called, which is why it needs no stub here either.
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }\n")
    assert java_trace._unsupported_reason(tmp_path) == "Gradle Java projects not yet supported by this harness"


def test_a_kotlin_dsl_gradle_project_is_refused_by_the_same_name(tmp_path):
    (tmp_path / "build.gradle.kts").write_text("plugins { java }\n")
    assert java_trace._unsupported_reason(tmp_path) == "Gradle Java projects not yet supported by this harness"


def test_a_project_with_no_build_file_at_all_is_told_what_it_needs(tmp_path):
    assert java_trace._unsupported_reason(tmp_path) == "needs a Maven build (no pom.xml found)"


# --- the L1.20 verdict, extracted so the per-seed outcomes can be asserted -----------------

def _ok(n=12):
    return f"[INFO] Tests run: {n}, Failures: 0, Errors: 0, Skipped: 0\n"


def _failed(failures=2, n=12):
    return f"[INFO] Tests run: {n}, Failures: {failures}, Errors: 0, Skipped: 0\n"


def test_every_randomized_run_passing_is_healthy():
    r = java_trace._determinism_verdict([(0, _ok())] * 5, "openjdk 21")
    assert r["value"] == "5/5" and r["band"] == "Healthy"
    assert "openjdk 21" in r["details"]


def test_one_failing_run_is_not_healthy_and_the_seed_carries_its_counts():
    outcomes = [(0, _ok()), (0, _ok()), (1, _failed(2)), (0, _ok()), (0, _ok())]
    r = java_trace._determinism_verdict(outcomes, "j")
    assert r["value"] == "4/5" and r["band"] == "Not Healthy"
    assert "seed 3: Tests run: 12, Failures: 2, Errors: 0, Skipped: 0" in r["details"]


def test_two_failing_runs_are_slop():
    outcomes = [(0, _ok()), (1, _failed()), (1, _failed()), (0, _ok()), (0, _ok())]
    assert java_trace._determinism_verdict(outcomes, "j")["band"] == "Slop"


def test_at_most_three_failing_seeds_are_named():
    r = java_trace._determinism_verdict([(1, _failed())] * 5, "j")
    assert r["value"] == "0/5" and r["band"] == "Slop"
    assert r["details"].count("seed ") == 3


def test_a_failing_seed_with_no_summary_line_still_carries_a_reason():
    r = java_trace._determinism_verdict([(0, _ok()), (1, "Tests run: 1\n[ERROR] boom")], "j")
    assert "seed 2:" in r["details"]


def test_a_run_that_executed_no_tests_is_not_a_determinism_result():
    # A compilation failure is not flakiness. 0/5 here would read as a flaky suite.
    outcomes = [(0, _ok()), (1, "[ERROR] COMPILATION ERROR : cannot find symbol")]
    r = java_trace._determinism_verdict(outcomes, "openjdk 21")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "seed 2" in r["details"] and "did not run" in r["details"]
    assert "openjdk 21" in r["details"]


def test_a_timed_out_run_stops_the_count_and_names_its_seed():
    outcomes = [(0, _ok()), (0, _ok()), (124, "")]
    r = java_trace._determinism_verdict(outcomes, "j")
    assert r["band"] == "n/a" and r["value"] == "n/a"
    assert "timed out" in r["details"] and "seed 3" in r["details"]


def test_a_terminal_run_stops_the_remaining_runs_from_being_made():
    # The harness hands the outcomes over lazily, so the verdict returning at seed 2 is what
    # stops seeds 3, 4 and 5 from each burning a full timeout.
    made = []

    def outcomes():
        for seed, pair in enumerate([(124, ""), (0, _ok()), (0, _ok())], start=1):
            made.append(seed)
            yield pair

    java_trace._determinism_verdict(outcomes(), "j")
    assert made == [1]


def test_no_runs_at_all_is_absent_not_a_clean_sweep():
    # 0 of 0 satisfies "every run passed". It must not band Healthy.
    r = java_trace._determinism_verdict([], "j")
    assert r["band"] == "n/a" and r["value"] == "n/a"

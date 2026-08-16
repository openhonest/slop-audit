"""The Java runtime harness (L1.19 JaCoCo branch coverage, L1.20 Surefire random-order
determinism), tested at the two points where it is a pure function of its input.

What this file used to contain, and why it does not: eight tests that stubbed `_maven` and
`_run_untrusted`, fed `decision_space_coverage` and `test_determinism` a JaCoCo report and a
Surefire summary the test itself had written, and asserted the numbers back out. They proved
that the module returns what the test handed it. If Maven changed its output wording or
JaCoCo changed its report layout, every one of them stayed green while the harness broke in
the field. One of them, a `_maven` stub in the Gradle case, was verified dead: the module
returns the Gradle refusal before `_maven` is ever called.

The cause is module shape, not test care. `decision_space_coverage` probes the JDK, runs
`mvn test jacoco:report`, locates the report, parses it and decides the band inside one
function, so there is no value to assert against and a fake is the only way in. Extracting
`_coverage_result(covered, missed, returncode, jdk) -> L1Result` and
`_determinism_result(per_seed, jdk) -> L1Result` is what makes those tests honest, and it is
filed as separate work. Until then the bands, the not-run guard, the coverage-missing n/a and
the per-seed failure reason are proved by nothing.
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

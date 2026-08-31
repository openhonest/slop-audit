"""C#'s branch counts are read by a function a test can call.

The reading sat inside the function that runs `dotnet test`, so proving it needed the .NET
SDK on the machine. It was proved by a stand-in until the 2026-08-17 sweep removed those,
and since then by nothing: 58% of that harness was unreached, the lowest of the nine, and
every line that decides what a coverage report says was in the unreached part.

Java and Ruby already lift their readers out for exactly this reason, and each is covered.
C# was the one left with the reading welded to the subprocess.

What the reader has to get right, and what these hold it to. Cobertura writes the two
branch counts as attributes on the top-level `coverage` element. A report with the element
and no counts is a schema this reader does not know, which is a different fact from a
project with no branches, and reading it as zero would publish Slop for a repository whose
coverage was never measured.
"""

import pytest
from l1_analyzer import csharp_trace

_FULL = ('<?xml version="1.0"?>\n'
         '<coverage line-rate="0.9" branch-rate="0.95" branches-valid="40" '
         'branches-covered="38" version="1.9" timestamp="0">\n'
         '  <packages/>\n</coverage>\n')

_NO_BRANCHES = ('<?xml version="1.0"?>\n'
                '<coverage line-rate="0.9" branches-valid="0" branches-covered="0">\n'
                '  <packages/>\n</coverage>\n')

_NO_COUNTS = ('<?xml version="1.0"?>\n'
              '<coverage line-rate="0.9" version="1.9">\n  <packages/>\n</coverage>\n')


def test_the_two_branch_counts_are_read_in_the_order_the_verdict_wants():
    """Covered first, then valid. The verdict takes (covered, total) and the report writes
    them the other way round, which is one transposition away from a coverage of 105%."""
    assert csharp_trace._branch_totals(_FULL) == (38, 40)


def test_a_project_with_no_branches_reads_as_zero_of_zero():
    assert csharp_trace._branch_totals(_NO_BRANCHES) == (0, 0)


def test_a_report_carrying_no_branch_counts_is_not_a_coverage_of_zero():
    """The refusal that must never become 0.0. A report without the attributes is a schema
    this reader does not know, and grading it Slop would publish a verdict on a repository
    whose coverage was never measured."""
    assert csharp_trace._branch_totals(_NO_COUNTS) is None


def test_a_report_that_is_not_a_report_at_all_is_refused(tmp_path):
    for text in ("", "not xml", "<other branches-valid=\"3\"/>"):
        assert csharp_trace._branch_totals(text) is None, text


@pytest.mark.parametrize(("covered", "valid", "band"), [
    (40, 40, "Healthy"), (37, 40, "Healthy"), (36, 40, "Not Healthy"),
    (24, 40, "Not Healthy"), (23, 40, "Slop"), (0, 40, "Slop"),
])
def test_the_bands_sit_where_the_specification_puts_them(covered, valid, band):
    """Over 90 Healthy, 60 to 90 Not Healthy, under 60 Slop. Held here because the sweep
    left them proved by nothing, and a band boundary that drifts is a grade that drifts."""
    assert csharp_trace._coverage_verdict((covered, valid), 0, "dotnet 8")["band"] == band

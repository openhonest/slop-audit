"""A coverage share whose scope is not stated cannot be compared with another one.

Two runs of the same commit on the same compiler reported L1.19 at 66.9 and 65.1. The
numerator agreed within four regions and the denominator was 7,137 apart, which is the whole
1.8 points. Reported on 2026-09-06 by the session auditing turso, who could not account for
it, and neither could the report: the details line gives a percentage and two region counts
and never says how much of the repository they came from.

Measured here rather than guessed at. A warm target directory does not move the denominator:
a crate built twice reports the same regions both times, and a dependency's regions never
enter the report at all. What does move it is which directory cargo was pointed at. In a
two-member workspace:

    at the workspace root   26 regions across 2 files
    inside one member       13 regions across 1 file

That is cargo behaving as documented, and it means the same repository has several honest
coverage figures depending on where the run started. A reader handed one of them cannot tell
which, so the number is not comparable to any other and nothing says so.

The file count travels with the figure for the same reason the scope does. It is not the
whole answer to turso's 7,137, and it would have let them see in seconds that the two runs
had read different amounts of the repository.
"""

from __future__ import annotations

from l1_analyzer import rust_trace

_RAN = "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out\n"


def test_the_details_say_how_many_files_the_report_covered():
    result = rust_trace._coverage_verdict((100, 66), 0, "rustc 1.88", 600.0, _RAN, 12)
    assert "12 file" in result["details"], result["details"]


def test_one_file_is_said_in_the_singular():
    """A reader who meets "1 files" stops trusting the sentence around it."""
    result = rust_trace._coverage_verdict((10, 5), 0, "rustc 1.88", 600.0, _RAN, 1)
    assert "1 file," in result["details"] or "1 file " in result["details"], result["details"]


def test_the_figure_itself_is_unchanged():
    """The share is right and stays right. What was missing is what it was a share of."""
    assert rust_trace._coverage_verdict((100, 66), 0, "rustc 1.88", 600.0, _RAN, 12)["value"] == 66.0


def test_a_file_table_this_reader_cannot_count_is_not_a_count_of_none():
    """Nothing rather than zero. A zero would be a real answer to a different question, and
    this repository's own clause 8 caught it on the first run after this returned one: a file
    table nobody could read, reported as a measurement of no files."""
    result = rust_trace._coverage_verdict((100, 66), 0, "rustc 1.88", 600.0, _RAN, None)
    assert "could not count" in result["details"], result["details"]
    assert "0 file" not in result["details"]


def test_an_unreadable_report_yields_nothing_rather_than_zero():
    assert rust_trace._files_measured({}) is None
    assert rust_trace._files_measured({"data": [{"files": []}]}) == 0

"""A suite writes into the tree it runs in, so nothing static may be read after it.

MEASURED 2026-09-23 on a four-file Ruby project written for the executing corpus. The project
starts SimpleCov, as every Ruby project must for coverage to be measurable at all, and
SimpleCov writes its report into the repository. The report carries the rendered SOURCE of the
file under audit, so the dead-code corpus read the name of an unreferenced function out of the
report about that function and stopped calling it dead:

    execution off:  L1.12 = 38.46, Slop
    execution on:   L1.12 = 0.0,   Healthy

The number went from the worst band to the best because the tests had run. Seven readings sat
below the coverage run: L1.12, L1.13, L1.14, L1.18b, the path cover, the thread surface and
the absolute-path scan, with interleaving robustness an eighth in the CLI above them. Java's
target/, C's .gcda files, JavaScript's coverage output and Python's .coverage are the same
shape; Ruby is only the one that writes readable source.

The fix is an ORDER rather than a rule about SimpleCov, and this is the test that holds it.
Nothing measures the order from the outside, so it is measured from the panel itself: the two
rows that execute the project's code are the last two written, which is the same statement.

The corresponding test for the Rust port is `panel::tests::the_two_rows_that_execute_are_last`.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import indicators
from l1_analyzer.boundary import boundary

# The two rows that run the audited project's own code. Everything else reads its source.
EXECUTING = ("L1.19", "L1.20")


@boundary
def a_repository(tmp_path: Path) -> Path:
    """One tiny Python file, which is all this needs: the question is the ORDER the panel is
    written in, and every row is written whatever the repository holds."""
    (tmp_path / "band.py").write_text(
        "def band(n):\n    if n < 0:\n        return 'neg'\n    return 'pos'\n")
    return tmp_path


def test_the_two_rows_that_execute_are_the_last_two_written(tmp_path):
    panel = indicators.compute_source_indicators(
        a_repository(tmp_path), lang="python", exec_tests=False, timeout_seconds=30.0,
        classify_state_bounds=True, python_executable=None, build_args=())
    written = [key for key in panel if key != "lang"]
    assert written[-2:] == list(EXECUTING), (
        "every static reading must be taken before anything runs, and these are the last "
        f"rows written: {written[-4:]}")


def test_no_static_row_is_written_after_a_row_that_executes(tmp_path):
    """The same rule said the other way round, because the first test would still pass if a
    new static row were appended at the very end and the two executing rows moved up one."""
    panel = indicators.compute_source_indicators(
        a_repository(tmp_path), lang="python", exec_tests=False, timeout_seconds=30.0,
        classify_state_bounds=True, python_executable=None, build_args=())
    written = [key for key in panel if key != "lang"]
    first_executing = min(written.index(code) for code in EXECUTING)
    after = [key for key in written[first_executing:] if key not in EXECUTING]
    assert not after, f"these rows are read from a tree a run may have changed: {after}"

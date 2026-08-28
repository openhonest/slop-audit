"""The static coverage row said the trace is not run, on runs that run it.

The panel enumerates decision points without executing anything, and its detail ends:
"exercised-coverage fraction requires a test-execution trace (not run by this reference
implementation)". That was true of the website, which never runs anyone's code.

The CLI does run it. On a Java repository the harness invoked Maven, found the JDK, and
reported exactly why coverage was not produced. The reader got both sentences at once: ours
saying the trace is not run, and the harness's saying what happened when it ran.

The parenthesis is the older, larger version of the same claim we already removed from the
footer, where one line asserted the runtime harness is Python-only. It has not been Python-
only for some time: there are harnesses for eight languages and the Java one works. Both
sentences told non-Python adopters we could not do a thing we do.

The row says what it counted and stops. Whether a trace ran, and what it found, belongs to
whoever ran it.
"""

import pathlib

from l1_analyzer import indicators


def _detail(repo: pathlib.Path) -> str:
    return str(indicators._compute_decision_space(repo, "python")["details"])


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "app.py").write_text(
        "def pick(kind):\n"
        "    if kind == 'a':\n        return 1\n"
        "    if kind == 'b':\n        return 2\n    return 0\n")
    return tmp_path


def test_the_row_says_what_it_counted(tmp_path):
    detail = _detail(_repo(tmp_path))
    assert "decision points" in detail
    assert "files" in detail


def test_it_does_not_say_whether_a_trace_was_run(tmp_path):
    """It cannot know. The same function serves the website, which runs nothing, and the
    CLI, which runs the suite, and it was written as though only the first existed."""
    detail = _detail(_repo(tmp_path))
    assert "not run" not in detail
    assert "reference implementation" not in detail


def test_it_still_says_the_count_is_not_a_coverage_figure(tmp_path):
    """The bound has to survive. A count of decision points is not the share of them a
    test reaches, and dropping the sentence entirely would leave a number that reads as
    one."""
    detail = _detail(_repo(tmp_path))
    assert "exercises" in detail or "exercised" in detail or "reach" in detail


def test_the_band_stays_absent(tmp_path):
    """Nothing about the wording changes what was measured, which is a count and not a
    fraction, so there is still no band to give it."""
    assert indicators._compute_decision_space(_repo(tmp_path), "python")["band"] == "n/a"

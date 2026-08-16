"""The gate must not report a reading the thread-safety meter never took.

The ratchet guarded itself with `_verdict_of(ts) == thread_surface.UNREAD`, which names ONE
of the three ways the meter can fail to read. A C, C# or unknown-language repository takes a
different one - there is no scanner for it at all, and the verdict is n/a - so it walked
straight past the guard, printed the meter's empty counts as `0/0 thread-safety overrides`,
and at a baseline of 4 FAILED the commit demanding the adopter lower their baseline to zero
on the strength of a measurement that did not happen. That is the ratchet ratcheting itself
open, which is the exact failure the guard was written to prevent.

These tests pin the reading, not the wording: a repository whose surface was not read says so
and is not gated, and a repository whose surface WAS read still counts.
"""

from __future__ import annotations

from pathlib import Path

from l1_analyzer import cli, thread_surface


def _repo(tmp_path: Path, name: str, source: str) -> Path:
    (tmp_path / name).write_text(source)
    return tmp_path


_C_SOURCE = "int add(int a, int b) {\n  return a + b;\n}\n"
_PY_SOURCE = "import threading\n\n\ndef go(x):\n    return x + 1\n"


def test_a_language_with_no_scanner_is_reported_as_not_measured(tmp_path, capsys):
    _repo(tmp_path, "main.c", _C_SOURCE)
    assert cli.main([str(tmp_path), "--lang", "c", "--gate", "--max-thread-exposed", "0"]) == 0
    line = capsys.readouterr().out
    assert "thread-safety surface not measured" in line
    assert "thread-safety overrides" not in line, "an unread meter printed a count of overrides"


def test_a_loose_baseline_over_a_language_with_no_scanner_does_not_fail_the_commit(tmp_path, capsys):
    """The downward arm of the ratchet. Over a repository the meter never read, `0` is not the
    real count, so "lower it to 0" is advice built out of nothing - and it used to fail the
    commit until the adopter took it."""
    _repo(tmp_path, "main.c", _C_SOURCE)
    assert cli.main([str(tmp_path), "--lang", "c", "--gate", "--max-thread-exposed", "4"]) == 0
    assert "Lower it to 0" not in capsys.readouterr().out


def test_a_repository_of_no_recognised_language_is_reported_as_not_measured(tmp_path, capsys):
    (tmp_path / "README.md").write_text("# nothing to compile\n")
    assert cli.main([str(tmp_path), "--gate", "--max-thread-exposed", "4"]) == 0
    out = capsys.readouterr().out
    assert "thread-safety surface not measured" in out
    assert "Lower it to 0" not in out


def test_a_language_with_a_scanner_still_reports_the_count_it_read(tmp_path, capsys):
    """The other half of the fix: "not measured" must not swallow a real reading. Python has a
    scanner, so a Python repository is counted against the baseline as before."""
    _repo(tmp_path, "app.py", _PY_SOURCE)
    assert cli.main([str(tmp_path), "--lang", "python", "--gate", "--max-thread-exposed", "0"]) == 0
    assert "0/0 thread-safety overrides" in capsys.readouterr().out


def test_measured_separates_a_reading_from_every_way_of_not_reading():
    """All three not-readings, at the predicate itself. `_na` is the one the gate let through."""
    assert not thread_surface.measured(thread_surface._na("c"))
    assert not thread_surface.measured(
        thread_surface._unread("python", 0, {"counts": {}, "paths": []}))
    # The shape a refusal reaches the panel in: indicators._measure turns IncompleteCode into
    # an n/a dict that carries value, band and details, and no verdict at all.
    assert not thread_surface.measured({"value": "n/a", "band": "n/a", "details": "..."})
    assert thread_surface.measured({"verdict": thread_surface.CLEAN, "counts": {}})


def test_a_scanner_that_read_nothing_is_still_unread_not_n_a():
    """The two not-readings keep their own words, because they send the reader to different
    places: n/a is ours to fix, unread is the repository's scope rules or its syntax."""
    assert thread_surface._na("c")["verdict"] == thread_surface.NO_SCANNER
    assert thread_surface._unread("python", 0, {"counts": {}, "paths": []})["verdict"] == thread_surface.UNREAD

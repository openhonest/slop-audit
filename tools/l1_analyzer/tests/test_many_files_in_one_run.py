"""Measuring several files in one run, and not silently measuring one of them.

`--honest-code a.py b.py` returned a result describing `a.py` alone. Nothing said the second
path had been dropped: argparse absorbed it as the positional repository argument, which
this branch returns before ever reading. A caller naming ten files got a clean-looking
result about one of them, and would reasonably read it as covering all ten. An instrument
answering a narrower question than it was asked, without saying so, is the shape this
package has spent a day removing.

The batch shape falls out of the same fix and pays for itself. The Honest Code analysis
costs about nothing: on a small file a real run takes as long as `--help`, so the whole bill
is process startup, an interpreter plus tree-sitter grammars for nine languages. Ten files
one at a time pays that ten times.

One path returns exactly what it always returned. A consumer already reads that shape, and
changing it to serve a new one would break a working integration to add a feature.
"""

import json
import time

import pytest
from l1_analyzer import cli

DIRTY = "def f(x, timeout=30):\n    return x\n"
CLEAN = "def f(x: int, timeout: int) -> int:\n    return x\n"


def _run(argv: list[str], capsys) -> tuple[int, str, str]:
    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture
def files(tmp_path):
    (tmp_path / "one.py").write_text(DIRTY)
    (tmp_path / "two.py").write_text(DIRTY)
    (tmp_path / "three.py").write_text(CLEAN)
    return [str(tmp_path / n) for n in ("one.py", "two.py", "three.py")]


# --------------------------------------------------------------------------
# One file, unchanged
# --------------------------------------------------------------------------

def test_one_file_returns_exactly_what_it_always_returned(files, capsys):
    """A consumer already reads this shape. Changing it to serve the batch case would
    break a working integration to add a feature."""
    _code, out, _err = _run(["--honest-code", files[0], "--format", "json"], capsys)
    assessment = json.loads(out)
    assert isinstance(assessment, dict)
    assert assessment["path"] == files[0]


def test_one_clean_file_still_says_nothing(files, capsys):
    code, out, err = _run(["--honest-code", files[2]], capsys)
    assert code == 0 and out.strip() == "" and err.strip() == ""


# --------------------------------------------------------------------------
# Several files, all of them measured
# --------------------------------------------------------------------------

def test_every_file_named_is_measured(files, capsys):
    _code, out, _err = _run(["--honest-code", *files, "--format", "json"], capsys)
    results = json.loads(out)
    assert [r["path"] for r in results] == files


def test_a_second_path_is_no_longer_swallowed_by_the_repository_argument(files, capsys):
    """The defect exactly. It was not ignored, it was parsed as a different argument, and
    the branch that answers returns before anything reads that argument."""
    _code, out, _err = _run(["--honest-code", files[0], files[1], "--format", "json"], capsys)
    results = json.loads(out)
    assert len(results) == 2


def test_the_hook_shape_reports_every_file_that_has_something_to_change(files, capsys):
    code, _out, err = _run(["--honest-code", *files], capsys)
    assert code == 1
    assert "one.py:" in err and "two.py:" in err


def test_a_clean_file_among_dirty_ones_contributes_nothing(files, capsys):
    _code, _out, err = _run(["--honest-code", *files], capsys)
    assert "three.py" not in err


def test_a_batch_of_clean_files_says_nothing_and_succeeds(tmp_path, capsys):
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text(CLEAN)
    code, out, err = _run(["--honest-code", str(tmp_path / "a.py"), str(tmp_path / "b.py")],
                          capsys)
    assert code == 0 and out.strip() == "" and err.strip() == ""


def test_the_text_report_covers_each_file_in_turn(files, capsys):
    _code, out, _err = _run(["--honest-code", *files, "--format", "text"], capsys)
    assert out.count("Honest Code conformity") == 3


# --------------------------------------------------------------------------
# What it refuses
# --------------------------------------------------------------------------

def test_a_path_that_is_not_there_is_refused_before_anything_is_measured(files, tmp_path):
    """Refused rather than skipped. A caller who named a file that is not there has a
    different problem from one whose file is clean, and a run that quietly measured the
    rest would report a coverage it did not have."""
    with pytest.raises(SystemExit):
        cli.main(["--honest-code", files[0], str(tmp_path / "absent.py")])


def test_a_directory_is_refused_with_a_message(tmp_path):
    """It used to return something that was not JSON, which at least failed loudly. It says
    what it wants now."""
    with pytest.raises(SystemExit):
        cli.main(["--honest-code", str(tmp_path)])


# --------------------------------------------------------------------------
# What the batch is for
# --------------------------------------------------------------------------

def test_measuring_many_files_in_one_call_costs_about_one_file(files):
    """The whole bill is process startup, so the saving is the point of the flag rather
    than a side effect of it. Inside one process the work itself is what is left, and this
    asserts the work stays small enough for the batch to be worth having."""
    from l1_analyzer import honest_code

    started = time.perf_counter()
    for path in files * 4:
        honest_code.assess_file(path)
    each = (time.perf_counter() - started) / (len(files) * 4)
    assert each < 0.05, f"{each * 1000:.1f}ms per file leaves the batch saving nothing to win"

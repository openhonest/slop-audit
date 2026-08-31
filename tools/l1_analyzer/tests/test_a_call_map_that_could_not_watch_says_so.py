"""The call map names the pure lane, and a lane it could not watch is not a clean lane.

The map sorts a module's functions into a pure lane and a lane that touches the outside.
Reading the source can only guess: a function that calls another which opens a file looks
pure from where it sits. So the suite is run and watched, and what the watcher saw settles
the guess.

A suite that could not be watched is the case this holds. No writes are seen, so every
function looks pure, and the map that comes out is the best possible map made from no
evidence at all. The reason is printed above it, because a caller reading a clean pure lane
has to know whether that came from watching or from watching nothing.
"""

from l1_analyzer import cli

_MODULE = ("def band(n: int) -> str:\n"
           "    return 'high' if n > 10 else 'low'\n")


def test_a_suite_that_could_not_be_watched_is_named_above_the_map(tmp_path, capsys):
    """The tests here import a module that is not there, so nothing runs and nothing is
    seen. The map still prints, and the sentence above it says why the pure lane is free."""
    (tmp_path / "m.py").write_text(_MODULE)
    (tmp_path / "test_m.py").write_text("import not_a_real_module_at_all\n")
    assert cli._report_call_map(tmp_path / "m.py", (tmp_path / "test_m.py",), "l1") == 0
    printed = capsys.readouterr().out
    assert "could not be watched" in printed
    assert "band" in printed


def test_a_suite_that_ran_prints_the_map_and_no_excuse(tmp_path, capsys):
    (tmp_path / "m.py").write_text(_MODULE)
    (tmp_path / "test_m.py").write_text(
        "import sys\nsys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))\n"
        "from m import band\n\n\ndef test_band():\n    assert band(20) == 'high'\n")
    assert cli._report_call_map(tmp_path / "m.py", (tmp_path / "test_m.py",), "l1") == 0
    printed = capsys.readouterr().out
    assert "could not be watched" not in printed
    assert "band" in printed

"""The panel audits a tree, so it refuses a file and a path that is not there.

Twenty of the twenty-two stages read a repository. The git history, the config files, the
coverage run and the test run all need a tree to walk. A single file used to reach the
coverage runner and come back as a stack trace, which reads as the tool being broken rather
than as the caller pointing it at the wrong thing.

Two refusals rather than one, because they send the reader to different places. A path that
is not there is a typo. A path that is there and is a file is someone who wanted the clause
check or the facets report, both of which do take one file, and the message says so.
"""

import pytest
from l1_analyzer import cli


def test_a_path_that_is_not_there_is_named(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nowhere")]) == 2
    assert "does not exist" in capsys.readouterr().err


def test_a_single_file_is_refused_with_what_to_do_instead(tmp_path, capsys):
    """Pointing at a file is a reasonable thing to try, so the refusal says what this
    command takes rather than only that the argument was wrong."""
    (tmp_path / "m.py").write_text("x = 1\n")
    assert cli.main([str(tmp_path / "m.py")]) == 2
    said = capsys.readouterr().err
    assert "directory" in said
    assert "m.py" in said


@pytest.mark.parametrize("argv", [["nowhere"], ["setup.py"]])
def test_neither_refusal_exits_zero(argv, tmp_path, capsys):
    """Exit 2 rather than 0. A caller gating on this tool reads a zero as a clean audit,
    and a refusal that exits zero reports a clean audit that never ran."""
    (tmp_path / "setup.py").write_text("x = 1\n")
    assert cli.main([str(tmp_path / argv[0])]) == 2
    capsys.readouterr()

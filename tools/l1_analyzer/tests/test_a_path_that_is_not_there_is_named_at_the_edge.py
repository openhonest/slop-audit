"""Every command that takes file paths refuses a path that is not there, and says which.

Five commands take paths on the command line, and each one used to hand whatever it was
given to a reader. A path that is not there came back as a stack trace, which tells a
caller the tool broke rather than that they mistyped a filename.

The check sits at the edge for a reason that is stronger than tidiness. `--honest-code`
and `--facets` take several paths, and a run that skipped the missing ones and measured
the rest would report a coverage it did not have. A caller who named a file that is not
there has a different problem from one whose files are clean, and they must not get the
same output.

Every one of these exits 2 and names the path. Exit 2 rather than 1, because 1 is what a
finding exits with: a caller gating on this tool has to be able to tell "your code has a
problem" from "I could not read what you gave me".
"""

import pytest
from l1_analyzer import cli

_MISSING = "no_such_file_anywhere.py"


def _refusal(capsys, *argv) -> str:
    with pytest.raises(SystemExit) as exited:
        cli.main(list(argv))
    assert exited.value.code == 2
    return capsys.readouterr().err


@pytest.fixture
def real(tmp_path):
    (tmp_path / "m.py").write_text("def f() -> int:\n    return 1\n")
    return str(tmp_path / "m.py")


def test_the_facets_command_needs_a_module_and_a_test_file(capsys):
    """One path is not enough to ask the question. This command reads a module against the
    tests that are supposed to hold evidence about it, so a module alone has nothing to
    compare and would read as total silence rather than as a missing argument."""
    assert "at least one test file" in _refusal(capsys, "--facets", "m.py")


def test_the_facets_command_names_the_path_that_is_not_there(capsys, real):
    assert _MISSING in _refusal(capsys, "--facets", real, _MISSING)


def test_the_clause_check_names_the_path_that_is_not_there(capsys, real):
    """Several files are measured in one process, so this is the command where a skipped
    missing path would silently shrink what was measured."""
    assert _MISSING in _refusal(capsys, "--honest-code", real, _MISSING)


def test_the_call_map_names_the_path_that_is_not_there(capsys, real):
    assert _MISSING in _refusal(capsys, "--call-map", real, _MISSING)


def test_the_proof_gate_names_the_path_that_is_not_there(capsys, real):
    assert _MISSING in _refusal(
        capsys, "--prove-facet", real, _MISSING, "0", "arg", "prop", "why")


def test_the_proof_gate_refuses_a_request_number_that_is_not_a_number(capsys, real):
    """The index selects which proof request is being answered. A word there means the
    caller is answering a request nobody made, and running the gate on request zero by
    default would retain a passing test against the wrong function."""
    assert "as a number" in _refusal(
        capsys, "--prove-facet", real, real, "second", "arg", "prop", "why")


def test_a_negative_request_number_is_a_number(capsys, real):
    """It will not select anything, and the gate says so in its own words. What matters
    here is that the argument reader does not refuse it as malformed: the caller typed a
    number, and telling them it is not one would send them looking in the wrong place."""
    assert cli.main(["--prove-facet", real, real, "-3", "arg", "prop", "why"]) == 1
    said = capsys.readouterr().out
    assert "index -3" in said
    assert "as a number" not in said

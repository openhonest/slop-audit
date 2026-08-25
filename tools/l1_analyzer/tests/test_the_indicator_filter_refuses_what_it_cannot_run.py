"""`--indicators banana` selected nothing and exited 0.

A caller scripting this could not tell "no indicator matched, because you typed it wrong"
from "the audit ran and found nothing". That is the silent failure this whole tool exists
to name, in the tool itself, on a documented flag.

The cause is the shape, not the typo. The flag's values were tested against three separate
literal tuples spread through the dispatch, so nothing anywhere held the set of valid
indicators and nothing could refuse a value outside it. An input space left open by a
dispatch that reads closed is L1.21.18, and this file is the clause applied to its own CLI.
"""

import pytest
from l1_analyzer import cli


@pytest.mark.parametrize("given", ["banana", "99", "L1.17", "1,banana", "18b"])
def test_an_indicator_nobody_can_run_is_refused_rather_than_selected_quietly(given):
    """Returned rather than raised. The refusal used to be printed inside the deciding
    function and carried out on SystemExit, which put output in a function whose whole job
    is to decide. It raises a typed refusal now and the boundary maps it to exit 2."""
    assert cli.main([".", "--no-exec", "--format", "json", "--indicators", given]) == 2


def test_the_refusal_names_the_value_and_what_would_have_worked(capsys):
    assert cli.main([".", "--no-exec", "--format", "json", "--indicators", "L1.17"]) == 2
    said = capsys.readouterr()
    message = said.err + said.out
    assert "L1.17" in message, "a refusal that does not name the value cannot be acted on"
    assert "17" in message, "and it has to show the form that would have worked"


@pytest.mark.parametrize("given", ["17", "1,2,18", "all"])
def test_a_value_the_dispatch_can_run_is_still_accepted(given):
    """The other direction. A gate that refuses everything passes the test above and breaks
    the flag."""
    assert cli.main([".", "--no-exec", "--format", "json", "--indicators", given]) == 0


def test_the_valid_set_is_named_once_rather_than_spread_through_the_dispatch():
    """The defect was three literal tuples in three branches, so no reader and no check
    could see the whole input space. One table, and the branches read it."""
    assert "17" in cli.INDICATORS
    assert "banana" not in cli.INDICATORS
    assert len(cli.INDICATORS) >= 20

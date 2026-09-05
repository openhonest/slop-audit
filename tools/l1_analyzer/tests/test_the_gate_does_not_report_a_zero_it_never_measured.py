"""A gate that read nothing must not print a clean line.

The pass line names two readings: "0 production god-files" and "finitely testable". Both
were printed whether or not anything was read. A repository the god-file indicator could not
parse got the same sentence as one it read and cleared.

That is the reading this instrument exists to refuse, on the instrument's own output. The
god-file indicator is already honest: handed a tree with no source it raises rather than
returning zero, and says a share over no files is absent. The gate then tested the value for
being a number, found it was not, appended no problem, and printed the zero itself.

Named on 2026-09-05 by the session working on the Honest Framework, which put the general
case better than the gherkin note here had: a measure unavailable where the discipline is
absent, whose silence reads as a pass, rewards the least organised codebase with the best
result. This file is that argument applied to our own gate.

The state half already had the machinery, `report.census_unread`, and it did not fire here
either: it needs declarations to have been found, and a tree with none has none.
"""

import subprocess

import pytest
from l1_analyzer import cli


@pytest.fixture
def no_source(tmp_path):
    (tmp_path / "README.md").write_text("# documentation only\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_tree_with_no_source_does_not_pass_the_gate(no_source, capsys):
    """Nothing was measured, so there is nothing to pass."""
    code = cli.main([str(no_source), "--gate"])
    printed = capsys.readouterr().out
    assert "0 production god-files" not in printed, printed
    assert code != 0 or "not measured" in printed.lower() or "unread" in printed.lower()


def test_the_line_says_which_reading_was_not_taken(no_source, capsys):
    """A refusal a reader cannot act on is a refusal that stops the work. It has to name
    the measure that could not answer, not merely decline to praise."""
    cli.main([str(no_source), "--gate"])
    printed = capsys.readouterr().out.lower()
    assert "god-file" in printed or "l1.17" in printed


def test_a_tree_the_gate_did_read_still_says_so(capsys):
    """The other direction, so the refusal cannot become a way of never passing. This
    repository has source, the indicator reads it, and the clean line is earned."""
    from pathlib import Path

    here = Path(__file__).resolve().parents[3]
    assert cli.main([str(here), "--gate", "--max-type-escapes", "18",
                     "--max-honest-code", "0"]) == 0
    assert "0 production god-files" in capsys.readouterr().out

"""L1.5 divides code deletions by code additions, as the canon says it does.

The canon defines L1.5 as "lines deleted divided by lines added ACROSS CODE FILES. A high
value indicates sustained refactoring; a low value indicates accumulation without cleanup."
The implementation divided total deletions by total additions over every file in the
history, markdown included.

The classifier that separates them already existed: `_classify_file` tags each path doc,
code or other, and `code_added` was tracked all the way through and never read. L1.4 uses
the doc side of exactly this split, so both halves of the data were present and only one
was used.

It matters most on the repositories this instrument is aimed at. A methodology repository
is mostly prose, and prose is written once and rarely deleted, so measuring it as
refactoring reports accumulation that never happened. This one scored 15.5% Slop with docs
counted. The reverse error is just as real: a repository whose docs are heavily rewritten
would score as refactoring code it never touched.

Prose churn is not code refactoring, and reading one as the other is the instrument
measuring something other than what it names.
"""

import pathlib
import subprocess

import pytest
from l1_analyzer import indicators


def _commit(repo: pathlib.Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", message], check=True, capture_output=True)


@pytest.fixture
def prose_heavy(tmp_path) -> pathlib.Path:
    """Code that is refactored and prose that only ever grows: the shape of a spec
    repository, and the shape the whole-tree divisor reads as accumulation."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "m.py").write_text("\n".join(f"line_{n} = {n}" for n in range(20)) + "\n")
    _commit(tmp_path, "code")
    # Refactor the code: delete most of it. Code delete/add is now high.
    (tmp_path / "m.py").write_text("line_0 = 0\n")
    _commit(tmp_path, "refactor the code down")
    # Add a great deal of prose, deleting none of it.
    (tmp_path / "spec.md").write_text("\n".join(f"paragraph {n}" for n in range(200)) + "\n")
    _commit(tmp_path, "write the spec")
    return tmp_path


def test_prose_additions_do_not_drown_the_code_ratio(prose_heavy):
    """The defect, end to end. Nineteen code lines deleted against twenty added is a
    refactoring signal; two hundred lines of prose in the divisor buries it."""
    result = indicators.compute_git_indicators(prose_heavy, None, None)["L1.5"]
    assert result["value"] > 50, (
        f"L1.5 read {result['value']}, which is the whole-tree ratio. The canon divides by "
        f"lines added across CODE files: {result['details']}"
    )


def test_the_details_line_says_it_counted_code(prose_heavy):
    """A reader has to be able to tell which divisor produced the number."""
    assert "code" in indicators.compute_git_indicators(prose_heavy, None, None)["L1.5"]["details"]


def test_l1_4_still_divides_by_every_added_line(prose_heavy):
    """The other half of the same split, and it is right as it stands: L1.4 is the doc
    share OF ALL additions, so its divisor is the whole tree by definition."""
    result = indicators.compute_git_indicators(prose_heavy, None, None)["L1.4"]
    assert result["value"] > 80, result["details"]


def test_a_repository_with_no_code_refuses_rather_than_reading_zero(tmp_path):
    """A ratio over no code lines is absent, not zero, and zero is the Slop end of this
    scale. A docs-only repository must not be graded as one that never refactors."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("just prose\n")
    _commit(tmp_path, "docs only")
    result = indicators.compute_git_indicators(tmp_path, None, None)["L1.5"]
    assert result["band"] == "n/a"
    assert result["value"] == "n/a"

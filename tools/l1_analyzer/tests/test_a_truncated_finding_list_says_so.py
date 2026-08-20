"""A result that lists fewer findings than it counted says which, in its own details line.

`absolute_paths.scan` caps its finding list at 50 and `dead_code.analyze` caps each of its
three lists at 100. The count is honest: `value` carries the real total and the details
sentence names it. The LIST is short, and nothing said so.

Two fields of one result then disagree. A reader who counts the list gets 50 where the
value says 57, and the only way to notice is to compare the two, which is exactly what
nobody does when one of them is a list they are iterating.

The same principle as the sweep ceiling landed earlier today: a truncated sweep that said
nothing read as a sweep that finished. It speaks only when the cap bit, because a note on
every result is one a reader learns to skip.
"""

import pathlib

import pytest
from l1_analyzer import absolute_paths, dead_code


@pytest.fixture(scope="module")
def many_findings(tmp_path_factory) -> pathlib.Path:
    """More absolute paths than the cap, so the list is short and the count is not."""
    repo = tmp_path_factory.mktemp("paths")
    lines = "\n".join(f'PATH_{n} = "/Users/someone/dev/project/file_{n}.txt"'
                      for n in range(absolute_paths._CAP + 12))
    (repo / "m.py").write_text(lines + "\n")
    return repo


def test_the_count_is_the_real_one(many_findings):
    """The half that was already honest, asserted so the fix cannot quietly cap the count
    instead of disclosing the list."""
    result = absolute_paths.scan(many_findings, "python")
    assert result["value"] > absolute_paths._CAP


def test_the_list_is_capped(many_findings):
    result = absolute_paths.scan(many_findings, "python")
    assert len(result["findings"]) == absolute_paths._CAP


def test_the_details_line_says_the_list_was_cut(many_findings):
    result = absolute_paths.scan(many_findings, "python")
    assert str(absolute_paths._CAP) in result["details"]
    assert "listed" in result["details"], result["details"]


def test_a_result_under_the_cap_says_nothing_about_it(tmp_path):
    """It speaks only when the cap bit. A note on every result is one a reader skips, which
    is how the one that mattered would be missed."""
    (tmp_path / "m.py").write_text('P = "/Users/someone/dev/one.txt"\n')
    details = absolute_paths.scan(tmp_path, "python")["details"]
    assert "listed" not in details, details


def test_a_clean_result_says_nothing_about_it(tmp_path):
    (tmp_path / "m.py").write_text("x = 1\n")
    assert "listed" not in absolute_paths.scan(tmp_path, "python")["details"]


def test_dead_code_discloses_its_own_cap(tmp_path):
    """The other capped result, and it caps three lists rather than one."""
    unreferenced = "\n\n".join(f"def never_called_{n}():\n    return {n}"
                               for n in range(dead_code._CAP + 20))
    (tmp_path / "m.py").write_text(unreferenced + "\n")
    result = dead_code.analyze(tmp_path, "python")
    assert len(result["findings"]) == dead_code._CAP
    assert "listed" in result["details"], result["details"]

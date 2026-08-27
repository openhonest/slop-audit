"""Two functions implementing one named scope, and disagreeing about it.

`_read_source_bytes` asks `_bucket_reason`, which sets aside vendored trees, the scope's own
markers, documentation, conventional tooling files and loose root scripts. `_read_text_files`
applies only the first two. So two indicators declared under the same scope name saw
different file sets, and the name promised they did not.

The disagreement was recorded in features/scope.feature and left standing, because folding
them together would have applied the documentation and tooling reasons under whole-repo,
where the test tree and the loose scripts ARE the subject. That is the actual fault: the
three judgment-call reasons were unconditional, so no scope could decline them.

They are named per scope now. Whole-repo declines all three and reads what it says it reads.
Production takes all three, and one function answers for both readers.
"""

import pytest
from l1_analyzer import scope


def _tree(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    (tmp_path / "pkg" / "app.py").write_text("APP = 1\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.py").write_text("NOTE = 1\n")
    (tmp_path / "setup.py").write_text("SETUP = 1\n")
    (tmp_path / "loose.py").write_text("LOOSE = 1\n")
    return tmp_path


def _read_by_both(repo, named):
    text, _ = scope._read_text_files(repo, frozenset({".py"}), named)
    raw, _ = scope._read_source_bytes(repo, (".py",), named)
    return {p.name for p, _ in text}, {p.name for p, _ in raw}


@pytest.mark.parametrize("named", [scope.PRODUCTION,
                                   scope.PRODUCTION_WITHOUT_CONFORMANCE,
                                   scope.WHOLE_REPO])
def test_both_readers_of_one_scope_see_one_file_set(tmp_path, named):
    text, raw = _read_by_both(_tree(tmp_path), named)
    assert text == raw, sorted(text ^ raw)


def test_production_sets_aside_documentation_tooling_and_loose_scripts(tmp_path):
    text, _ = _read_by_both(_tree(tmp_path), scope.PRODUCTION)
    assert text == {"__init__.py", "app.py"}, sorted(text)


def test_whole_repo_reads_them_because_they_are_its_subject(tmp_path):
    """The reason the three reasons had to become conditional rather than shared. Whole-repo
    measures the ratio of test lines to production lines and whether whitespace is
    disciplined anywhere. A whole-repo reading that skipped the docs and the loose scripts
    would answer a narrower question under a name that promises the wider one."""
    text, _ = _read_by_both(_tree(tmp_path), scope.WHOLE_REPO)
    assert text == {"__init__.py", "app.py", "note.py", "setup.py", "loose.py"}, sorted(text)


@pytest.mark.parametrize("named", list(scope.SCOPES))
def test_a_vendored_tree_is_set_aside_under_every_scope(tmp_path, named):
    """Vendored code is nobody's here to answer for, whatever the question. It stays
    unconditional, and so does machine output, for the same reason."""
    repo = _tree(tmp_path)
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "dep.py").write_text("DEP = 1\n")
    (repo / "pkg" / "made.py").write_text("# @generated\nMADE = 1\n")
    text, raw = _read_by_both(repo, named)
    assert "dep.py" not in text and "dep.py" not in raw
    assert "made.py" not in text and "made.py" not in raw


def test_every_scope_says_which_judgment_calls_it_makes(tmp_path):
    """The table is where a reader checks it, so no scope may leave it unsaid."""
    for named in scope.SCOPES:
        entry = scope.scope_rule(named)
        assert "buckets" in entry, named
        assert set(entry["buckets"]) <= {"docs", "tooling", "root-script"}, named

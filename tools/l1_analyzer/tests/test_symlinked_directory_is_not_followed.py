"""A symlinked directory is not walked, by decision rather than by Python version.

The two tools agreed on symlinked trees by coincidence. pathlib's `**` stopped following
symlinked directories in Python 3.13; walkdir, which the Rust port uses, has never
followed them. So a run of l1_analyzer under 3.12 or earlier would descend into a
symlinked directory the port skips, and the panels would diverge on any repository that
has one.

The decision is the one already written beside it for nested checkouts: measuring a tree
that is not in this commit reports code the commit does not carry. A symlinked directory
points at exactly that, and it can also point at itself.

Stated in code now, so the behaviour does not depend on which interpreter is running.
This machine is on 3.13, where `**` skips them anyway, so the behavioural test alone
would pass either way; the predicate is asserted directly beside it, which is what makes
the assertion mean something on 3.12.

A symlinked FILE is still read. `is_file()` follows symlinks deliberately, which the
walker's own docstring records, and one file is not a tree.
"""

import os
import pathlib
import tempfile

from l1_analyzer.scope import _rglob_files, under_symlinked_dir


def test_source_inside_a_symlinked_directory_is_not_walked():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "src").mkdir()
        (root / "src" / "own.py").write_text("x = 1\n")
        elsewhere = root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "other.py").write_text("y = 2\n")
        os.symlink(elsewhere, root / "src" / "linked")
        found = {p.name for p in _rglob_files(root / "src", "*.py")}
    assert found == {"own.py"}, found


def test_a_symlinked_file_is_still_read():
    """The other half of the decision. One file is not a tree, and `is_file()` follows
    symlinks on purpose."""
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "real.py").write_text("x = 1\n")
        (root / "src").mkdir()
        os.symlink(root / "real.py", root / "src" / "alias.py")
        found = {p.name for p in _rglob_files(root / "src", "*.py")}
    assert found == {"alias.py"}, found


def test_the_predicate_says_so_directly():
    """Asserted apart from the walk, because this interpreter skips them anyway and the
    behavioural test above cannot tell a decision from a version."""
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "real").mkdir()
        os.symlink(root / "real", root / "link")
        assert under_symlinked_dir(root / "link", root) is True
        assert under_symlinked_dir(root / "real", root) is False


def test_the_walker_actually_consults_the_predicate():
    """A structural assertion, and it is here because nothing else on this interpreter can
    make it.

    Python 3.13's `**` skips symlinked directories on its own, so both behavioural tests
    above pass whether or not `_rglob_files` consults anything: measured by deleting the
    clause and re-running them, all three still green. That is precisely the coincidence
    this file exists to end, and a test that cannot tell the decision from the version
    cannot protect the decision.

    So this reads the source. It is the weakest kind of assertion and the only one that
    fails when someone removes the clause as apparently-redundant on 3.13 - which it is,
    on 3.13, and is not on 3.12 or in the Rust port's absence of it.
    """
    import inspect

    from l1_analyzer import scope
    assert "under_symlinked_dir" in inspect.getsource(scope._rglob_files), (
        "the walker no longer consults the predicate; on 3.13 nothing else will notice")

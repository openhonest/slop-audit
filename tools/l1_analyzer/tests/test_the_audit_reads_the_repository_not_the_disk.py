"""An audit reads what the project says is part of it, and everything else in the tree.

A `.gitignore` entry is a statement, written by whoever put it there, that a directory is
not part of the codebase: a build output, a vendored dependency, a scratch tree kept for
reference. Reading those reports code the project has disowned, and a fresh clone then reads
differently from the working copy.

The case that forced it, on 2026-09-05. The Honest Framework held a `python.botched`
directory beside `python`: 262 MB, 20,743 files, ignored at line 19 of its own `.gitignore`.
It carried the only three pieces of provably unbounded state in the whole measurement, so
the repository read as not exhaustively testable on the strength of code it had disowned.

IGNORED, NOT UNTRACKED. My first attempt skipped everything git does not track, which is
wrong and worse than the problem: a module written five minutes ago is untracked too, and it
is the file a developer most wants measured. An audit that goes quiet on uncommitted work
reports on the past. It survived my own tests because a staged file counts as tracked, so
the test below writes a file and never adds it.

Not every tree is a git working copy. A tarball, an extracted archive and a vendored copy
are all real audit subjects, so where there is no git the walk reads everything.
"""

import subprocess

from l1_analyzer.scope import _rglob_files


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    return tmp_path


def _names(root, pattern="*.py"):
    return sorted(p.name for p in _rglob_files(root, pattern))


def test_a_gitignored_directory_is_not_read(tmp_path):
    """The Honest Framework case. A scratch tree the author kept, in no commit, carrying
    the only unbounded state the measurement found."""
    repo = _repo(tmp_path)
    (repo / "kept.py").write_text("x = 1\n")
    (repo / ".gitignore").write_text("scratch/\n")
    scratch = repo / "scratch"
    scratch.mkdir()
    (scratch / "botched.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "kept.py", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=repo, check=True)
    assert _names(repo) == ["kept.py"]


def test_a_tracked_file_is_read_wherever_it_sits(tmp_path):
    repo = _repo(tmp_path)
    deep = repo / "src" / "pkg"
    deep.mkdir(parents=True)
    (deep / "mod.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=repo, check=True)
    assert _names(repo) == ["mod.py"]


def test_a_file_written_and_never_added_is_read(tmp_path):
    """The case that catches the wrong rule, and the reason this file exists in this shape.

    A developer runs the audit on what they just wrote, before committing it. That file is
    untracked and it is the one they most want measured. Skipping it makes the instrument
    report on the past."""
    repo = _repo(tmp_path)
    (repo / "just_written.py").write_text("x = 1\n")
    assert _names(repo) == ["just_written.py"]


def test_a_file_added_but_not_yet_committed_is_read(tmp_path):
    repo = _repo(tmp_path)
    (repo / "new.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "new.py"], cwd=repo, check=True)
    assert _names(repo) == ["new.py"]


def test_a_directory_that_is_not_a_repository_is_still_measured(tmp_path):
    """A tarball, an extracted archive and a vendored copy are all real subjects. Refusing
    them would turn a working reading into no reading at all."""
    (tmp_path / "loose.py").write_text("x = 1\n")
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "inner.py").write_text("y = 2\n")
    assert _names(tmp_path) == ["inner.py", "loose.py"]


def test_an_ignored_file_is_skipped_even_beside_tracked_ones(tmp_path):
    repo = _repo(tmp_path)
    (repo / "kept.py").write_text("x = 1\n")
    (repo / ".gitignore").write_text("build.py\n")
    (repo / "build.py").write_text("y = 2\n")
    subprocess.run(["git", "add", "kept.py", ".gitignore"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "one"], cwd=repo, check=True)
    assert _names(repo) == ["kept.py"]


def test_a_repository_with_no_commits_still_reads_its_files(tmp_path):
    """A tree initialised and not yet committed is a real subject. The rule reads
    `.gitignore`, which needs no history."""
    repo = _repo(tmp_path)
    (repo / "first.py").write_text("x = 1\n")
    assert _names(repo) == ["first.py"]

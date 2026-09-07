"""A checkout that will not copy costs a worker, not the run.

The pool makes one copy per worker. On a filesystem that copies by reference the copies are
nearly free; on any other, eight copies of a 6 GB checkout is 48 GB of real bytes, and that
operation fails in ways the free one does not: disk pressure, a partial copy, no space left
halfway through the sixth worker.

Raised on 2026-09-07 by the session auditing turso, who was about to be the first person to
run that path: their box is ext4 and every verification so far had exercised the reflink one.
They were right, and reading the code with that in mind found two defects.

A failed copy raised out of the pool and took the whole sweep down. By then the sweep has
already asked a model for every proposal, so the expensive half was spent and the traceback
threw it away.

And a copy that failed part way left the half-made directory behind, so the fallback then
failed on a directory that already existed and reported that instead of the real cause. The
reader is sent to the wrong problem.

Now a copy that fails stops the copying, the sweep runs with the workers it got, and the
report says how many it asked for and how many it has. Fewer workers is slower. No workers
would be a sweep that proved nothing, so one is the floor and it is the repository itself.
"""

from __future__ import annotations

import subprocess

import pytest
from l1_analyzer import sweep_pool


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("pub fn f() -> i32 { 1 }\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_a_copy_that_will_not_be_made_leaves_the_sweep_with_fewer_workers(tmp_path, monkeypatch):
    """Every copy after the first fails. The sweep runs on what it has."""
    repo = _repo(tmp_path)
    calls = {"n": 0}

    def copy_once_then_fail(repo_path, destination):
        calls["n"] += 1
        if calls["n"] > 1:
            return ""
        sweep_pool._copy_tree(repo_path, destination)
        return "byte for byte"

    monkeypatch.setattr(sweep_pool, "copy_checkout", copy_once_then_fail)
    made = sweep_pool.checkouts_for(repo, 4, tmp_path / "work")
    assert made["copies"] == 1
    assert made["asked"] == 4
    assert len(made["paths"]) == 1


def test_a_sweep_that_could_copy_nothing_still_has_one_worker(tmp_path, monkeypatch):
    """No workers would be a sweep that proved nothing and reported it as one that found
    nothing. The floor is the repository itself, proven in place as a serial sweep always
    was."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(sweep_pool, "copy_checkout", lambda *a: "")
    made = sweep_pool.checkouts_for(repo, 4, tmp_path / "work")
    assert made["paths"] == [repo]
    assert made["copies"] == 0


def test_the_report_says_it_asked_for_more_than_it_got(tmp_path, monkeypatch):
    """A sweep that wanted eight workers and ran on two must not read like one that asked
    for two."""
    monkeypatch.setattr(sweep_pool, "copy_checkout", lambda *a: "")
    made = sweep_pool.checkouts_for(_repo(tmp_path), 8, tmp_path / "work")
    said = sweep_pool.pool_detail(len(made["paths"]), made["copies"], made["how"], made["asked"])
    assert "8" in said and "could not be made" in said, said


def test_a_half_made_copy_is_cleared_before_anything_else_is_tried(tmp_path):
    """A failed copy leaves a directory behind. Trying the next thing against it reports
    that the directory exists, which sends the reader to the wrong problem."""
    repo = _repo(tmp_path)
    destination = tmp_path / "work" / "worker-0"
    destination.mkdir(parents=True)
    (destination / "left-over").write_text("from a copy that died")
    assert sweep_pool.copy_checkout(repo, destination)
    assert not (destination / "left-over").exists()
    assert (destination / "src" / "lib.rs").read_text() == "pub fn f() -> i32 { 1 }\n"


@pytest.mark.parametrize("workers", [2, 3])
def test_the_real_copy_produces_a_working_checkout(tmp_path, workers):
    """The path a filesystem without reflink takes, which is the one nothing had run."""
    made = sweep_pool.checkouts_for(_repo(tmp_path), workers, tmp_path / "work")
    assert made["how"] in {"by reference", "byte for byte"}
    for path in made["paths"]:
        assert (path / "src" / "lib.rs").read_text() == "pub fn f() -> i32 { 1 }\n"
        assert (path / ".git").is_dir()

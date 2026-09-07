"""Each worker proves in its own copy of the repository, and the run says what a copy cost.

The sweep proves a module by appending a test to that module's own source file, compiling,
and putting the file back. Two workers in one checkout would restore each other's files
mid-compile, and cargo locks the target directory besides. So parallelism needs isolation
rather than a thread pool.

The cost is disk. A turso checkout with a warm target directory is 34 GB. On a filesystem
that copies by reference, which is APFS here and Btrfs or XFS with reflink on Linux, the copy
is nearly free until something writes to it. On any other filesystem it is 34 GB a worker.

A run must say which of those it got. Eight workers is a good trade on one filesystem and a
quarter of a terabyte on another, and a reader who is told only "8 workers" cannot tell them
apart.
"""

from __future__ import annotations

import subprocess

from l1_analyzer import sweep_pool


def boundary(fn):
    """Mark this file's one edge, and change nothing about it."""
    return fn


@boundary
def _repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "lib.rs").write_text("pub fn f() -> i32 { 1 }\n")
    (tmp_path / "Cargo.toml").write_text("[package]\nname = \"x\"\nversion = \"0.1.0\"\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_one_worker_proves_in_the_repository_itself(tmp_path):
    """No copy where none is needed. A single-worker sweep is what it always was, and
    copying a checkout to hand it back to itself would cost the disk for nothing."""
    repo = _repo(tmp_path)
    made = sweep_pool.checkouts_for(repo, 1, tmp_path / "work")
    assert made["paths"] == [repo]
    assert made["copies"] == 0


def test_a_parallel_sweep_never_proves_in_the_repository_itself(tmp_path):
    """Every worker gets a copy, the first one included, so the checkout under audit is
    never edited at all.

    Asked for by the session auditing turso on 2026-09-07, before eight dirty checkouts
    rather than after. A module is proven by appending a test to its own source file and
    putting the file back, and a hard kill skips the putting back. One killed serial sweep
    left one modified file they found by hand. Eight workers would leave up to eight, in
    eight directories, and nobody would know which.

    A copy is disposable by construction, so an interrupt leaves nothing anybody has to
    clean: the directories go, and the repository was never touched."""
    repo = _repo(tmp_path)
    made = sweep_pool.checkouts_for(repo, 3, tmp_path / "work")
    assert len(made["paths"]) == 3
    assert repo not in made["paths"]
    assert len({str(p) for p in made["paths"]}) == 3
    for path in made["paths"]:
        assert (path / "src" / "lib.rs").read_text() == "pub fn f() -> i32 { 1 }\n"


def test_a_copy_is_its_own_checkout_and_not_a_link_to_the_first(tmp_path):
    """The whole point of the copy. A worker that edited a file shared with another worker
    would be the defect this exists to remove."""
    repo = _repo(tmp_path)
    made = sweep_pool.checkouts_for(repo, 2, tmp_path / "work")
    (made["paths"][1] / "src" / "lib.rs").write_text("edited by the second worker\n")
    assert (made["paths"][0] / "src" / "lib.rs").read_text() == "pub fn f() -> i32 { 1 }\n"
    assert (repo / "src" / "lib.rs").read_text() == "pub fn f() -> i32 { 1 }\n"


def test_the_run_says_how_the_copies_were_made(tmp_path):
    """Eight workers is a good trade on a filesystem that copies by reference and a quarter
    of a terabyte on one that does not. A reader told only the number cannot tell which."""
    made = sweep_pool.checkouts_for(_repo(tmp_path), 2, tmp_path / "work")
    assert made["how"] in {"by reference", "byte for byte"}
    assert made["copies"] == 2


def test_the_sentence_a_reader_gets_names_the_pool_and_the_cost():
    said = sweep_pool.pool_detail(8, 8, "by reference")
    assert "8" in said and "by reference" in said
    assert "repository" in said, "a reader is not told their own checkout was left alone"


def test_a_single_worker_sweep_says_so_rather_than_saying_nothing():
    """A sweep that wanted eight workers and got one must not read like a sweep that asked
    for one."""
    assert "1 worker" in sweep_pool.pool_detail(1, 0, "by reference")
